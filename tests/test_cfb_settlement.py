import importlib.util
from pathlib import Path
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('cfb_settlement_guard',Path('research/cfb/settlement_guard.py'));g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
NOW=pd.Timestamp('2026-10-07T09:00Z')
def prediction():return dict(prediction_id='test',game_id=1,home_team='Troy',away_team='Southern Mississippi',predicted_winner='Troy',home_win_prob=.7,snapshot_created_utc='2026-10-06T18:00Z',kickoff_utc='2026-10-07T00:00Z')
def final():return dict(game_id=1,home_team='Troy',away_team='Southern Miss',start_date='2026-10-07T00:00Z',start_time_tbd=False,completed=True,home_points=30,away_points=20)
def test_numeric_in_progress_scores_and_placeholders_do_not_settle():
 assert g.result_for(prediction(),{**final(),'completed':False},NOW) is None
 for update in [dict(home_points=20),dict(home_points=-1),dict(home_points=float('nan')),dict(start_time_tbd=True)]:assert g.result_for(prediction(),{**final(),**update},NOW) is None

def test_final_correctly_settles_aliases_without_altering_snapshot():
 p=prediction();before=p.copy();result=g.result_for(p,final(),NOW)
 assert result['actual_winner']=='Troy' and result['correct']==1 and result['brier']==pytest.approx(.09)
 assert p==before

def test_actual_rescheduled_kickoff_controls_pregame_validity():
 assert g.result_for(prediction(),{**final(),'start_date':'2026-10-06T17:00Z'},NOW) is None
 assert g.result_for(prediction(),{**final(),'start_date':'2026-10-07T23:00Z'},NOW) is None
 assert g.result_for(prediction(),final(),NOW) is not None

def test_wrong_home_away_and_pre_freeze_shadow_snapshots_rejected():
 assert g.result_for(prediction(),{**final(),'away_team':'Alabama'},NOW) is None
 assert g.result_for(prediction(),final(),NOW,'2026-10-06T19:00Z') is None
 assert g.result_for(prediction(),final(),NOW,'2026-10-06T17:00Z') is not None

def test_duplicate_schedule_or_prediction_ids_rejected():
 with pytest.raises(ValueError):g.schedule_index(pd.DataFrame([final(),final()]))
 with pytest.raises(ValueError):g.checked_schedule_fields(pd.DataFrame([prediction(),prediction()]),g.schedule_index(pd.DataFrame([final()])))

def test_current_kickoff_metadata_preserves_original_snapshot_time():
 p=prediction();d=g.checked_schedule_fields(pd.DataFrame([p]),g.schedule_index(pd.DataFrame([{**final(),'start_date':'2026-10-07T23:00Z'}])))
 assert d.iloc[0].kickoff_utc==p['kickoff_utc'] and d.iloc[0].schedule_kickoff_utc=='2026-10-07T23:00Z'

def test_candidate_b_bundle_integrity():
 m=g.verify_bundle('model/cfb/v2/candidate_b_bundle.joblib','model/cfb/v2/candidate_b_manifest.json');assert m['version']=='CFB_V2_CANDIDATE_B'
