"""Chronological, date-batched NBA team baseline. No holdout loading."""
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

ROOT = Path(__file__).resolve().parents[2]
FEATURES = ['home_advantage','elo_diff','off_diff','def_diff','pace_diff','efg_diff','tov_diff','orb_diff','ftr_diff','win_diff','net5_diff','rest_diff','b2b_diff','history_diff']
PRIORS = np.array([108.,108.,100.,.50,.13,.25,.25,.50])
BOX_FIELDS = ['field_goals_made','field_goals_attempted','three_point_field_goals_made','free_throws_made','free_throws_attempted','offensive_rebounds','defensive_rebounds','turnovers','team_score']
DATE_OVERRIDES = {'401161536':'2020-02-29'}
# NBA official scorer's report confirms the archive's March 1 morning date is wrong:
# https://statsdmz.nba.com/pdfs/20200229/20200229_GSWPHX_book.pdf

def truth(value):
    return str(value).lower() in ('true','1','1.0')

def load_games(seasons=range(2016,2026)):
    games, audit = [], []
    for season in seasons:
        schedule = pd.read_parquet(ROOT/f'data/nba/source/schedule_{season}.parquet')
        box = pd.read_parquet(ROOT/f'data/nba/source/box_{season}.parquet')
        assert not schedule.game_id.duplicated().any(), f'duplicate schedule {season}'
        assert not box.duplicated(['game_id','team_id']).any(), f'duplicate box {season}'
        regular = schedule[pd.to_numeric(schedule.season_type)==2].copy()
        joined = {str(int(k)): v for k,v in box.groupby('game_id')}
        reasons = defaultdict(int)
        for r in regular.to_dict('records'):
            gid = str(int(r['game_id']))
            if not (1<=int(r['home_id'])<=30 and 1<=int(r['away_id'])<=30):
                reasons['exhibition_non_nba_teams'] += 1; continue
            if not truth(r['status_type_completed']) or r['status_type_state']!='post':
                reasons['unfinished'] += 1; continue
            # ESPN sometimes classifies the non-record Cup final as regular season.
            note = str(r.get('notes_headline','')).lower()
            if ('cup' in note or 'tournament' in note) and ('championship' in note or 'final' in note and 'semifinal' not in note and 'quarterfinal' not in note):
                reasons['cup_championship'] += 1; continue
            b = joined.get(gid)
            if b is None or len(b)!=2:
                reasons['missing_box_pair'] += 1; continue
            home = b[b.team_home_away=='home']; away = b[b.team_home_away=='away']
            if len(home)!=1 or len(away)!=1:
                raise ValueError(f'Invalid home/away {gid}')
            h,a = home.iloc[0],away.iloc[0]
            assert int(h.team_id)==int(r['home_id']) and int(a.team_id)==int(r['away_id'])
            assert int(h.opponent_team_id)==int(a.team_id) and int(a.opponent_team_id)==int(h.team_id)
            assert float(h.team_score)==float(r['home_score']) and float(a.team_score)==float(r['away_score']), gid
            vals = pd.to_numeric(pd.concat([h[BOX_FIELDS],a[BOX_FIELDS]]),errors='coerce')
            if not np.isfinite(vals).all() or (vals<0).any():
                reasons['invalid_box'] += 1; continue
            if float(h.team_score)==float(a.team_score):
                raise ValueError(f'Tied completed game {gid}')
            if any(2*float(t.field_goals_made)+float(t.three_point_field_goals_made)+float(t.free_throws_made)!=float(t.team_score) for t in (h,a)):
                reasons['box_points_do_not_reconcile'] += 1; continue
            start = pd.to_datetime(r['date'],utc=True)
            day = start.tz_convert('America/New_York').date().isoformat()
            day = DATE_OVERRIDES.get(gid,day)
            neutral = truth(r['neutral_site']) or (season==2020 and day>='2020-07-01')
            possessions = np.mean([float(t.field_goals_attempted)+.44*float(t.free_throws_attempted)-float(t.offensive_rebounds)+float(t.turnovers) for t in (h,a)])
            if possessions<=0: raise ValueError(f'Invalid possessions {gid}')
            def stats(t,opp):
                return [100*float(t.team_score)/possessions,100*float(opp.team_score)/possessions,possessions,
                        (float(t.field_goals_made)+.5*float(t.three_point_field_goals_made))/float(t.field_goals_attempted),
                        float(t.turnovers)/possessions,
                        float(t.offensive_rebounds)/max(1,float(t.offensive_rebounds)+float(opp.defensive_rebounds)),
                        float(t.free_throws_attempted)/float(t.field_goals_attempted),float(t.team_score>opp.team_score)]
            games.append(dict(game_id=gid,season=season,date=day,start_time=start.isoformat(),home_id=str(int(h.team_id)),away_id=str(int(a.team_id)),home_team=r['home_abbreviation'],away_team=r['away_abbreviation'],neutral=neutral,y=int(h.team_score>a.team_score),home_score=float(h.team_score),away_score=float(a.team_score),home_stats=stats(h,a),away_stats=stats(a,h)))
        audit.append(dict(season=season,schedule_regular=len(regular),included=sum(g['season']==season for g in games),excluded=dict(reasons),date_corrections={k:v for k,v in DATE_OVERRIDES.items() if k in joined}))
    return pd.DataFrame(games).sort_values(['date','game_id']).reset_index(drop=True),audit

