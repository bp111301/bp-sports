"""Read fixed CBB weights, archive pregame forecasts, grade verified finals."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from develop import FEATURES, build_features, fetch, ident, season_games
from evaluate_holdout import predict_bundle


def confirmed(value):return str(value).lower() in ('true','1')


def targets(schedule, now, horizon_days=30):
    picked=[];excluded=Counter();coverage=Counter()
    for s in schedule.to_dict('records'):
        start=pd.to_datetime(s['date'],utc=True,errors='coerce')
        if pd.isna(start) or start<=now or start>now+pd.Timedelta(days=horizon_days):continue
        coverage['source_games_in_horizon']+=1
        reason=None
        if s['season']!=2027 or s['season_type']!=2:reason='not_target_regular_season'
        elif s['status_type_name']!='STATUS_SCHEDULED':reason='not_scheduled'
        elif not confirmed(s.get('time_valid',False)):reason='tipoff_time_unconfirmed'
        elif pd.isna(s['neutral_site']):reason='venue_unknown'
        elif str(s.get('away_non_div1_team')).lower()=='true':reason='non_division_i'
        elif pd.isna(s['home_conference_id']) or pd.isna(s['away_conference_id']):reason='division_or_conference_unknown'
        if reason:excluded[reason]+=1;continue
        picked.append(dict(game_id=ident(s['game_id']),season=2027,start=start,day=start.floor('D'),
                           home_id=ident(s['home_id']),away_id=ident(s['away_id']),
                           home=s['home_display_name'],away=s['away_display_name'],neutral=bool(s['neutral_site']),
                           forecast=True,y=np.nan,home_score=np.nan,away_score=np.nan,values={}))
    if len({g['game_id'] for g in picked})!=len(picked):raise ValueError('Duplicate schedule IDs')
    return picked,dict(coverage),dict(excluded)


def forecast_features(history, upcoming, now):
    # A current source cannot be used to pretend a past historical snapshot existed.
    history=[g for g in history if g['start']<now and g['season']<=2027]
    if not upcoming:return pd.DataFrame(columns=FEATURES)
    frame=build_features(history+upcoming)
    return frame[frame.game_id.isin({g['game_id'] for g in upcoming})].copy()


def capture(ledger, frame, bundle, bundle_sha, now, schedule_sha):
    keys={(r['bundle_sha256'],r['game_id']) for r in ledger}
    result=list(ledger);probabilities=predict_bundle(bundle,frame) if len(frame) else []
    for r,p in zip(frame.to_dict('records'),probabilities):
        if r['start']<=now:raise ValueError('Post-tipoff forecast rejected')
        if (bundle_sha,r['game_id']) in keys:continue
        if not np.isfinite(p) or not 0<=p<=1:raise ValueError('Invalid probability')
        result.append(dict(prediction_id=bundle['version']+':'+r['game_id'],model_version=bundle['version'],
                           bundle_sha256=bundle_sha,game_id=r['game_id'],season=2027,season_type=2,
                           home_team_id=r['home_id'],away_team_id=r['away_id'],home_team=r['home'],away_team=r['away'],
                           neutral_site=bool(r['neutral']),start_time_utc=r['start'].isoformat(),created_at_utc=now.isoformat(),
                           home_win_prob=float(p),predicted_winner=r['home'] if p>=.5 else r['away'],
                           status='pending',market_used_for_pick=False,source_schedule_sha256=schedule_sha,
                           forecast_stage='early_research_prior',features={k:float(r[k]) for k in FEATURES}))
        keys.add((bundle_sha,r['game_id']))
    return result


def grade(ledger, schedule, now):
    if schedule.game_id.duplicated().any():raise ValueError('Duplicate result game IDs')
    indexed={ident(s['game_id']):s for s in schedule.to_dict('records')}
    result=[];issues=[]
    for original in ledger:
        r=dict(original)
        if r['status']=='settled':result.append(r);continue
        s=indexed.get(r['game_id'])
        if s is None:result.append(r);continue
        start=pd.to_datetime(s['date'],utc=True,errors='coerce')
        if s['season']!=r['season'] or s['season_type']!=2 or ident(s['home_id'])!=r['home_team_id'] or ident(s['away_id'])!=r['away_team_id']:
            issues.append({'game_id':r['game_id'],'reason':'result_identity_mismatch'});result.append(r);continue
        if s['status_type_name']!='STATUS_FINAL' or not confirmed(s['status_type_completed']):result.append(r);continue
        if not confirmed(s.get('time_valid',False)) or pd.isna(start) or pd.Timestamp(r['created_at_utc'])>=start or start>now:
            issues.append({'game_id':r['game_id'],'reason':'final_tipoff_not_verified_after_capture'});result.append(r);continue
        h=pd.to_numeric(s['home_score'],errors='coerce');a=pd.to_numeric(s['away_score'],errors='coerce')
        if pd.isna(h) or pd.isna(a) or h==a or min(h,a)<0 or not float(h).is_integer() or not float(a).is_integer():
            issues.append({'game_id':r['game_id'],'reason':'invalid_final_scores'});result.append(r);continue
        y=int(h>a);p=r['home_win_prob'];q=min(1-1e-15,max(1e-15,p))
        r.update(status='settled',actual_home_win=y,home_score=int(h),away_score=int(a),
                 actual_winner=r['home_team'] if y else r['away_team'],correct=int((p>=.5)==bool(y)),
                 brier=float((p-y)**2),log_loss=float(-(y*np.log(q)+(1-y)*np.log(1-q))),
                 verified_start_time_utc=start.isoformat(),settled_at_utc=now.isoformat())
        result.append(r)
    return result,issues


def summary(ledger):
    settled=[r for r in ledger if r['status']=='settled'];n=len(settled);wins=sum(r['correct'] for r in settled)
    return dict(saved_games=len(ledger),settled_games=n,pending_games=len(ledger)-n,wins=wins,losses=n-wins,
                accuracy=wins/n if n else None,brier=sum(r['brier'] for r in settled)/n if n else None,
                log_loss=sum(r['log_loss'] for r in settled)/n if n else None)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',default='runtime/cbb');parser.add_argument('--output',default='data/cbb/prospective');parser.add_argument('--horizon-days',type=int,default=30);args=parser.parse_args()
    now=pd.Timestamp.now(tz='UTC');root=Path(__file__).parent;cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
    bundle_path=root/'results/candidate_bundle.json';raw=bundle_path.read_bytes();bundle=json.loads(raw);bundle_sha=hashlib.sha256(raw).hexdigest()
    report=json.loads((root/'results/holdout_2026.json').read_text())
    if bundle['status']!='passed_historical_gate_pending_live_validation' or not all(report['gate_checks'].values()):raise ValueError('Candidate did not pass historical gate')
    if bundle['evaluation_lock_sha256']!=hashlib.sha256((root/'EVALUATION_LOCK.json').read_bytes()).hexdigest():raise ValueError('Evaluation lock changed')
    schedule,source=fetch(2027,'schedule',cache,refresh=True)
    upcoming,coverage,excluded=targets(schedule,now,args.horizon_days)
    with ThreadPoolExecutor(max_workers=4) as pool:seasons=list(pool.map(lambda y:season_games(y,cache),range(2020,2027)))
    history=[g for games,_ in seasons for g in games]
    # Once the season begins, refresh current-season final boxes before state updates.
    if schedule.status_type_name.eq('STATUS_FINAL').any():
        fetch(2027,'box',cache,refresh=True)
        current,_=season_games(2027,cache);history+=current
    now=pd.Timestamp.now(tz='UTC')
    upcoming,coverage,excluded=targets(schedule,now,args.horizon_days)
    frame=forecast_features(history,upcoming,now)
    now=pd.Timestamp.now(tz='UTC')
    if len(frame):frame=frame[frame.start.gt(now)]
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True);path=output/'prediction_ledger.json'
    ledger=json.loads(path.read_text()) if path.exists() else []
    if len({(r['bundle_sha256'],r['game_id']) for r in ledger})!=len(ledger):raise ValueError('Duplicate archived forecasts')
    if any(r['bundle_sha256']!=bundle_sha for r in ledger):raise ValueError('Model identity changed')
    ledger=capture(ledger,frame,bundle,bundle_sha,now,source['sha256']);ledger,issues=grade(ledger,schedule,now)
    totals=summary(ledger)
    dashboard=dict(feed_status='research_preview',model_version=bundle['version'],bundle_sha256=bundle_sha,
                   updated_at_utc=now.isoformat(),coverage=coverage,excluded=excluded,grading_issues=issues,
                   summary=totals,predictions=ledger,source=source,history_sources=[audit['sources'] for _,audit in seasons],
                   limitations=['Early forecasts use prior-season state; no roster/transfer/injury inputs','Source schedule is incomplete; unconfirmed times and unknown eligibility are excluded','Historical accuracy is separate from this prospective record'])
    # Atomic local replacement; existing forecast identity/probabilities stay immutable.
    for file,value in [('prediction_ledger.json',ledger),('dashboard.json',dashboard),('summary.json',{**totals,'updated_at_utc':now.isoformat(),'bundle_sha256':bundle_sha,'grading_issues':issues})]:
        target=output/file;temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temporary.replace(target)
    print(json.dumps({'summary':totals,'coverage':coverage,'excluded':excluded,'grading_issues':issues},indent=2))


if __name__=='__main__':main()
