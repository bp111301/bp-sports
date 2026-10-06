"""Frozen goalie experiment; three atomic predictions at the same pregame cutoff."""
from collections import Counter
from datetime import datetime,timezone,timedelta
import importlib.metadata
import json,sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

NHL=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(NHL),str(NHL/'prospective'),str(NHL/'goalie_capture')]
from experiment_goalies import base,adv,model,load_goalies
from experiment_goalies_weighted import weighted_features
import build_ledger as control
import collect as capture

ROOT=Path('model/nhl/goalie_experiment');OUT=Path('data/nhl/goalie_experiment')
FEATURE='weighted_goalie_probable_diff'
def code_hashes():
    files=[NHL/'backtest_baseline.py',NHL/'experiment_team_stats.py',NHL/'experiment_goalies.py',NHL/'experiment_goalies_weighted.py',NHL/'prospective/build_ledger.py',NHL/'goalie_capture/collect.py',NHL/'goalie_capture/probe_source.py',Path(__file__)]
    return {str(p.relative_to(NHL.parent.parent)):control.sha(p) for p in files}

def quality(pid,g,date):
    valid=g[(g.playerId==pid) & g.gameDate.lt(date)].copy()
    valid=valid[valid.shotsAgainst.gt(0) & valid.saves.ge(0) & valid.saves.le(valid.shotsAgainst)].sort_values(['gameDate','gameId']).tail(20)
    valid=valid[(date-valid.gameDate).dt.days<=365]
    return float((valid.saves.sum()+300*.905)/(valid.shotsAgainst.sum()+300))

def inferred_quality(team,season,g,date):
    starts=g[(g.teamAbbrev==team) & (g.season==str(season)) & g.gameDate.lt(date) & g.gamesStarted.gt(0)].sort_values(['gameDate','gameId']).tail(10)
    if starts.empty:return .905
    ids=starts.playerId.astype(int).tolist();counts=Counter(ids);best=max(counts.values());pid=next(p for p in reversed(ids) if counts[p]==best)
    return quality(pid,g,date)

def goalie_inputs(g,target,reports):
    date=pd.Timestamp(target['game_date']).normalize()
    inferred=inferred_quality(target['home_team'],target['season'],g,date)-inferred_quality(target['away_team'],target['season'],g,date)
    confirmed=quality(int(reports['home']['nhl_goalie_id']),g,date)-quality(int(reports['away']['nhl_goalie_id']),g,date)
    return inferred,confirmed

def normalize_goalies(g,history):
    g=g[g.gameId.isin(history.game_id)].copy()
    g['gameDate']=pd.to_datetime(g.gameDate).dt.normalize();g['season']=g.season.astype(str)
    for col in ['playerId','shotsAgainst','saves','gamesStarted']:
        g[col]=pd.to_numeric(g[col],errors='coerce')
    if g.duplicated(['gameId','playerId']).any():raise ValueError('Duplicate goalie appearance')
    g=g.dropna(subset=['playerId','gameDate'])
    return g

def freeze_if_needed():
    spec=json.loads((ROOT/'spec.json').read_text());bundle=ROOT/'frozen_bundle.joblib'
    expected={'goalie_feature':FEATURE,'goalie_history_appearances':20,'goalie_history_max_days':365,'prior_save_pct':.905,'prior_shots':300,'team_start_history':10,'logistic_C':.5,'prediction_window_minutes':60,'require_both_confirmed':True,'first_formal_review_paired_games':500,'automatic_promotion':False}
    if any(spec.get(k)!=v for k,v in expected.items()):raise ValueError('Unsupported experiment specification')
    versions={p:importlib.metadata.version(p) for p in control.PACKAGES}
    if bundle.exists():
        manifest=json.loads((ROOT/'manifest.json').read_text())
        if manifest['bundle_sha256']!=control.sha(bundle) or manifest['spec_sha256']!=control.sha(ROOT/'spec.json') or manifest['code_sha256']!=code_hashes() or manifest['package_versions']!=versions or manifest['reference_bundle_sha256']!=control.sha(control.ROOT/'watchlist.joblib'):raise ValueError('Frozen goalie experiment identity changed; do not refit')
        return joblib.load(bundle),manifest
    d=base.load('runtime/nhl/prospective/training_games');t=adv.load_team_stats('runtime/nhl/prospective/training_team_stats');g=normalize_goalies(load_goalies('runtime/nhl/goalie_experiment/training_goalies'),d)
    if d.season.max()!=spec['training_last_season'] or (d.season>spec['training_last_season']).any():raise ValueError('Training boundary violation')
    reference,reference_manifest=control.freeze_if_needed(d,t)
    x,af=adv.attach(d,base.build_features(d),t,20);x=x.join(weighted_features(d,g)[[FEATURE]])
    features=base.FEATURES+af+[FEATURE];goalie_model=model(features).fit(x[features],d.home_win)
    # Preserve fixed training inputs so recurring jobs do not re-download/refit history.
    keep=['gameId','teamId','gameDate','season']+adv.RAW
    payload={'spec':spec,'features':features,'model':goalie_model,'reference':reference['reference'],'reference_features':reference['features'],'training_games':d,'training_team_stats':t[keep],'training_goalies':g[['gameId','teamAbbrev','playerId','gameDate','season','shotsAgainst','saves','gamesStarted']]}
    joblib.dump(payload,bundle,compress=3)
    manifest={'version':spec['version'],'created_at_utc':datetime.now(timezone.utc).isoformat(),'training_seasons':sorted(d.season.unique().tolist()),'training_games':len(d),'training_last_game_date':str(d.game_date.max().date()),'bundle_sha256':control.sha(bundle),'spec_sha256':control.sha(ROOT/'spec.json'),'reference_bundle_sha256':reference_manifest['bundle_sha256'],'code_sha256':code_hashes(),'package_versions':versions,'training_input_sha256':{str(p):control.sha(p) for folder in ['runtime/nhl/prospective/training_games','runtime/nhl/prospective/training_team_stats','runtime/nhl/goalie_experiment/training_goalies'] for p in sorted(Path(folder).glob('*.csv'))},'status':'research_only_not_promoted'}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return payload,manifest

