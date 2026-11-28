"""Operational safeguards use fixtures and temporary files, never live grading."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest


def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,Path(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_nfl_cli_delegates_to_confirmed_final_grader(monkeypatch):
    import sys
    from types import SimpleNamespace
    called=[]
    grader=SimpleNamespace(REQUEST_ERRORS=[],nfl=lambda now,ledger_path:called.append(ledger_path))
    monkeypatch.setitem(sys.modules,'check_finals',grader)
    module=load_module('pipeline/settle_predictions.py','nfl_cli_test')
    monkeypatch.setattr(sys,'argv',['settle_predictions','--ledger','temporary.csv','--schedules','unverified.csv'])
    module.main()
    assert called==['temporary.csv']


def test_grading_timestamp_cannot_hide_stopped_forecast_capture():
    import overview_ui as overview
    from tests.test_overview_ui import fixture,NOW
    payload=fixture()
    board,_,updates=overview.prepare(payload,NOW)
    original=updates['NHL']
    payload['nhl_update']['data']['as_of_utc']=NOW.isoformat()
    payload['nhl']['data'][1]['created_at_utc']=(NOW-pd.Timedelta(minutes=1)).isoformat()
    _,_,checked=overview.prepare(payload,NOW)
    assert checked['NHL']==original==board.loc[board.sport.eq('NHL'),'created'].max()


def test_optional_goalie_provider_outage_keeps_nhl_ledger_available():
    import nhl_ui
    rows=json.loads(nhl_ui.SNAPSHOT.read_text())['predictions']
    csv=pd.DataFrame(rows).to_csv(index=False)
    def fetch(path):
        if path.endswith('prediction_ledger.csv'):return csv
        if 'v2_research/summary.json' in path:return '{}'
        raise TimeoutError('goalie provider offline')
    nhl_ui.load_dashboard.clear()
    try:
        with patch('nhl_ui.get_text',side_effect=fetch):payload,saved=nhl_ui.load_dashboard()
        assert not saved and len(payload['predictions'])==len(rows)
        assert payload['goalies']==[] and payload['goalie_summary']['errors']
    finally:nhl_ui.load_dashboard.clear()


def test_cbb_capture_health_reports_block_after_valid_outputs_are_saved():
    module=load_module('pipeline/capture_health.py','capture_health_test')
    assert module.failure_reason('cbb',{'feed_status':'research_preview','capture_blocked_reason':None}) is None
    assert module.failure_reason('cbb',{'feed_status':'research_preview','capture_blocked_reason':'waiting_for_stats'})=='waiting_for_stats'


@pytest.mark.parametrize('missing,features,expected',[
    ([],[],None),(['42'],[],'42'),([],['43'],'43'),(['42'],['42','43'],'42, 43'),
])
def test_cfb_capture_health_reports_supported_gaps_and_ignores_out_of_scope_games(missing,features,expected):
    module=load_module('pipeline/capture_health.py','cfb_capture_health_test')
    coverage={'groups':{'fbs_vs_fbs':{'scheduled_games':53,'missing_current_forecast_game_ids':missing,'missing_feature_game_ids':features},
                        'fbs_vs_fcs':{'scheduled_games':1,'missing_current_forecast_game_ids':['unsupported'],'missing_feature_game_ids':['unsupported']}}}
    reason=module.failure_reason('cfb',coverage)
    assert reason is None if expected is None else reason=='Missing supported CFB forecasts or inputs: '+expected


@pytest.mark.parametrize('coverage',[{}, {'groups':{}}, {'groups':{'fbs_vs_fbs':{'scheduled_games':53}}}])
def test_cfb_missing_coverage_is_not_reported_as_healthy(coverage):
    module=load_module('pipeline/capture_health.py','cfb_invalid_health_test')
    assert module.failure_reason('cfb',coverage)


def test_cfb_reports_coverage_failure_after_publishing_valid_forecasts():
    workflow=Path('.github/workflows/update_cfb_predictions.yml').read_text()
    assert workflow.index('Commit CFB feeds')<workflow.index('Report supported CFB forecast gaps')
    assert 'python pipeline/capture_health.py cfb data/cfb/input_receipts/coverage.json' in workflow
    watchdog=Path('.github/workflows/final_grading_watchdog.yml').read_text()
    assert 'dispatch_if_due update_cfb_predictions.yml 43200' in watchdog


def test_publishing_gate_rejects_changed_probabilities_missing_or_duplicate_forecasts():
    module=load_module('pipeline/verify_preservation.py','preservation_test')
    old=[{'prediction_id':'1','home_win_prob':'0.7000000000000000123','status':'pending'}]
    valid=[{**old[0],'status':'settled'},{'prediction_id':'2','home_win_prob':'.6','status':'pending'}]
    module.verify_rows(old,valid,('prediction_id',),{'status'})
    for rows in [[{**old[0],'home_win_prob':'0.7'}],[],old+old]:
        with pytest.raises(ValueError):module.verify_rows(old,rows,('prediction_id',),{'status'})
