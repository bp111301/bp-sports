"""Missingness-robust NHL development; excluded failed season never evaluated."""
import argparse,hashlib,importlib.util,json,tempfile,shutil
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=module('nhl_20261028_base',HERE/'vendor/nhl/backtest_baseline.py')
adv=module('nhl_20261028_adv',HERE/'vendor/nhl/experiment_team_stats.py')
DEV=['20212022','20222023','20232024','20242025'];NAMES=['control','no_indicators','guarded_no_indicators']
def historical_games(t):
    rows=[]
    for (season,gid),g in t.groupby(['season','gameId'],sort=True):
        if len(g)!=2 or set(g.homeRoad)!={'H','R'}:raise ValueError('Unpaired official NHL game')
        h=g[g.homeRoad.eq('H')].iloc[0];a=g[g.homeRoad.eq('R')].iloc[0]
        if h.gameDate!=a.gameDate or h.gamesPlayed!=1 or a.gamesPlayed!=1 or int(h.wins)+int(a.wins)!=1:raise ValueError('Invalid completed game identity')
        hs,aw=float(h.goalsFor),float(a.goalsFor)
        if hs!=float(a.goalsAgainst) or aw!=float(h.goalsAgainst):raise ValueError('Inconsistent official score pair')
        if hs==aw:
            if int(h.winsInShootout)+int(a.winsInShootout)!=1:raise ValueError('Tied result without shootout winner')
            if h.wins:hs+=1
            else:aw+=1
        if int(hs>aw)!=int(h.wins):raise ValueError('Winner disagrees with normalized score')
        rows.append(dict(game_id=int(gid),season=str(season),game_date=pd.Timestamp(h.gameDate).normalize(),home_id=int(h.teamId),away_id=int(a.teamId),home_team=a.opponentTeamAbbrev,away_team=h.opponentTeamAbbrev,home_score=hs,away_score=aw,home_win=int(h.wins)))
    return pd.DataFrame(rows).sort_values(['season','game_date','game_id']).reset_index(drop=True)
def selection_data(path):
    path=Path(path);allowed=[str(y)+str(y+1) for y in range(2018,2025)]
    # Only these files enter the extraction loader. 2025–26 is not opened here.
    with tempfile.TemporaryDirectory() as temp:
        for season in allowed:
            for report in ['summary','powerplay','penaltykill']:
                source=path/f'{report}_{season}.csv'
                if not source.exists():raise ValueError('Missing development source '+str(source))
                shutil.copyfile(source,Path(temp)/source.name)
        t=adv.load_team_stats(temp)
    if t.season.astype(str).gt('20242025').any():raise ValueError('Excluded NHL season entered development')
    d=historical_games(t)
    if t.duplicated(['season','gameId','teamId']).any():raise ValueError('Duplicate NHL team game')
    return d,t
def learner(features,indicators=False):
    prep=ColumnTransformer([('num',Pipeline([('imp',SimpleImputer(strategy='median',add_indicator=indicators)),('scale',StandardScaler())]),features)],remainder='drop')
    return Pipeline([('prep',prep),('model',LogisticRegression(C=.5,max_iter=3000))])
def advanced_available(x,features):return np.isfinite(x[features].to_numpy(float)).all(axis=1)
def fit_pair(d,x,features,tr):
    full=learner(features);fallback=learner(base.FEATURES)
    full.fit(x.loc[tr,features],d.loc[tr,'home_win']);fallback.fit(x.loc[tr,base.FEATURES],d.loc[tr,'home_win'])
    return full,fallback
def predict_guarded(models,x,features,advanced):
    p=models[0].predict_proba(x[features])[:,1];ok=advanced_available(x,advanced)
    if (~ok).any():p[~ok]=models[1].predict_proba(x.loc[~ok,base.FEATURES])[:,1]
    return p
def summarize(pred):
    return {name:{'overall':adv.metrics(g.home_win.to_numpy(),g.probability.to_numpy()),'by_season':[{**adv.metrics(s.home_win.to_numpy(),s.probability.to_numpy()),'season':season} for season,s in g.groupby('season')]} for name,g in pred.groupby('candidate')}
def eligibility(scores):
    control=scores['control'];out={}
    for name in NAMES[1:]:
        s=scores[name];a=s['overall'];b=control['overall'];improved=sum(x['brier']<y['brier'] for x,y in zip(s['by_season'],control['by_season']))
        out[name]={'research_eligible':bool(a['brier']<b['brier'] and a['log_loss']<b['log_loss'] and a['accuracy']>=b['accuracy'] and improved>=3),'brier_improved_seasons':improved,'production_promoted':False}
    return out
def run(data_dir,out_dir):
    d,t=selection_data(data_dir);bx=base.build_features(d);x,af=adv.attach(d,bx,t,20);features=base.FEATURES+af
    expected=set(zip(t.gameId.astype(int),t.teamId.astype(int)))
    if any((int(r.game_id),int(team)) not in expected for r in d.itertuples() for team in [r.home_id,r.away_id]):raise ValueError('Missing NHL team-game join')
    rows=[];boundaries=[]
    for season in DEV:
        tr=d.index[d.season.lt(season)];te=d.index[d.season.eq(season)]
        if not len(tr) or not len(te) or not d.loc[tr,'season'].lt(season).all():raise ValueError('NHL fold boundary invalid')
        control=learner(features,True);control.fit(x.loc[tr,features],d.loc[tr,'home_win']);models=fit_pair(d,x,features,tr)
        probabilities={'control':control.predict_proba(x.loc[te,features])[:,1],'no_indicators':models[0].predict_proba(x.loc[te,features])[:,1],'guarded_no_indicators':predict_guarded(models,x.loc[te],features,af)}
        boundaries.append({'test_season':season,'training_max_season':str(d.loc[tr,'season'].max()),'fallback_test_games':int((~advanced_available(x.loc[te],af)).sum())})
        for name,p in probabilities.items():
            for i,v in zip(te,p):rows.append({'game_id':int(d.at[i,'game_id']),'season':season,'candidate':name,'home_win':int(d.at[i,'home_win']),'probability':float(v),'training_max_season':str(d.loc[tr,'season'].max()),'advanced_available':bool(advanced_available(x.loc[[i]],af)[0])})
        print('NHL fold',season,'done',flush=True)
    pred=pd.DataFrame(rows);scores=summarize(pred);decisions=eligibility(scores);out=Path(out_dir);out.mkdir(parents=True,exist_ok=True);pred.to_csv(out/'development_predictions.csv',index=False)
    result={'status':'reused_historical_development_only','excluded_from_selection':['20252026','20262027'],'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),'source_adapter':'Official per-game team report pairs; add only the official shootout winner goal to tied regulation/OT score totals; rolling stats keep unadjusted per-game team stats. Same date/order semantics as baseline.','scores':scores,'decisions':decisions,'fold_boundaries':boundaries,'input_audit':{'games':len(d),'team_stat_rows':len(t),'duplicate_game_ids':int(d.game_id.duplicated().sum()),'join_coverage':1.,'advanced_features':af,'missingness':{f:float(x[f].isna().mean()) for f in features}}}
    (out/'development_results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'scores':{k:v['overall'] for k,v in scores.items()},'decisions':decisions},indent=2),flush=True)
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',default='runtime/challengers_20261028/nhl/team_game_stats');ap.add_argument('--out-dir',default='runtime/challengers_20261028/results/nhl');a=ap.parse_args();run(a.data_dir,a.out_dir)
if __name__=='__main__':main()
