"""Locked experimental watchlist: immutable pregame records, no production picks."""
from datetime import datetime,timezone
import hashlib,json,sys
from pathlib import Path
import importlib.metadata
import joblib
import numpy as np
import pandas as pd

NHL=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(NHL));sys.path.insert(0,str(NHL/'v2'))
from experiment_goalies import base,adv,model
from experiment_models import recent_weights
from experiment_regulation import strength_features,regulation_labels

ROOT=Path('model/nhl/v2_research');OUT=Path('data/nhl/v2_research')
PACKAGES=['numpy','pandas','scikit-learn','scipy','joblib','requests']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def code_hashes():
    return {str(p):sha(p) for p in [NHL/'backtest_baseline.py',NHL/'experiment_team_stats.py',NHL/'experiment_goalies.py',NHL/'v2/experiment_models.py',NHL/'v2/experiment_regulation.py',Path(__file__)]}

def freeze_if_needed(d,t):
    spec=json.loads((ROOT/'spec.json').read_text());bundle=ROOT/'watchlist.joblib'
    versions={package:importlib.metadata.version(package) for package in PACKAGES}
    if bundle.exists():
        manifest=json.loads((ROOT/'manifest.json').read_text())
        if manifest['bundle_sha256']!=sha(bundle) or manifest['spec_sha256']!=sha(ROOT/'spec.json') or manifest['code_sha256']!=code_hashes() or manifest['package_versions']!=versions:raise ValueError('Locked watchlist identity/dependencies changed; do not silently refit')
        return joblib.load(bundle),manifest
    if d.season.max()!=spec['training_last_season'] or (d.season>spec['training_last_season']).any():raise ValueError('Unexpected watchlist training boundary')
    bx=base.build_features(d);x,af=adv.attach(d,bx,t,20);rx,_=adv.attach(d,strength_features(d),t,20);features=base.FEATURES+af
    reference=model(features).fit(x[features],d.home_win)
    decay=model(features).fit(x[features],d.home_win,model__sample_weight=recent_weights(d.season))
    regulation=model(features).fit(rx[features],regulation_labels(d).reg_outcome)
    payload={'reference':reference,'decay':decay,'regulation':regulation,'features':features,'spec':spec}
    joblib.dump(payload,bundle,compress=3)
    manifest={'version':spec['version'],'created_at_utc':datetime.now(timezone.utc).isoformat(),'training_seasons':sorted(d.season.unique().tolist()),'training_games':len(d),'training_last_game_date':str(d.game_date.max().date()),'bundle_sha256':sha(bundle),'spec_sha256':sha(ROOT/'spec.json'),'code_sha256':code_hashes(),'package_versions':versions,'source_sha256':{str(p):sha(p) for folder in ['runtime/nhl/prospective/training_games','runtime/nhl/prospective/training_team_stats'] for p in sorted(Path(folder).glob('*.csv'))},'status':'experimental watchlist; no candidate promoted'}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(ROOT/'requirements-frozen.txt').write_text('\n'.join(f'{k}=={v}' for k,v in versions.items())+'\n')
    return payload,manifest

def forecast_inputs(history,team_stats,target):
    target=dict(target);target.update(home_score=0,away_score=0,home_win=0,last_period_type='REG')
    d=pd.concat([history,pd.DataFrame([target])],ignore_index=True);d['season']=d.season.astype(str);d['game_date']=pd.to_datetime(d.game_date);d=d.sort_values(['season','game_date','game_id']).reset_index(drop=True)
    idx=d.index[d.game_id==int(target['game_id'])]
    if len(idx)!=1:raise ValueError('Forecast game already present in completed history')
    placeholders=pd.DataFrame([{'gameId':int(target['game_id']),'teamId':int(team),'gameDate':pd.Timestamp(target['game_date']),'season':str(target['season']),**{c:np.nan for c in adv.RAW}} for team in [target['home_id'],target['away_id']]])
    # Filter stats to completed history before appending the unobserved placeholder.
    t=pd.concat([team_stats[team_stats.gameId.isin(history.game_id)],placeholders],ignore_index=True)
    x,_=adv.attach(d,base.build_features(d),t,20);rx,_=adv.attach(d,strength_features(d),t,20)
    return x.loc[idx],rx.loc[idx]

def append_prediction(rows,new,now):
    if pd.Timestamp(new['start_time_utc'])<=pd.Timestamp(now):return False
    if any(str(r['candidate'])==str(new['candidate']) and int(r['game_id'])==int(new['game_id']) for r in rows):return False
    rows.append(new);return True