def append_pair(rows,record,now):
    start=pd.Timestamp(record['start_time_utc']);created=pd.Timestamp(record['created_at_utc']);cutoff=pd.Timestamp(record['input_cutoff_utc'])
    if not cutoff<=created<=pd.Timestamp(now)<start or start-created>pd.Timedelta(minutes=60):return False
    if any(int(r['game_id'])==int(record['game_id']) for r in rows):return False
    if set(record['probabilities'])!={'team_control','inferred_goalie','confirmed_goalie'}:raise ValueError('Incomplete pair')
    if any(not np.isfinite(p) or not 0<=p<=1 for p in record['probabilities'].values()):raise ValueError('Invalid probability')
    for side in ['home','away']:
        r=record['goalie_observations'][side]
        if r['confirmed_eligible'] is not True or r['status']!='Confirmed' or r.get('report_timestamp_valid') is not True or r.get('nhl_goalie_id') is None or int(r['game_id'])!=int(record['game_id']) or r['team']!=record[side+'_team'] or pd.Timestamp(r['captured_at_utc'])>cutoff or pd.Timestamp(r['start_time_utc'])!=start:return False
    rows.append(record);return True

def settle(rows,complete,now):
    bygame={int(r.game_id):r for _,r in complete.iterrows()}
    for r in rows:
        if r['status']!='pending' or int(r['game_id']) not in bygame:continue
        actual=bygame[int(r['game_id'])]
        if pd.Timestamp(r['created_at_utc'])<min(pd.Timestamp(r['start_time_utc']),actual.start_time_utc):
            r['status']='settled';r['actual_home_win']=int(actual.home_win)
        else:r['status']='invalid_timing';r['actual_home_win']=None
        r['settled_at_utc']=now.isoformat()

def summary(rows,coverage,now):
    settled=[r for r in rows if r['status']=='settled'];metrics=[]
    for candidate in ['team_control','inferred_goalie','confirmed_goalie']:
        if not settled:continue
        p=np.array([r['probabilities'][candidate] for r in settled]);y=np.array([r['actual_home_win'] for r in settled]);metrics.append({'candidate':candidate,**adv.metrics(y,p)})
    result={'as_of_utc':now.isoformat(),'status':'research_only_not_promoted','weights_frozen':True,'paired_games':len(rows),'settled_paired_games':len(settled),'pending_paired_games':sum(r['status']=='pending' for r in rows),'invalid_timing':sum(r['status']=='invalid_timing' for r in rows),'coverage':coverage,'metrics':metrics,'first_formal_review_paired_games':500,'automatic_promotion':False}
    if metrics:
        lookup={m['candidate']:m for m in metrics};result['confirmed_minus_control']={c:{k:lookup['confirmed_goalie'][k]-lookup[c][k] for k in ['accuracy','brier','log_loss']} for c in ['team_control','inferred_goalie']}
    return result

def current_games():
    # A single team schedule does not contain all clubs, so use the league season
    # downloader for completed feature history; it is refreshed per CI workspace.
    return pd.read_csv('runtime/nhl/prospective/current_games/nhl_games_20262027.csv',dtype={'season':str})

