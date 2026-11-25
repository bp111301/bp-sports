"""NFL coverage, evidence and append-only capture tests use local fixtures."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipeline import build_predictions as builder
from pipeline import nfl_availability as availability
from pipeline import nfl_forecast_audit as audit
from pipeline import nfl_pregame_gate as gate
from pipeline import verify_preservation

NOW=datetime(2026,11,25,1,tzinfo=timezone.utc)  # Tuesday evening Central


def game(gid='early',day='2026-11-25',time='20:00',**changes):
    return dict(game_id=gid,season='2026',week='12',game_type='REG',gameday=day,gametime=time,
                home_score='',away_score='',home_team='LA',away_team='GB',**changes)


def forecast(gid='early',capture=None,**changes):
    return dict(game_id=gid,captured_at_utc=(capture or NOW).isoformat(),home_team='LA',away_team='GB',
                kickoff_utc='2026-11-26T01:00:00Z',v4_pick='LA',v4_adjusted_confidence='.6',**changes)


def test_wednesday_slate_is_captured_before_thursday_morning():
    assert gate.run_reason([game()],NOW,forecasts=[])=='early_slate_coverage'
    assert gate.capture_health([game()],[],NOW)['missing_upcoming_game_ids']==['early']
    assert not gate.should_run([game(day='2026-12-01')],NOW,forecasts=[])


def test_complete_fresh_slate_skips_heavy_refresh_but_missing_game_does_not():
    games=[game(),game(gid='later',day='2026-11-29',time='13:00')]
    saved=[forecast(),{**forecast('later'),'kickoff_utc':'2026-11-29T18:00:00Z'}]
    assert gate.capture_health(games,saved,NOW)['status']=='ready'
    assert not gate.should_run(games,NOW,forecasts=saved)
    assert gate.should_run(games,NOW,forecasts=saved[:1])


def test_new_grades_or_build_time_cannot_hide_stale_forecasts():
    saved=[forecast(capture=NOW-timedelta(hours=25))]
    metadata={'captured_at_utc':NOW.isoformat(),'grading_updated_at_utc':NOW.isoformat()}
    health=gate.capture_health([game()],saved,NOW,metadata)
    assert health['status']=='stale' and health['last_forecast_at_utc']==saved[0]['captured_at_utc']
    assert not gate.should_run([game()],NOW,forecasts=saved,metadata=metadata)  # early retry cooldown
    assert gate.should_run([game()],NOW+timedelta(hours=1),forecasts=saved,metadata=metadata)


@pytest.mark.parametrize('change',[
    {'captured_at_utc':'2026-11-26T01:00:00Z'}, {'home_team':'NE'},
    {'kickoff_utc':'2026-11-26T02:00:00Z'}, {'qb_input_review_required':'True'},
    {'v4_adjusted_confidence':'nan'}, {'v4_pick':'NE'},
])
def test_invalid_snapshot_does_not_count_as_coverage(change):
    health=gate.capture_health([game()],[{**forecast(),**change}],NOW)
    assert health['covered_games']==0 and health['missing_upcoming_game_ids']==['early']


def test_kickoff_window_remains_open_despite_early_retry_cooldown():
    now=datetime(2026,11,25,23,30,tzinfo=timezone.utc)
    assert gate.run_reason([game()],now,forecasts=[],metadata={'captured_at_utc':now.isoformat()})=='pregame_window'
    assert not gate.future_games([game()],datetime(2026,11,26,1,tzinfo=timezone.utc))


def evidence(qb_id='00-0000001',name='New Starter',**changes):
    return dict(team='LA',qb_id=qb_id,qb_name=name,source_url='https://www.nfl.com/news/starter',
                verified_at_utc='2026-11-25T00:59:00Z',source_published_at_utc='2026-11-24T20:00:00Z',
                source_kind='official_announcement',**changes)


def starter(override=None,announcements=None,injuries=None,previous=None,pid='00-0000000'):
    return availability.starter_context('LA','GB','Old Starter',pid,override or {},announcements or [],
                                        injuries or {},{},previous or {},pd.Timestamp(NOW),pd.Timestamp('2026-11-26T01:00Z'))


def test_explicit_starter_change_is_checked_even_if_schedule_qb_not_out():
    context,selected=starter(announcements=[evidence()])
    assert selected['qb_name']=='New Starter' and context['qb_evidence_state']=='confirmed'
    assert 'schedule_differs_from_confirmation' in context['qb_evidence_issues']
    assert not context['qb_review_required']


def test_conflicting_confirmations_block_instead_of_selecting_first():
    context,_=starter(announcements=[evidence(),evidence(qb_id='00-0000002',name='Other Starter')])
    assert context['qb_review_required'] and context['qb_evidence_state']=='conflict'
    context,_=starter(override=evidence(qb_id='00-0000002',name='Manual Starter'),announcements=[evidence()])
    assert context['qb_review_required']


@pytest.mark.parametrize('change',[
    {'verified_at_utc':'2026-11-26T02:00:00Z'}, {'verified_at_utc':'2026-11-01T00:00Z'},
    {'source_published_at_utc':'2026-11-25T02:00Z'}, {'source_url':'http://www.nfl.com/news/starter'},
    {'team':'GB'}, {'verified_at_utc':'invalid'},
])
def test_stale_future_or_wrong_team_news_cannot_confirm_starter(change):
    context,selected=starter(announcements=[{**evidence(),**change}])
    assert not selected and context['qb_evidence_state']=='unconfirmed'


def test_report_failure_keeps_known_absence_and_missing_identity_is_blocked():
    previous={'assumed_qb':'Old Starter','qb_review_required':True,'qb_status':'Out','assumption_checked_at_utc':'2026-11-24T22:00Z'}
    context,_=starter(previous=previous)
    assert context['qb_review_required'] and context['qb_status']=='Out'
    assert context['prior_absence_evidence']['assumption_checked_at_utc']=='2026-11-24T22:00Z'
    context,_=starter(pid=np.nan)
    assert context['qb_review_required'] and context['qb_evidence_state']=='missing_identity'
    assert not starter()[0]['qb_review_required']  # known ID, unconfirmed: labeled, not invented as confirmed


def test_future_dated_manual_override_cannot_enter_forecast_inputs():
    context,selected=starter(override={**evidence(),'verified_at_utc':'2026-11-25T02:00Z'})
    assert not selected and context['assumed_qb']=='Old Starter'
    assert context['qb_review_required'] and 'invalid_override_time' in context['qb_evidence_issues']


def test_current_confirmation_is_retained_when_headline_leaves_front_page():
    previous={'assumed_qb':'New Starter','assumed_qb_id':'00-0000001','qb_evidence_state':'confirmed',
              'starter_source_url':'https://www.nfl.com/news/starter','starter_verified_at_utc':'2026-11-25T00:59:00Z',
              'assumption_source':'official_announcement'}
    context,selected=starter(previous=previous)
    assert context['qb_evidence_state']=='confirmed' and selected['qb_name']=='New Starter'
    assert selected['verified_at_utc']=='2026-11-25T00:59:00Z'
    previous['starter_verified_at_utc']='2026-11-01T00:00Z'
    assert starter(previous=previous)[0]['qb_evidence_state']=='unconfirmed'


def test_builder_rejects_wrong_starter_wrong_matchup_and_stale_context():
    row={'home_team':'LA','away_team':'GB','home_qb_id_assumed':'00-0000000','away_qb_id_assumed':'00-0000003',
         'home_qb_name_assumed':'Old Starter','away_qb_name_assumed':'Away Starter','kickoff_utc':'2026-11-26T01:00Z'}
    report={'home_team':'LA','away_team':'GB','checked_at_utc':NOW.isoformat(),'kickoff_utc':row['kickoff_utc']}
    assert not builder.qb_review(row,report,pd.Timestamp(NOW))
    for change in [{'home_team':'NE'},{'checked_at_utc':'2026-11-23T01:00Z'},
                   {'checked_at_utc':'2026-11-25T02:00Z'},{'home':{'assumed_qb_id':'00-0000009'}},
                   {'qb_review_required':True}]:
        assert builder.qb_review(row,{**report,**change},pd.Timestamp(NOW))


def test_audit_log_preserves_bytes_and_rejects_changed_duplicate(tmp_path):
    path=tmp_path/'receipts.jsonl'
    path.write_text('{ "prediction_id": "old", "confidence": 0.7 }\n')
    before=path.read_bytes()
    audit.append_receipts(path,[{'prediction_id':'new','features':{'unknown':np.nan},'probability':np.float64(.6)}])
    assert path.read_bytes().startswith(before)
    records=[json.loads(line) for line in path.read_text().splitlines()]
    assert records[1]['features']['unknown'] is None
    audit.append_receipts(path,records)
    with pytest.raises(ValueError,match='different evidence'):audit.append_receipts(path,[{'prediction_id':'old','confidence':.8}])
    verify_preservation.verify_rows(records,records+[{'prediction_id':'third'}],('prediction_id',),set())
    with pytest.raises(ValueError):verify_preservation.verify_rows(records,[{**records[0],'confidence':.8},records[1]],('prediction_id',),set())


def manifest(root):
    records=[]
    for name in ['schedules.csv','play_by_play_2026.csv.gz']:
        (root/name).write_bytes(b'fixture input\n')
        records.append({'file':name,'sha256':audit.digest(root/name),'bytes':(root/name).stat().st_size,
                        'retrieved_at_utc':(pd.Timestamp.now(tz='UTC')-pd.Timedelta(minutes=5)).isoformat(),
                        'source_url':'https://example.test/'+name})
    (root/'manifest.json').write_text(json.dumps(records))


def test_audit_refuses_changed_raw_inputs(tmp_path):
    manifest(tmp_path);bundle=tmp_path/'bundle';bundle.write_bytes(b'frozen')
    assert audit.inputs(tmp_path,2026,bundle,tmp_path/'absent.json')['bundle_sha256']==hashlib.sha256(b'frozen').hexdigest()
    (tmp_path/'schedules.csv').write_bytes(b'changed')
    with pytest.raises(ValueError,match='does not match'):audit.inputs(tmp_path,2026,bundle,tmp_path/'absent.json')


def test_receipt_after_capture_cannot_claim_contemporaneous_evidence():
    feed=pd.DataFrame([dict(game_id='g',captured_at_utc='2026-11-25T01:00:00Z',kickoff_utc='2026-11-26T01:00:00Z')])
    features=pd.DataFrame([{'game_id':'g','x':1.}]).set_index('game_id')
    evidence={'input_receipts':[{'retrieved_at_utc':'2026-11-25T01:00:01Z'}]}
    with pytest.raises(ValueError,match='before capture'):
        audit.records(feed,features,{'g':{}},'frozen',evidence,{},'snapshot')


def test_workflows_keep_cron_and_publish_receipts_before_reporting_capture_failure():
    workflow=Path('.github/workflows/update_predictions.yml').read_text()
    assert '0 13,14 * 1,2,9-12 0,4' in workflow and '7,22,37,52 * * 1,2,9-12 *' in workflow
    assert workflow.index('Check actual NFL forecast coverage')<workflow.index('Commit generated snapshots')<workflow.index('Report incomplete NFL capture')
    assert 'git add data/nfl/audit' in workflow
    watchdog=Path('.github/workflows/final_grading_watchdog.yml').read_text()
    assert '17 */2 * * *' in watchdog and '--remote --due-only' in watchdog
    assert 'dispatch_if_due update_predictions.yml 900' in watchdog


def test_health_cli_reports_gap_without_refreshing_build_or_forecast_timestamps(tmp_path,monkeypatch):
    import sys
    schedule=tmp_path/'schedules.csv'
    now=datetime.now(timezone.utc);start=now+timedelta(days=1)
    eastern=start.astimezone(gate.ZoneInfo('America/New_York'))
    row={**game(),'season':str(gate.season_for(now)),'gameday':eastern.strftime('%Y-%m-%d'),'gametime':eastern.strftime('%H:%M')}
    with schedule.open('w') as file:
        writer=csv.DictWriter(file,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    meta=tmp_path/'metadata.json';stamp=(now-timedelta(days=2)).isoformat();meta.write_text(json.dumps({'captured_at_utc':stamp}))
    output=tmp_path/'health.json'
    monkeypatch.setattr(sys,'argv',['gate','--health-only','--schedule',str(schedule),'--ledger',str(tmp_path/'absent.csv'),
                                   '--metadata',str(meta),'--availability',str(tmp_path/'absent.json'),
                                   '--health-output',str(output),'--update-metadata','--fail-on-gaps'])
    with pytest.raises(SystemExit,match='Missing upcoming forecasts'):gate.main()
    assert json.loads(meta.read_text())['captured_at_utc']==stamp
    assert json.loads(output.read_text())['last_forecast_at_utc'] is None


def test_new_capture_links_receipt_to_eligible_snapshot_and_preserves_old_forecast(tmp_path,monkeypatch):
    import sys
    from types import SimpleNamespace
    manifest(tmp_path)
    bundle=tmp_path/'bundle';bundle.write_bytes(b'frozen test fixture')
    now=pd.Timestamp.now(tz='UTC');start=now+pd.Timedelta(days=1)
    targets=pd.DataFrame([dict(game_id=gid,home_team='LA',away_team='GB',game_type='REG',week=12,
                               kickoff_utc=start,gameday=start.tz_localize(None).normalize(),gametime='20:00',
                               home_qb_id='00-0000001',home_qb_name='Home QB',away_qb_id='00-0000002',away_qb_name='Away QB',
                               home_score=np.nan,away_score=np.nan) for gid in ['eligible','blocked']])
    predictor=SimpleNamespace(predict_proba=lambda x:np.tile([.4,.6],(len(x),1)))
    frozen={'bundle_version':'test_frozen','market_used_for_pick':False,
            'v3':{'features':['base'],'win_model':predictor},'base_features':['base'],
            'qb_change_features':['change'],'qb_quality_features':['quality'],
            'qb_change_model':predictor,'qb_quality_model':predictor,
            'qb_change_calibrator':predictor,'qb_quality_calibrator':predictor,
            'risk_thresholds':{'explosive_last5_abs_q75':1,'turnover_last5_abs_q75':1,'early_success_last5_abs_q75':1}}
    monkeypatch.setattr(builder.joblib,'load',lambda path:frozen)
    monkeypatch.setattr(builder,'load_inputs',lambda *args:(targets.copy(),pd.DataFrame()))
    monkeypatch.setattr(builder,'team_games',lambda *args:(targets.iloc[:0],pd.DataFrame()))
    monkeypatch.setattr(builder,'elo',lambda *args:{})
    monkeypatch.setattr(builder,'base_features',lambda *args:pd.DataFrame({'game_id':['eligible','blocked'],'base':[1.,2.]}))
    monkeypatch.setattr(builder,'qb_games',lambda *args:pd.DataFrame())
    monkeypatch.setattr(builder,'qb_features',lambda *args:pd.DataFrame([dict(game_id=gid,change=0.,quality=np.nan,
                            home_qb_id_assumed='00-0000001',home_qb_name_assumed='Home QB',
                            away_qb_id_assumed='00-0000002',away_qb_name_assumed='Away QB') for gid in ['eligible','blocked']]))
    monkeypatch.setattr(builder,'risk',lambda *args:pd.DataFrame([dict(game_id=gid,net_explosive_5=0.,to_recent_edge_5=0.,early_success_matchup_5=0.) for gid in ['eligible','blocked']]))
    contexts={'games':{gid:dict(game_id=gid,home_team='LA',away_team='GB',checked_at_utc=now.isoformat(),
                               kickoff_utc=start.isoformat(),qb_review_required=gid=='blocked') for gid in ['eligible','blocked']}}
    availability_path=tmp_path/'availability.json';availability_path.write_text(json.dumps(contexts))
    ledger=tmp_path/'ledger.csv'
    ledger.write_text('prediction_id,game_id,captured_at_utc,v4_adjusted_confidence,settlement_status\nold:old,old,2026-10-01T00:00:00Z,0.7000000000000000123,final\n')
    old=verify_preservation.records(str(ledger),ledger.read_text())
    audit_path=tmp_path/'audit.jsonl'
    monkeypatch.setattr(sys,'argv',['build','--season','2026','--data-dir',str(tmp_path),'--bundle',str(bundle),
                                   '--overrides',str(tmp_path/'absent.json'),'--ledger',str(ledger),
                                   '--audit-log',str(audit_path),'--availability',str(availability_path)])
    builder.main()
    after=verify_preservation.records(str(ledger),ledger.read_text())
    verify_preservation.verify_rows(old,after,('prediction_id',),set())
    new=[r for r in after if r['game_id']=='eligible']
    assert len(new)==1 and not any(r['game_id']=='blocked' for r in after)
    receipt=json.loads(audit_path.read_text())
    assert receipt['prediction_id']==new[0]['prediction_id']
    assert receipt['features']['quality'] is None and receipt['missing_features']==['quality']
    assert receipt['component_home_probabilities']['v4_core']==pytest.approx(.6)
    assert receipt['bundle_sha256']==audit.digest(bundle)
    metadata=json.loads((tmp_path/'prediction_metadata.json').read_text())
    assert metadata['eligible_games']==metadata['audit_receipts_saved']==1
    assert metadata['qb_review_games']==['blocked']