def current_stats(completed):
    from download_team_game_stats import fetch
    if completed.empty:return pd.DataFrame()
    root=Path('runtime/nhl/prospective/current_team_stats');root.mkdir(parents=True,exist_ok=True)
    for report in ['summary','powerplay','penaltykill']:
        pd.DataFrame(fetch(report,'20262027')).to_csv(root/f'{report}_20262027.csv',index=False)
    t=adv.load_team_stats(root);return t[t.gameId.isin(completed.game_id)].copy()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    training=base.load('runtime/nhl/prospective/training_games');stats=adv.load_team_stats('runtime/nhl/prospective/training_team_stats')
    payload,manifest=freeze_if_needed(training,stats)
    raw=pd.read_csv('runtime/nhl/prospective/current_games/nhl_games_20262027.csv',dtype={'season':str});raw.game_date=pd.to_datetime(raw.game_date);raw['start_time_utc']=pd.to_datetime(raw.start_time_utc,utc=True)
    asof=datetime.now(timezone.utc)
    complete=raw[raw.game_state.isin(['OFF','FINAL']) & raw.start_time_utc.le(asof) & raw.home_score.notna() & raw.away_score.notna()].copy();complete['home_win']=(complete.home_score>complete.away_score).astype(int)
    hist=pd.concat([training,complete],ignore_index=True).sort_values(['season','game_date','game_id']).reset_index(drop=True)
    ct=current_stats(complete);all_stats=pd.concat([stats,ct],ignore_index=True) if not ct.empty else stats
    path=OUT/'prediction_ledger.csv';rows=pd.read_csv(path).to_dict('records') if path.exists() else []
    completed={int(r.game_id):r for _,r in complete.iterrows()}
    for r in rows:
        if int(r['game_id']) in completed and (pd.isna(r.get('settled_at_utc')) or not r.get('settled_at_utc')):
            actual=completed[int(r['game_id'])]
            valid=pd.Timestamp(r['created_at_utc'])<pd.Timestamp(r['start_time_utc']) and pd.Timestamp(r['created_at_utc'])<actual.start_time_utc
            r['status']='settled' if valid else 'invalid_timing';r['actual_home_win']=int(actual.home_win) if valid else np.nan;r['settled_at_utc']=asof.isoformat()
    upcoming=raw[raw.game_state.isin(['FUT','PRE']) & raw.start_time_utc.gt(asof) & raw.start_time_utc.le(pd.Timestamp(asof)+pd.Timedelta(hours=36))].sort_values('start_time_utc')
    created=0
    for _,target in upcoming.iterrows():
        if all(any(int(r['game_id'])==int(target.game_id) and r['candidate']==name for r in rows) for name in payload['spec']['candidates']):continue
        x,rx=forecast_inputs(hist,all_stats,target.to_dict());features=payload['features']
        reference=float(payload['reference'].predict_proba(x[features])[0,1]);decay=float(payload['decay'].predict_proba(x[features])[0,1]);rp=payload['regulation'].predict_proba(rx[features])[0];classes=list(payload['regulation'].named_steps['model'].classes_);regulation=float(rp[classes.index(2)]+.5*rp[classes.index(1)])
        for name,p in [('reference_control',reference),('decay2_logistic',decay),('linear_regulation_blend',.5*reference+.5*regulation)]:
            now=datetime.now(timezone.utc);record={'game_id':int(target.game_id),'season':str(target.season),'game_date':str(target.game_date.date()),'start_time_utc':target.start_time_utc.isoformat(),'home_team':target.home_team,'away_team':target.away_team,'candidate':name,'home_win_prob':p,'created_at_utc':now.isoformat(),'data_snapshot_at_utc':asof.isoformat(),'bundle_sha256':manifest['bundle_sha256'],'spec_sha256':manifest['spec_sha256'],'status':'pending','actual_home_win':np.nan,'settled_at_utc':None}
            created+=int(append_prediction(rows,record,now))
    columns=['game_id','season','game_date','start_time_utc','home_team','away_team','candidate','home_win_prob','created_at_utc','data_snapshot_at_utc','bundle_sha256','spec_sha256','status','actual_home_win','settled_at_utc']
    pd.DataFrame(rows,columns=columns).to_csv(path,index=False)
    summary={'version':payload['spec']['version'],'as_of_utc':asof.isoformat(),'new_prediction_rows':created,'total_prediction_rows':len(rows),'pending':sum(r['status']=='pending' for r in rows),'settled':sum(r['status']=='settled' for r in rows),'invalid_timing':sum(r['status']=='invalid_timing' for r in rows),'status':'research_only_not_promoted','historical_gate_passed':False,'weights_frozen':True,'metrics':[]}
    for name in payload['spec']['candidates']:
        valid=[r for r in rows if r['candidate']==name and r['status']=='settled']
        if valid:
            y=np.array([r['actual_home_win'] for r in valid]);p=np.array([r['home_win_prob'] for r in valid]);summary['metrics'].append({'candidate':name,'games':len(valid),'accuracy':float(((p>=.5)==y).mean()),'brier':float(((p-y)**2).mean())})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