def main():
    OUT.mkdir(parents=True,exist_ok=True);payload,manifest=freeze_if_needed();now=datetime.now(timezone.utc)
    path=OUT/'paired_ledger.jsonl';rows=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    raw=current_games();raw['game_date']=pd.to_datetime(raw.game_date);raw['start_time_utc']=pd.to_datetime(raw.start_time_utc,utc=True)
    complete=raw[raw.game_state.isin(['OFF','FINAL']) & raw.start_time_utc.le(now) & raw.home_score.notna() & raw.away_score.notna()].copy();complete['home_win']=(complete.home_score>complete.away_score).astype(int)
    settle(rows,complete,now)
    future=raw[raw.game_state.isin(['FUT','PRE']) & raw.start_time_utc.gt(now) & raw.start_time_utc.le(pd.Timestamp(now)+pd.Timedelta(minutes=60))].sort_values('start_time_utc')
    observations=[json.loads(line) for line in Path('data/nhl/goalie_capture/observations.jsonl').read_text().splitlines()]
    eligible=[];coverage=[]
    for _,target in future.iterrows():
        if any(int(r['game_id'])==int(target.game_id) for r in rows):continue
        reports={side:capture.available_at(observations,int(target.game_id),side,now) for side in ['home','away']}
        if not all(reports.values()):coverage.append({'game_id':int(target.game_id),'status':'missing_both_eligible_confirmations'});continue
        if any(pd.Timestamp(r['start_time_utc'])!=target.start_time_utc for r in reports.values()):coverage.append({'game_id':int(target.game_id),'status':'changed_start_time_requires_new_report_capture'});continue
        eligible.append((target,reports))
    if eligible:
        history=pd.concat([payload['training_games'],complete],ignore_index=True).sort_values(['season','game_date','game_id']).reset_index(drop=True)
        ct=control.current_stats(complete);stats=pd.concat([payload['training_team_stats'],ct],ignore_index=True) if not ct.empty else payload['training_team_stats']
        from download_goalie_game_stats import fetch
        cg=pd.DataFrame(fetch('20262027'));cg['season']='20262027';g=normalize_goalies(pd.concat([payload['training_goalies'],cg],ignore_index=True),history)
        cutoff=datetime.now(timezone.utc)
        for target,_ in eligible:
            reports={side:capture.available_at(observations,int(target.game_id),side,cutoff) for side in ['home','away']}
            if not all(reports.values()):continue
            x,_=control.forecast_inputs(history,stats,target.to_dict());iq,cq=goalie_inputs(g,target.to_dict(),reports);x[FEATURE]=iq
            pteam=float(payload['reference'].predict_proba(x[payload['reference_features']])[0,1]);pi=float(payload['model'].predict_proba(x[payload['features']])[0,1]);x[FEATURE]=cq;pc=float(payload['model'].predict_proba(x[payload['features']])[0,1])
            created=datetime.now(timezone.utc);snapshot={'input_cutoff_utc':cutoff.isoformat(),'team_features':{k:None if pd.isna(v) else float(v) for k,v in x[payload['reference_features']].iloc[0].items()},'inferred_goalie_diff':iq,'confirmed_goalie_diff':cq,'completed_history_sha256':capture.digest(history.to_json(date_format='iso',orient='split')),'goalie_history_sha256':capture.digest(g.to_json(date_format='iso',orient='split'))}
            record={'game_id':int(target.game_id),'season':'20262027','home_team':str(target.home_team),'away_team':str(target.away_team),'start_time_utc':target.start_time_utc.isoformat(),'created_at_utc':created.isoformat(),'input_cutoff_utc':cutoff.isoformat(),'probabilities':{'team_control':pteam,'inferred_goalie':pi,'confirmed_goalie':pc},'goalie_observations':reports,'goalie_observation_ledger_sha256':control.sha('data/nhl/goalie_capture/observations.jsonl'),'feature_snapshot':snapshot,'bundle_sha256':manifest['bundle_sha256'],'reference_bundle_sha256':manifest['reference_bundle_sha256'],'spec_sha256':manifest['spec_sha256'],'status':'pending','actual_home_win':None,'settled_at_utc':None}
            added=append_pair(rows,record,created);coverage.append({'game_id':int(target.game_id),'status':'paired_prediction_recorded' if added else 'timing_or_identity_gate_rejected'})
    path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    result=summary(rows,coverage,datetime.now(timezone.utc));result['games_in_current_prediction_window']=len(future);result['newly_eligible_games']=len(eligible)
    (OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
