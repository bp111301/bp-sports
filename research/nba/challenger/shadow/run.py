"""Separate frozen NBA availability pairs; never writes public V1 data."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import sys
import joblib
import numpy as np
import pandas as pd
import requests

RESEARCH=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RESEARCH))
from injuries import cutoff_for,load_report,usable,contexts,code
from engine import report_candidates,impact_features,adjusted_probability,validate
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'data/nba/availability-shadow'
spec=importlib.util.spec_from_file_location('nba_v1_prospective',ROOT/'research/nba/prospective/run.py')
v1=importlib.util.module_from_spec(spec);spec.loader.exec_module(v1)


def digest(data):return hashlib.sha256(data).hexdigest()


def verify_models():
    frozen_path=ROOT/'model/nba/availability-shadow/frozen.json';raw=frozen_path.read_bytes()
    manifest=json.loads((frozen_path.parent/'manifest.json').read_text());frozen=json.loads(raw)
    if digest(raw)!=manifest['bundle_sha256']:raise ValueError('Frozen shadow bundle changed')
    if frozen['status']!='frozen_prospective_shadow_only' or frozen['season']!=2027:raise ValueError('Wrong shadow model')
    if digest((RESEARCH/'shadow/PROTOCOL.md').read_bytes())!=frozen['prospective_protocol_sha256']:raise ValueError('Prospective protocol changed')
    if digest((RESEARCH/'EXPERIMENT_LOCK.json').read_bytes())!=frozen['experiment_lock_sha256']:raise ValueError('Development lock changed')
    if frozen['fit']['last_training_season']!=2025 or frozen['reserved_season_2026_used_for_fit_or_selection']:raise ValueError('Invalid residual training boundary')
    original=v1.verify_frozen()
    if original['bundle_sha256']!=frozen['v1_bundle_sha256']:raise ValueError('V1 control differs from reviewed bundle')
    return frozen,manifest,joblib.load(ROOT/'model/nba/v1/frozen_bundle.joblib')


def player_state(history,need_current,receipts):
    accepted={r['game_id']:r for r in history.to_dict('records')};rows=[];ready=True
    expected={r['season']:r['sha256'] for r in json.loads((RESEARCH/'PLAYER_SOURCES.json').read_text())}
    for season in range(2020,2028):
        url=f'{v1.BASE}/espn_nba_player_boxscores/player_box_{season}.parquet'
        try:
            response=requests.get(url,timeout=(15,90))
            if season==2027 and response.status_code==404 and not need_current:
                receipts.append(dict(url=url,status=404,optional=True));continue
            response.raise_for_status();raw=response.content
            if season in expected and digest(raw)!=expected[season]:raise ValueError('Earlier player-source hash changed')
            receipts.append(dict(url=url,status=200,sha256=digest(raw),role='forward_player_state_only'))
            frame=pd.read_parquet(io.BytesIO(raw))
            if set(pd.to_numeric(frame.season).unique())!={season}:raise ValueError('Wrong player-source season')
            frame=frame[pd.to_numeric(frame.season_type)==2]
            if frame.duplicated(['game_id','athlete_id']).any():raise ValueError('Duplicate player identity')
            for r in frame.itertuples():
                gid=str(int(r.game_id));g=accepted.get(gid)
                if g is None:continue
                side='home' if str(int(r.team_id))==g['home_id'] else 'away';other='away' if side=='home' else 'home'
                if str(int(r.team_id))!=g[side+'_id'] or str(int(r.opponent_team_id))!=g[other+'_id']:raise ValueError('Player identity mismatch')
                if r.team_score!=g[side+'_score'] or r.opponent_team_score!=g[other+'_score']:raise ValueError('Player score reconciliation failed')
                if not np.isfinite(r.minutes) or r.minutes<=0:continue
                if r.minutes>80 or not np.isfinite(r.points):raise ValueError('Invalid prior player stats')
                rows.append(dict(game_id=gid,date=g['date'],athlete_id=str(int(r.athlete_id)),name=r.athlete_display_name,
                                 minutes=float(r.minutes),points=float(r.points)))
        except (requests.RequestException,ValueError) as error:
            ready=False;receipts.append(dict(url=url,status='unavailable',error=str(error)))
    return rows,ready


def report_for(game,cutoff,cache):
    receipts=[]
    for filename in report_candidates(cutoff):
        report=load_report(filename,cache)
        receipts.append({k:v for k,v in report.items() if k!='teams'})
        if usable(report,cutoff):
            home,away=contexts(game,report)
            return report,home,away,receipts
    return {},dict(known=False,players=[]),dict(known=False,players=[]),receipts


def record(predictions,results,adjusted_only=False):
    by_id={p['game_id']:p for p in predictions};rows=[r for r in results if not adjusted_only or not by_id[r['game_id']]['fallback']]
    empty=dict(games=0,correct=0,accuracy=None,brier=None,log_loss=None)
    return {label:v1.metrics([r['actual_home_win'] for r in rows],[by_id[r['game_id']][column] for r in rows]) if rows else empty
            for label,column in [('control','control_probability'),('candidate','candidate_probability')]}


def main():
    frozen,manifest,bundle=verify_models();OUT.mkdir(parents=True,exist_ok=True)
    predictions=v1.read_log(OUT/'predictions.jsonl');results=v1.read_log(OUT/'results.jsonl')
    validate(predictions,results,manifest['bundle_sha256'],frozen['v1_bundle_sha256'])
    fetched=datetime.now(timezone.utc);schedule,box,receipts=v1.fetch_sources(fetched,predictions,results)
    now=datetime.now(timezone.utc);new_results=v1.settle(predictions,results,schedule,now)
    results+=new_results;known={p['game_id'] for p in predictions};new=[];blocked=None;report_receipts=[]
    eligible=[r for r in schedule.to_dict('records') if v1.regular(r) and r['status_type_state']=='pre' and pd.Timestamp(r['date'])>now]
    eligible.sort(key=lambda r:str(r['date']))
    due=[r for r in eligible if str(int(r['game_id'])) not in known and cutoff_for(r['date'])<=now]
    readiness=[dict(game_id=str(int(r['game_id'])),home_team=r['home_abbreviation'],away_team=r['away_abbreviation'],
                    start_time_utc=pd.Timestamp(r['date']).isoformat(),capture_opens_utc=cutoff_for(r['date']).isoformat(),
                    status='already_saved' if str(int(r['game_id'])) in known else 'capture_window_open' if cutoff_for(r['date'])<=now else 'waiting_for_capture_window') for r in eligible[:10]]
    if due:
        try:
            history,_=v1.load_games(range(2016,2027)) # 2026 is forward state only, never residual fit/evaluation.
            box=v1.complete_current_boxes(schedule,box,receipts,OUT/'validated_team_boxes.jsonl')
            current=v1.current_history(schedule,box)
            if not current.empty:history=pd.concat([history,current],ignore_index=True)
            cache=ROOT/'runtime/nba/shadow-injuries';cache.mkdir(parents=True,exist_ok=True)
            player_cache={}
            for r in due:
                start=pd.Timestamp(r['date']);day=start.tz_convert('America/New_York').date().isoformat();cutoff=cutoff_for(start)
                prior=history[history.date<day]
                if day not in player_cache:player_cache[day]=player_state(prior,bool((prior.season==2027).any()),receipts)
                players,player_ready=player_cache[day]
                game=dict(date=day,start_time=start.isoformat(),home_team=code(r['home_abbreviation']),away_team=code(r['away_abbreviation']))
                report,home,away,report_audit=report_for(game,cutoff,cache);report_receipts+=report_audit
                both=bool(home['known'] and away['known'])
                captured=datetime.now(timezone.utc)
                if not both and captured<start-timedelta(minutes=15):continue
                if captured>=start:continue
                feature,history_cutoff=v1.forecast_features(history,r)
                control=float(bundle['models']['linear'].predict_proba(pd.DataFrame([feature])[v1.FEATURES])[0,1])
                availability,listed,matched=impact_features(home,away,players,day)
                fallback=not both or not player_ready or (listed>0 and matched/listed<.8)
                candidate=control if fallback else adjusted_probability(control,availability,frozen)
                reason='unknown_report' if not both else 'missing_player_state' if not player_ready else 'low_identity_coverage' if fallback else None
                captured=datetime.now(timezone.utc)
                if captured>=start:continue
                injury={k:v for k,v in report.items() if k!='teams'};injury.update(both_known=both)
                new.append(dict(game_id=str(int(r['game_id'])),season=2027,season_type=2,home_id=str(int(r['home_id'])),away_id=str(int(r['away_id'])),
                    home_team=r['home_abbreviation'],away_team=r['away_abbreviation'],start_time_utc=start.isoformat(),created_at_utc=captured.isoformat(),
                    history_cutoff=history_cutoff,availability_cutoff_utc=cutoff.isoformat(),shadow_sha256=manifest['bundle_sha256'],
                    v1_bundle_sha256=frozen['v1_bundle_sha256'],control_probability=control,candidate_probability=candidate,
                    fallback=bool(fallback),fallback_reason=reason,team_features={c:float(feature[c]) for c in v1.FEATURES},
                    availability_features=availability,listed_players=listed,matched_players=matched,injury_report=injury,
                    home_availability=home,away_availability=away,source_receipts=list(receipts),
                    source_receipt_sha256=digest(json.dumps(receipts,sort_keys=True).encode())))
        except (ValueError,requests.RequestException) as error:
            blocked=str(error)
    predictions+=new
    validate(predictions,results,manifest['bundle_sha256'],frozen['v1_bundle_sha256'])
    v1.append(OUT/'predictions.jsonl',new);v1.append(OUT/'results.jsonl',new_results)
    v1.append(OUT/'source_receipts.jsonl',[dict(fetched_at_utc=fetched.isoformat(),sources=receipts,injury_reports=report_receipts)])
    dashboard=dict(status='enabled_shadow_only',updated_at_utc=datetime.now(timezone.utc).isoformat(),season=2027,regular_season_only=True,
                   shadow_sha256=manifest['bundle_sha256'],v1_bundle_sha256=frozen['v1_bundle_sha256'],weights_frozen=True,
                   saved_pairs=len(predictions),adjusted_pairs=sum(not p['fallback'] for p in predictions),fallback_pairs=sum(p['fallback'] for p in predictions),
                   record=record(predictions,results),adjusted_only_record=record(predictions,results,True),capture_blocked_reason=blocked,
                   upcoming=readiness,public_model_unchanged=True)
    (OUT/'dashboard.json').write_text(json.dumps(dashboard,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(new_pairs=len(new),new_results=len(new_results),**dashboard),indent=2))


if __name__=='__main__':main()

