"""Capture immutable paired forward forecasts; never write the public V1 feed."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import develop as v1
from evaluate_holdout import predict_bundle
from prospective import targets, grade, confirmed
from run import VARIANTS, prospective_extra_features
from shadow_data import load_history, load_season


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def in_capture_window(upcoming,now,hours=24):
    return [g for g in upcoming if now<g['start']<=now+pd.Timedelta(hours=hours)]


def forecast_frame(history,upcoming,players,now):
    if not upcoming:return pd.DataFrame(columns=VARIANTS['combined'])
    history=[g for g in history if g['start']<now and not g.get('forecast')]
    ids={g['game_id'] for g in upcoming}
    base=v1.build_features(history+upcoming)
    extra=prospective_extra_features(history,upcoming,players,now)
    frame=base.merge(extra,on='game_id',validate='one_to_one')
    return frame[frame.game_id.isin(ids)].sort_values(['start','game_id']).copy()


def validate_pairs(ledger,identities):
    ids=set()
    for pair in ledger:
        if pair['game_id'] in ids:raise ValueError('Duplicate paired game')
        ids.add(pair['game_id'])
        if pair['identities']!=identities:raise ValueError('Frozen paired model identity changed')
        control,challenger=pair['control'],pair['challenger']
        for key in ['game_id','season','season_type','home_team_id','away_team_id','home_team',
                    'away_team','neutral_site','start_time_utc','created_at_utc']:
            if control[key]!=challenger[key]:raise ValueError('Pair capture context differs')
        if control['game_id']!=pair['game_id'] or control['season']!=2027 or control['season_type']!=2:
            raise ValueError('Unexpected paired season or identity')
        if pd.Timestamp(control['created_at_utc'])>=pd.Timestamp(control['start_time_utc']):
            raise ValueError('Post-tipoff paired capture')
        if pd.Timestamp(control['start_time_utc'])-pd.Timestamp(control['created_at_utc'])>pd.Timedelta(hours=24):
            raise ValueError('Saved pair outside 24-hour capture window')
        for name,row in [('control',control),('challenger',challenger)]:
            if row['status'] not in ('pending','settled'):raise ValueError('Invalid paired status')
            if row['bundle_sha256']!=identities[name]:raise ValueError('Bundle identity mismatch')
            expected_features=v1.FEATURES if name=='control' else VARIANTS['combined']
            if set(row['features'])!=set(expected_features):raise ValueError('Saved feature schema mismatch')
            if not np.isfinite(row['home_win_prob']) or not 0<=row['home_win_prob']<=1:
                raise ValueError('Invalid saved probability')
            if not all(np.isfinite(value) for value in row['features'].values()):
                raise ValueError('Nonfinite saved features')
        if (control['status']=='settled') != (challenger['status']=='settled'):
            raise ValueError('One-sided paired settlement')
        if control['status']=='settled' and any(control[k]!=challenger[k] for k in ['actual_home_win','home_score','away_score']):
            raise ValueError('Paired final outcomes differ')


def capture_pairs(ledger,frame,control,challenger,identities,now,schedule_sha):
    validate_pairs(ledger,identities)
    result=list(ledger);saved={p['game_id'] for p in ledger}
    probabilities={name:predict_bundle(bundle,frame) if len(frame) else []
                   for name,bundle in [('control',control),('challenger',challenger)]}
    for i,r in enumerate(frame.to_dict('records')):
        if r['start']<=now:raise ValueError('Post-tipoff capture rejected')
        if r['start']>now+pd.Timedelta(hours=24):raise ValueError('Outside 24-hour capture window')
        if r['game_id'] in saved:continue
        pair=dict(game_id=r['game_id'],identities=identities.copy(),
                  control_scope='paired replay of frozen V1; separate from public V1 snapshots',
                  roster_context=dict(home_known=bool(r['home_rotation_known']),away_known=bool(r['away_rotation_known']),
                                      fallback='Unknown until earlier eligible player appearances clear the UTC-day embargo'),
                  feature_state_as_of_utc=now.isoformat())
        for name,bundle in [('control',control),('challenger',challenger)]:
            p=float(probabilities[name][i])
            if not np.isfinite(p) or not 0<=p<=1:raise ValueError('Invalid paired probability')
            pair[name]=dict(prediction_id=bundle['version']+':'+r['game_id'],model_version=bundle['version'],
                           bundle_sha256=identities[name],game_id=r['game_id'],season=2027,season_type=2,
                           home_team_id=r['home_id'],away_team_id=r['away_id'],home_team=r['home'],away_team=r['away'],
                           neutral_site=bool(r['neutral']),start_time_utc=r['start'].isoformat(),created_at_utc=now.isoformat(),
                           home_win_prob=p,predicted_winner=r['home'] if p>=.5 else r['away'],status='pending',
                           market_used_for_pick=False,source_schedule_sha256=schedule_sha,
                           features={k:float(r[k]) for k in bundle['features']})
        result.append(pair);saved.add(r['game_id'])
    validate_pairs(result,identities)
    return result


def grade_pairs(ledger,schedule,now,identities):
    validate_pairs(ledger,identities)
    controls,ci=grade([p['control'] for p in ledger],schedule,now)
    challengers,si=grade([p['challenger'] for p in ledger],schedule,now)
    result=[{**p,'control':c,'challenger':s} for p,c,s in zip(ledger,controls,challengers)]
    validate_pairs(result,identities)
    return result,[dict(model='control',**issue) for issue in ci]+[dict(model='challenger',**issue) for issue in si]


def paired_summary(ledger):
    settled=[p for p in ledger if p['control']['status']=='settled' and p['challenger']['status']=='settled']
    n=len(settled);result=dict(saved_pairs=len(ledger),settled_pairs=n,pending_pairs=len(ledger)-n)
    for name in ['control','challenger']:
        rows=[p[name] for p in settled];wins=sum(r['correct'] for r in rows)
        result[name]=dict(wins=wins,losses=n-wins,accuracy=wins/n if n else None,
                          brier=sum(r['brier'] for r in rows)/n if n else None,
                          log_loss=sum(r['log_loss'] for r in rows)/n if n else None)
    result['challenger_minus_control']={k:result['challenger'][k]-result['control'][k] if n else None
                                        for k in ['accuracy','brier','log_loss']}
    result['pick_disagreements']=sum(p['control']['predicted_winner']!=p['challenger']['predicted_winner'] for p in ledger)
    result['roster_unknown_pairs']=sum(not p['roster_context']['home_known'] or not p['roster_context']['away_known'] for p in ledger)
    return result


def coverage_by_day(schedule,eligible,now):
    days={};eligible_ids={g['game_id'] for g in eligible}
    for s in schedule.to_dict('records'):
        start=pd.to_datetime(s['date'],utc=True,errors='coerce')
        if s['season']!=2027 or s['season_type']!=2 or pd.isna(start) or not now<start<=now+pd.Timedelta(days=30):continue
        # Unconfirmed source timestamps may be date placeholders, not actual CT tipoffs.
        day=start.tz_convert('America/Chicago').strftime('%Y-%m-%d') if confirmed(s.get('time_valid',False)) else 'Unconfirmed source date/time'
        count=days.setdefault(day,dict(source_games=0,eligible=0,unconfirmed_tipoff=0))
        count['source_games']+=1
        count['eligible']+=v1.ident(s['game_id']) in eligible_ids
        count['unconfirmed_tipoff']+=not confirmed(s.get('time_valid',False))
    return days


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',default='runtime/cbb');parser.add_argument('--output',default='data/cbb/shadow');parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    if Path(args.output).resolve()==Path('data/cbb/prospective').resolve():raise ValueError('Refuse public V1 output path')
    root=Path(__file__).parent;cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
    lock_path=root/'SHADOW_LOCK.json';bundle_path=root/'results/shadow_bundle.json'
    lock=json.loads(lock_path.read_text())
    if lock['capture_window_hours']!=24:raise ValueError('Unexpected paired capture window')
    control_path=root.parent/'results/candidate_bundle.json'
    bundle=json.loads(bundle_path.read_text());control=json.loads(control_path.read_text())
    identities=dict(control=digest(control_path),challenger=digest(bundle_path),protocol=digest(lock_path))
    if bundle['shadow_lock_sha256']!=identities['protocol'] or bundle['status']!='shadow_only_no_public_promotion':
        raise ValueError('Frozen shadow protocol mismatch')
    if bundle['features']!=VARIANTS['combined'] or control['features']!=v1.FEATURES:
        raise ValueError('Frozen feature schema mismatch')
    expected_control=bundle.get('control_bundle_sha256')
    if expected_control!=identities['control']:raise ValueError('Frozen V1 control changed')
    schedule,source=v1.fetch(2027,'schedule',cache,refresh=True)
    now=pd.Timestamp.now(tz='UTC');upcoming,coverage,excluded=targets(schedule,now)
    active=in_capture_window(upcoming,now)
    needed=upcoming if args.preflight else active
    audits=[]
    if needed:
        history,players,audits=load_history(cache,range(2020,2027))
        if ((schedule.season_type==2)&schedule.status_type_name.eq('STATUS_FINAL')).any():
            batch,rotation,audit=load_season(2027,cache,refresh=True)
            history+=batch;players.update(rotation);audits.append(audit)
        frame=forecast_frame(history,needed,players,now)
    else:frame=pd.DataFrame(columns=VARIANTS['combined'])
    now=pd.Timestamp.now(tz='UTC')
    if len(frame):frame=frame[frame.start.gt(now)]
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True);ledger_path=output/'paired_ledger.json'
    if args.preflight:
        rows=[]
        cp=predict_bundle(control,frame) if len(frame) else []
        sp=predict_bundle(bundle,frame) if len(frame) else []
        for r,c,s in zip(frame.to_dict('records'),cp,sp):
            if not np.isfinite(c) or not np.isfinite(s) or not 0<=c<=1 or not 0<=s<=1:raise ValueError('Invalid readiness inference')
            rows.append(dict(game_id=r['game_id'],start_time_utc=r['start'].isoformat(),home=r['home'],away=r['away'],
                             control_home_probability=float(c),challenger_home_probability=float(s),
                             home_rotation_known=bool(r['home_rotation_known']),away_rotation_known=bool(r['away_rotation_known'])))
        preview=dict(kind='non_record_readiness_preview',not_for_grading=True,checked_at_utc=now.isoformat(),
                     identities=identities,source=source,games=rows,history_sources=audits)
        (output/'readiness_preview.json').write_text(json.dumps(preview,indent=2,allow_nan=False)+'\n')
    if len(frame):frame=frame[frame.start.le(now+pd.Timedelta(hours=24))]
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    ledger=capture_pairs(ledger,frame,control,bundle,identities,now,source['sha256'])
    ledger,issues=grade_pairs(ledger,schedule,now,identities);totals=paired_summary(ledger)
    dashboard=dict(status='shadow_only_not_public',updated_at_utc=now.isoformat(),identities=identities,
                   capture_window_hours=24,eligible_future_games=len(upcoming),within_capture_window=len(frame),
                   summary=totals,coverage=coverage,excluded=excluded,coverage_by_day=coverage_by_day(schedule,upcoming,now),
                   source=source,history_sources=audits,grading_issues=issues,
                   limitations=['Source schedule coverage is partial; unconfirmed tipoffs are excluded',
                                'Continuity uses observed earlier appearances; opening-night roster and injury availability unknown',
                                'Paired V1 control is separate from original public V1 snapshots',
                                'No automatic promotion; historical 2026 evaluation unchanged'],predictions=ledger)
    for filename,value in [('paired_ledger.json',ledger),('dashboard.json',dashboard),('summary.json',{**totals,'updated_at_utc':now.isoformat(),'identities':identities,'grading_issues':issues})]:
        target=output/filename;temp=target.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temp.replace(target)
    print(json.dumps({k:dashboard[k] for k in ['status','summary','coverage','excluded','coverage_by_day','grading_issues']},indent=2))


if __name__=='__main__':main()
