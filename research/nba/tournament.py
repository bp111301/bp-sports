"""Fixed, preregistered NBA candidate tournament; original baseline is immutable."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from baseline import ROOT, FEATURES, PRIORS, load_games, build_features, metrics, bootstrap

EXTRA = ['opp_efg','opp_tov','opp_orb','opp_ftr','three_share','assist_rate']
EXTRA_PRIORS = np.array([.50,.13,.25,.25,.35,.25])
ADJUSTED = ['adjusted_off','adjusted_def']
FATIGUE = ['home_rest','away_rest','home_b2b','away_b2b','games3_diff','games5_diff']
CANDIDATES = [
    ('baseline_control',20,[],False),('windows10',10,[],False),
    ('windows30',30,[],False),('season_history',None,[],False),
    ('advanced20',20,EXTRA,False),('advanced10',10,EXTRA,False),
    ('advanced30',30,EXTRA,False),('advanced_season',None,EXTRA,False),
    ('opponent_adjusted20',20,ADJUSTED,False),('opponent_adjusted30',30,ADJUSTED,False),
    ('fatigue20',20,FATIGUE,False),('recency2',20,[],True),
]

def attach_extra(games):
    box=pd.concat([pd.read_parquet(ROOT/f'data/nba/source/box_{s}.parquet') for s in range(2016,2026)],ignore_index=True)
    lookup={(str(int(r.game_id)),str(int(r.team_id))):r for r in box.itertuples(index=False)}
    records=[]
    for r in games.to_dict('records'):
        h=lookup[r['game_id'],r['home_id']]; a=lookup[r['game_id'],r['away_id']]
        for side,t,opp,opp_side in [('home',h,a,'away'),('away',a,h,'home')]:
            r[side+'_extra']=[*r[opp_side+'_stats'][3:7],float(t.three_point_field_goals_attempted)/float(t.field_goals_attempted),float(t.assists)/float(t.field_goals_attempted)]
            assert np.isfinite(r[side+'_extra']).all()
        records.append(r)
    return pd.DataFrame(records)

def window_features(games,window):
    base=build_features(games).set_index('game_id'); rows=[]
    histories=defaultdict(list); extra=defaultdict(list); residual=defaultdict(list); played=defaultdict(list)
    current=None
    def mean(values,prior):
        v=values[-window:] if window else values
        return ((np.sum(v,axis=0) if v else np.zeros(len(prior)))+5*prior)/(len(v)+5)
    for day,batch in games.sort_values(['date','game_id']).groupby('date',sort=True):
        season=int(batch.iloc[0].season)
        if season!=current:
            histories.clear();extra.clear();residual.clear();played.clear();current=season
        updates=[]
        for r in batch.to_dict('records'):
            h,a=r['home_id'],r['away_id']; row=base.loc[r['game_id']].to_dict();row['game_id']=r['game_id']
            hs=mean(histories[h],PRIORS); ast=mean(histories[a],PRIORS)
            row.update(dict(zip(FEATURES[2:10],hs-ast)))
            row['history_diff']=min(len(histories[h]),window or 1000)-min(len(histories[a]),window or 1000)
            row.update(dict(zip(EXTRA,mean(extra[h],EXTRA_PRIORS)-mean(extra[a],EXTRA_PRIORS))))
            row.update(dict(zip(ADJUSTED,mean(residual[h],np.zeros(2))-mean(residual[a],np.zeros(2)))))
            rests=[min(7,(pd.Timestamp(day)-pd.Timestamp(played[t][-1])).days-1) if played[t] else 7 for t in (h,a)]
            row.update(home_rest=rests[0],away_rest=rests[1],home_b2b=float(rests[0]==0),away_b2b=float(rests[1]==0))
            for n in (3,5):
                count=lambda t:sum(0<(pd.Timestamp(day)-pd.Timestamp(d)).days<=n for d in played[t])
                row[f'games{n}_diff']=count(h)-count(a)
            rows.append(row)
            # Opposing quality is measured before this entire date's outcomes.
            ref=lambda t:(np.sum(histories[t][-20:],axis=0) if histories[t] else np.zeros(8))+5*PRIORS
            href=ref(h)/(min(20,len(histories[h]))+5); aref=ref(a)/(min(20,len(histories[a]))+5)
            updates.append((r,[r['home_stats'][0]-aref[1],r['home_stats'][1]-aref[0]],[r['away_stats'][0]-href[1],r['away_stats'][1]-href[0]]))
        for r,hr,ar in updates:
            for side,res in [('home',hr),('away',ar)]:
                t=r[side+'_id']; histories[t].append(r[side+'_stats']);extra[t].append(r[side+'_extra']);residual[t].append(res);played[t].append(day)
    return pd.DataFrame(rows)

def run_candidate(f,columns,weighted=False):
    rows=[]
    for season in range(2019,2026):
        train=f[f.season<season]; test=f[f.season==season].copy()
        assert train.date.max()<test.date.min()
        model=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=42))
        kwargs={}
        if weighted:
            weights=np.power(.5,(season-1-train.season.to_numpy())/2.)
            weights=weights/weights.mean()
            kwargs={'standardscaler__sample_weight':weights,'logisticregression__sample_weight':weights}
        model.fit(train[columns],train.y,**kwargs)
        test['probability']=model.predict_proba(test[columns])[:,1]
        test['training_last_date']=train.date.max()
        rows.append(test[['game_id','season','date','y','probability','training_last_date']])
    return pd.concat(rows,ignore_index=True)

def eligibility(candidate,reference,seasons):
    improved=sum(candidate[s]['brier']<reference[s]['brier'] for s in seasons)
    pooled=candidate['pooled']; control=reference['pooled']
    checks=dict(brier_gain_at_least_0005=control['brier']-pooled['brier']>=.0005,
                log_loss_improves=pooled['log_loss']<control['log_loss'],
                accuracy_preserved=pooled['correct']>=control['correct'],
                five_seasons_improve=improved>=5,
                latest_two_improve=all(candidate[s]['brier']<reference[s]['brier'] for s in (2024,2025)))
    return dict(eligible=all(checks.values()),checks=checks,brier_improved_seasons=improved)

def main():
    games,audit=load_games();games=attach_extra(games)
    frames={w:window_features(games,w) for w in (10,20,30,None)}
    outputs={}; scores={}; byseason=[]
    original=pd.read_csv(ROOT/'research/nba/results/baseline_oof_predictions.csv',dtype={'game_id':str})
    for name,window,add,weighted in CANDIDATES:
        oof=run_candidate(frames[window],FEATURES+add,weighted)
        assert oof.game_id.tolist()==original.game_id.tolist() and np.array_equal(oof.y,original.y)
        if name=='baseline_control':
            np.testing.assert_allclose(oof.probability,original.baseline_probability,rtol=0,atol=1e-12)
        outputs[name]=oof
        scores[name]={'pooled':metrics(oof.y,oof.probability)}
        for s,g in oof.groupby('season'):
            scores[name][int(s)]=metrics(g.y,g.probability)
            byseason.append(dict(candidate=name,season=int(s),**scores[name][int(s)]))
    reference=scores['baseline_control']; leaderboard=[]
    for name in outputs:
        checks=eligibility(scores[name],reference,list(range(2019,2026))) if name!='baseline_control' else dict(eligible=False,checks={},brier_improved_seasons=0)
        leaderboard.append(dict(candidate=name,**scores[name]['pooled'],**checks))
    eligible=[r for r in leaderboard if r['eligible']]
    selected=min(eligible,key=lambda r:(r['brier'],r['log_loss'],r['candidate']))['candidate'] if eligible else 'baseline_control'
    for row in leaderboard:
        paired=outputs[row['candidate']].rename(columns={'probability':'baseline_probability'}).copy()
        paired['elo_probability']=outputs['baseline_control'].probability.to_numpy()
        row['date_bootstrap_vs_baseline']=bootstrap(paired)
    out=ROOT/'research/nba/results';out.mkdir(exist_ok=True)
    pd.DataFrame(byseason).to_csv(out/'tournament_by_season.csv',index=False)
    combined=pd.concat([f.assign(candidate=n) for n,f in outputs.items()],ignore_index=True)
    combined.to_csv(out/'tournament_oof_predictions.csv',index=False)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    summary=dict(status='development_only_not_promoted',selected_development_candidate=selected,automatic_promotion=False,holdout_evaluated=False,excluded_holdout_season=2026,matched_games=len(original),candidate_count=len(CANDIDATES),leaderboard=sorted(leaderboard,key=lambda r:r['brier']),source_audit=audit,code_sha256=sha(Path(__file__)),baseline_code_sha256=sha(ROOT/'research/nba/baseline.py'),protocol_sha256=sha(ROOT/'research/nba/TOURNAMENT_PROTOCOL.md'),baseline_oof_sha256=sha(ROOT/'research/nba/results/baseline_oof_predictions.csv'),source_manifest_sha256=sha(ROOT/'data/nba/source/manifest.json'))
    (out/'tournament_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(pd.DataFrame(leaderboard)[['candidate','accuracy','brier','log_loss','eligible','brier_improved_seasons']].sort_values('brier').to_string(index=False))
    print('Selected development candidate:',selected,'; holdout unopened')

if __name__=='__main__':main()
