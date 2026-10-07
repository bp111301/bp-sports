import copy
import json
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import nba_ui

APP=Path(__file__).resolve().parents[1]/'app.py'

def fixture():return json.loads(nba_ui.SNAPSHOT.read_text())

def prediction():
    now=pd.Timestamp.now(tz='UTC')
    return dict(game_id='nba-test-1',season=2027,season_type=2,home_team='BOS',away_team='DET',home_win_prob=.65,start_time_utc=(now+pd.Timedelta(days=1)).isoformat(),created_at_utc=(now-pd.Timedelta(hours=1)).isoformat(),status='pending',actual_home_win=None)

def test_nba_page_keeps_live_and_historical_scores_separate():
    with patch('nba_ui.load_dashboard',return_value=(fixture(),False)):
        at=AppTest.from_file(APP,default_timeout=15);at.session_state['bp_sport']='NBA';at.run()
        assert not at.exception and not at.code
        assert at.radio(key='bp_sport').options==['Overview','NFL','CFB','NHL','NBA']
        assert [t.label for t in at.tabs]==['PREDICTIONS','MODEL RECORD','THE MODEL']
        assert any('0–0' in m.value and 'PROSPECTIVE' in m.value for m in at.markdown)
        assert any('69.19%' in m.value and 'HISTORICAL ACCURACY' in m.value for m in at.markdown)
        assert any('has not been enabled' in m.value for m in at.markdown)
        assert any('not yet adjust' in m.value for m in at.markdown)
        at.radio(key='bp_sport').set_value('NFL').run();assert not at.exception
        at.radio(key='bp_sport').set_value('CFB').run();assert not at.exception

def test_preseason_historical_late_and_future_captures_do_not_enter_live_record():
    now=pd.Timestamp.now(tz='UTC');valid=prediction();records=[]
    for changes in ({'season_type':1},{'season':2026},{'created_at_utc':valid['start_time_utc']},{'created_at_utc':(now+pd.Timedelta(hours=1)).isoformat()},{'status':'settled','actual_home_win':1}):
        r=copy.deepcopy(valid);r.update(changes);records.append(r)
    assert nba_ui.prepare_predictions(records,now).empty

def test_completed_results_and_started_pending_views():
    data=fixture();now=pd.Timestamp.now(tz='UTC');r=prediction()
    r['start_time_utc']=(now-pd.Timedelta(minutes=10)).isoformat()
    data['prospective']={'feed_status':'enabled','predictions':[r]}
    board=nba_ui.prepare_predictions([r],now);assert nba_ui.live_record(board)==(0,0,0)
    with patch('nba_ui.load_dashboard',return_value=(data,False)):
        at=AppTest.from_file(APP,default_timeout=15);at.session_state['bp_sport']='NBA';at.run()
        assert not at.exception
        at.selectbox(key='nba_view').set_value('Awaiting results').run()
        assert any('Status unavailable' in m.value for m in at.markdown)
        at.text_input(key='nba_search').set_value('Pistons').run();assert not at.exception and len([e for e in at.expander if e.label.startswith("Forecast details")])==1
    r['status']='settled';r['actual_home_win']=1
    assert nba_ui.live_record(nba_ui.prepare_predictions([r],now))==(1,1,0)

def test_invalid_identity_and_duplicate_forecasts_are_rejected():
    data=fixture();data['evaluation']['bundle_sha256']='different'
    with pytest.raises(ValueError):nba_ui.validate_history(data)
    r=prediction()
    with pytest.raises(ValueError):nba_ui.prepare_predictions([r,r],pd.Timestamp.now(tz='UTC'))

def test_saved_history_does_not_claim_zero_live_record():
    data=fixture();data['prospective']={'feed_status':'unavailable','predictions':[]}
    with patch('nba_ui.load_dashboard',return_value=(data,True)):
        at=AppTest.from_file(APP,default_timeout=15);at.session_state['bp_sport']='NBA';at.run()
        assert not at.exception
        assert any('saved historical snapshot' in w.value for w in at.warning)
        assert not any('0–0' in m.value for m in at.markdown)
