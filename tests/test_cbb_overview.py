from pathlib import Path
from unittest.mock import patch
import copy
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import overview_ui as ov

NOW=pd.Timestamp.now(tz='UTC')

def feed():
    record=dict(game_id='401911707',season=2027,season_type=2,
        model_version='CBB_V1_CANDIDATE_20261013',prediction_id='CBB_V1_CANDIDATE_20261013:401911707',
        bundle_sha256=ov.FROZEN_CBB,home_team='Tennessee State Tigers',away_team='Murray State Racers',
        home_team_id='2634',away_team_id='93',home_win_prob=.56,predicted_winner='Tennessee State Tigers',
        neutral_site=True,status='pending',created_at_utc=(NOW-pd.Timedelta(days=1)).isoformat(),
        start_time_utc=(NOW+pd.Timedelta(days=1)).isoformat())
    return dict(feed_status='research_preview',bundle_sha256=ov.FROZEN_CBB,
        updated_at_utc=NOW.isoformat(),predictions=[record])

def test_cbb_pending_forecasts_join_overview_without_inflating_live_record():
    source=feed();before=copy.deepcopy(source)
    board,available,updates=ov.prepare({'cbb':dict(ok=True,data=source)},NOW)
    assert available['cbb'] and len(board)==1 and board.iloc[0].group==ov.PRIMARY['CBB']
    assert ov.metrics(board)['games']==0 and ov.metrics(board)['accuracy'] is None
    assert updates['CBB']==NOW and source==before
    assert len(ov.select_games(board,'Upcoming','CBB','Murray',NOW))==1
    assert ov.select_games(board,'Results','CBB','',NOW).empty

def test_cbb_rejects_wrong_bundle_late_capture_and_duplicate_snapshots():
    source=feed()
    with pytest.raises(ValueError): ov.normalize('cbb',{**source,'bundle_sha256':'wrong'},NOW)
    r=source['predictions'][0]
    assert ov.normalize('cbb',{**source,'predictions':[{**r,'created_at_utc':r['start_time_utc']}]},NOW)==[]
    with pytest.raises(ValueError): ov.normalize('cbb',{**source,'predictions':[r,r]},NOW)

def test_cbb_overview_tile_filters_details_and_board_navigation():
    payload={'cbb':dict(ok=True,data=feed())}
    with patch('overview_ui.load_overview',return_value=payload),patch('overview_ui.context',return_value=None),patch('game_center_ui.load_scores',return_value={}):
        at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=20).run()
        assert not at.exception and at.button(key='open_CBB')
        assert any('Research candidate' in m.value and 'Awaiting season' in m.value for m in at.markdown)
        at.selectbox(key='desk_sport').select('CBB')
        at.selectbox(key='desk_view').select('Upcoming').run()
        assert not at.exception
        at.button(key='desk_details_CBB_401911707').click().run()
        assert not at.exception and any('CBB V1 CANDIDATE PICK' in m.value for m in at.markdown)
        at.button(key='open_CBB').click().run()
        assert not at.exception and at.radio(key='bp_sport').value=='CBB'