def build_features(games):
    history = defaultdict(lambda: deque(maxlen=20)); last = {}; elo = defaultdict(lambda:1500.)
    rows=[]; active_season=None
    for day, batch in games.sort_values(['date','game_id']).groupby('date',sort=True):
        season = int(batch.iloc[0].season)
        assert batch.season.nunique()==1
        if season!=active_season:
            history.clear(); last.clear()
            for team in elo: elo[team]=1500+.75*(elo[team]-1500)
            active_season=season
        def state(team):
            h=list(history[team]); avg=(np.sum(h,axis=0) if h else np.zeros(8))
            avg=(avg+5*PRIORS)/(len(h)+5)
            recent=h[-5:]
            net=sum(v[0]-v[1] for v in recent)/(len(recent)+5)
            rest=min(7,(pd.Timestamp(day)-pd.Timestamp(last[team])).days-1) if team in last else 7
            assert rest>=0, 'Two same-date games for a team or invalid ordering'
            return avg,net,rest,len(h)
        updates=[]
        for r in batch.to_dict('records'):
            h,a=r['home_id'],r['away_id']; hs,hn,hr,hcount=state(h); ast,an,ar,acount=state(a)
            advantage=0. if r['neutral'] else 1.
            ep=1/(1+10**(-(elo[h]-elo[a]+65*advantage)/400))
            diff=hs-ast
            feature=[advantage,elo[h]-elo[a],*diff.tolist(),hn-an,hr-ar,float(hr==0)-float(ar==0),hcount-acount]
            row={k:r[k] for k in ['game_id','season','date','start_time','home_team','away_team','y']}
            row.update(dict(zip(FEATURES,feature))); row['elo_probability']=ep
            row['history_cutoff']=day; rows.append(row)
            updates.append((r,20*(r['y']-ep)))
        # Entire date is predicted before any current-date score/stat update.
        seen=set()
        for r,change in updates:
            h,a=r['home_id'],r['away_id']
            assert h not in seen and a not in seen, 'Multiple team games on same date'
            seen.update((h,a))
            elo[h]+=change; elo[a]-=change
            history[h].append(r['home_stats']); history[a].append(r['away_stats'])
            last[h]=last[a]=day
    return pd.DataFrame(rows)

def metrics(y,p):
    return dict(games=len(y),correct=int(np.sum((np.asarray(p)>=.5)==np.asarray(y))),accuracy=float(accuracy_score(y,np.asarray(p)>=.5)),brier=float(brier_score_loss(y,p)),log_loss=float(log_loss(y,p,labels=[0,1])))

def evaluate(features):
    records=[]
    for season in range(2019,2026):
        train=features[features.season<season]; test=features[features.season==season].copy()
        assert len(train)>0 and len(test)>0 and train.date.max()<test.date.min()
        model=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=42))
        model.fit(train[FEATURES],train.y)
        test['baseline_probability']=model.predict_proba(test[FEATURES])[:,1]
        test['home_frequency_probability']=float(train.y.mean())
        test['training_last_date']=train.date.max()
        records.append(test)
    return pd.concat(records,ignore_index=True)

def bootstrap(oof):
    # Negative Brier/log-loss delta is better; positive accuracy delta is better.
    y=oof.y.to_numpy(); p=oof.baseline_probability.to_numpy(); q=oof.elo_probability.to_numpy()
    delta=pd.DataFrame({'date':oof.date,'brier':(p-y)**2-(q-y)**2,'log_loss':-(y*np.log(p)+(1-y)*np.log1p(-p))+(y*np.log(q)+(1-y)*np.log1p(-q)),'accuracy':((p>=.5)==y).astype(float)-((q>=.5)==y).astype(float)})
    sums=delta.groupby('date')[['brier','log_loss','accuracy']].sum().to_numpy(); counts=delta.groupby('date').size().to_numpy()
    rng=np.random.default_rng(42); draws=[]
    for _ in range(2000):
        ix=rng.integers(0,len(counts),len(counts)); draws.append(sums[ix].sum(axis=0)/counts[ix].sum())
    return {name:dict(delta=float(delta[name].mean()),interval95=np.quantile(np.array(draws)[:,i],[.025,.975]).tolist()) for i,name in enumerate(['brier','log_loss','accuracy'])}

def main():
    out=ROOT/'research/nba/results'; out.mkdir(parents=True,exist_ok=True)
    games,audit=load_games(); features=build_features(games); oof=evaluate(features)
    oof.to_csv(out/'baseline_oof_predictions.csv',index=False)
    season_rows=[]; pooled={}
    for name,col in [('team_logistic','baseline_probability'),('elo','elo_probability'),('home_frequency','home_frequency_probability')]:
        pooled[name]=metrics(oof.y,oof[col])
        for season,g in oof.groupby('season'):
            season_rows.append(dict(model=name,season=int(season),**metrics(g.y,g[col])))
    pd.DataFrame(season_rows).to_csv(out/'baseline_by_season.csv',index=False)
    calibration=[]
    for lower in np.arange(0,1,.1):
        group=oof[(oof.baseline_probability>=lower)&(oof.baseline_probability<lower+.1)]
        if len(group): calibration.append(dict(lower=float(lower),games=len(group),mean_probability=float(group.baseline_probability.mean()),home_win_rate=float(group.y.mean())))
    summary=dict(status='development_only_not_promoted',development_seasons=list(range(2019,2026)),excluded_holdout_season=2026,holdout_evaluated=False,source_audit=audit,features=FEATURES,pooled=pooled,baseline_vs_elo_date_bootstrap=bootstrap(oof),calibration=calibration,protocol_sha256=hashlib.sha256((ROOT/'research/nba/PROTOCOL.md').read_bytes()).hexdigest(),code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'baseline_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(pooled,indent=2))

if __name__=='__main__': main()
