"""UI integration and pregame-record presentation checks; no model fitting."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
import nhl_ui

APP=Path(__file__).resolve().parents[1]/'app.py'

def fixture():
    data=json.loads(nhl_ui.SNAPSHOT.read_text())
    now=pd.Timestamp.now(tz='UTC')
    for r in data['predictions']:
        r['start_time_utc']=(now+pd.Timedelta(days=1)).isoformat()
        r['created_at_utc']=(now-pd.Timedelta(hours=2)).isoformat()
    for r in data['goalies']:
        r['start_time_utc']=(now+pd.Timedelta(days=1)).isoformat()
        r['captured_at_utc']=(now-pd.Timedelta(hours=1)).isoformat()
    return data

def test_sport_navigation_models_and_search():
    with patch('nhl_ui.load_dashboard',return_value=(fixture(),False)):
        at=AppTest.from_file(APP,default_timeout=15).run()
        assert not at.exception
        assert at.radio(key='bp_sport').options==['NFL','CFB','NHL']
        at.radio(key='bp_sport').set_value('NHL').run()
        assert not at.exception
        assert len(at.expander)==12
        assert 'NHL is in prospective research' in at.info[0].value
        for candidate in nhl_ui.MODEL_NAMES:
            at.selectbox(key='nhl_candidate').set_value(candidate).run()
            assert not at.exception and len(at.expander)==12
        at.text_input(key='nhl_search').set_value('Red Wings').run()
        assert not at.exception and len(at.expander)==1
        at.radio(key='bp_sport').set_value('CFB').run()
        assert not at.exception
        assert any(t.label=='PREDICTIONS' for t in at.tabs)
        at.radio(key='bp_sport').set_value('NFL').run()
        assert not at.exception

def test_records_not_backtests_and_started_pending_not_upcoming():
    data=fixture();now=pd.Timestamp.now(tz='UTC')
    for r in data['predictions']:
        r['start_time_utc']=(now-pd.Timedelta(minutes=10)).isoformat()
    board=nhl_ui.prepare_predictions(data['predictions'])
    assert set(nhl_ui.record_metrics(board).Accuracy)=={'—'}
    with patch('nhl_ui.load_dashboard',return_value=(data,False)):
        at=AppTest.from_file(APP,default_timeout=15);at.session_state['bp_sport']='NHL';at.run()
        assert not at.exception and len(at.expander)==0
        at.selectbox(key='nhl_view').set_value('Awaiting results').run()
        assert len(at.expander)==12
        assert any('AWAITING FINAL RESULT' in m.value for m in at.markdown)

def test_invalid_pregame_rows_and_unverified_confirmations():
    data=fixture();bad=copy.deepcopy(data['predictions'][0]);bad['created_at_utc']=bad['start_time_utc']
    assert nhl_ui.prepare_predictions([bad]).empty
    bad['created_at_utc']=data['predictions'][0]['created_at_utc'];bad['status']='invalid_timing'
    assert nhl_ui.prepare_predictions([bad]).empty
    report={'goalie_name':'Example','status':'Confirmed','confirmed_eligible':False}
    assert 'Confirmation unverified' in nhl_ui.goalie_text(report)

def test_saved_snapshot_is_labeled():
    with patch('nhl_ui.load_dashboard',return_value=(fixture(),True)):
        at=AppTest.from_file(APP,default_timeout=15);at.session_state['bp_sport']='NHL';at.run()
        assert not at.exception
        assert any('saved snapshot' in x.value.lower() for x in at.warning)
