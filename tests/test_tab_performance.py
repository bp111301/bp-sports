from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from unittest.mock import patch

import pandas as pd
import pytest
import streamlit as st

from compact_board_ui import prepare_compact
from overview_ui import ts
from tests.test_overview_ui import fixture, NOW


def test_sport_switch_never_processes_an_unselected_feed():
    payload=fixture()
    class UnselectedRows:
        def __iter__(self):raise AssertionError('unselected sport was processed')
    payload['cbb']={'ok':True,'data':UnselectedRows()}
    board,available=prepare_compact('NFL',payload,{},NOW)
    assert available['nfl'] and set(board.sport)=={'NFL'}
    assert board.iloc[0].p==.6


def test_cbb_and_nfl_context_reuse_loaded_overview_sources():
    import cbb_ui
    import nfl_availability_ui
    cbb={'feed_status':'research_preview','predictions':[]}
    availability={'games':{'nfl1':{'qb_uncertain':True}}}
    payload={'cbb':{'ok':True,'data':cbb},'nfl_availability':{'ok':True,'data':availability}}
    with patch('overview_ui.load_overview',return_value=payload), \
         patch('cbb_ui.urlopen',side_effect=AssertionError('duplicate CBB request')), \
         patch('nfl_availability_ui.urlopen',side_effect=AssertionError('duplicate NFL request')):
        assert cbb_ui.load_feed()==cbb
        assert nfl_availability_ui.load_availability()==availability


def test_selected_feed_fetches_only_required_sources_and_reuses_cache(monkeypatch):
    import overview_ui as overview
    calls=[]
    def fetch(item):
        key,_=item;calls.append(key)
        return key,{'ok':True,'data':{'source':key}}
    overview.load_source.clear()
    monkeypatch.setattr(overview,'fetch_source',fetch)
    try:
        assert set(overview.load_overview(('nba','nba_injury')))=={'nba','nba_injury'}
        overview.load_overview(('nba',))
        assert sorted(calls)==['nba','nba_injury']
        overview.load_overview(('cbb',))
        assert calls.count('cbb')==1 and 'nfl' not in calls
        with pytest.raises(KeyError):overview.load_overview(('unknown',))
        assert len(calls)==3
    finally:overview.load_source.clear()


def test_favorites_menu_never_downloads_forecast_archives():
    import game_center_ui
    from streamlit.testing.v1 import AppTest
    game_center_ui.college_favorites.clear()
    with patch('cbb_ui.load_feed',side_effect=AssertionError('Menu must not download CBB forecasts')), \
         patch('overview_ui.load_overview',side_effect=AssertionError('Menu must not download other forecasts')):
        app=AppTest.from_string("import game_center_ui\ngame_center_ui.render_preferences({'DET':'Lions'})").run()
    assert not app.exception
    teams=game_center_ui.college_favorites()
    assert 'CBB:Murray State Racers' in teams and 'CFB:Texas Tech' in teams


def test_weekly_nfl_ignores_unrelated_sports_and_reuses_supplied_scores():
    import overview_ui as overview
    payload=fixture()
    class Unrelated:
        def __iter__(self):raise AssertionError('NFL records must not parse CBB')
    payload['cbb']={'ok':True,'data':Unrelated()}
    with patch('game_center_ui.load_scores',side_effect=AssertionError('Scores already loaded')):
        board,available=overview.weekly_board(payload,'NFL',NOW,score_feed={})
    assert available and len(board)==1 and board.iloc[0].p==.6


def test_cbb_pagination_limits_cards_preserves_export_and_resets_filters(monkeypatch):
    import io
    import cbb_ui
    from streamlit.testing.v1 import AppTest
    from tests.test_cbb_overview import feed
    data=feed();original=data['predictions'][0]
    data['predictions']=[dict(original,game_id=f'{i:03}',home_team=f'Home {i}',away_team=f'Away {i}',predicted_winner=f'Home {i}',features={'elo':i}) for i in range(81)]
    data['summary']={'saved_games':81}
    monkeypatch.setattr(cbb_ui,'_pagination_fixture',data,raising=False)
    with patch('cbb_ui.st.download_button') as download:
        app=AppTest.from_string('import cbb_ui\ncbb_ui.render_board(cbb_ui._pagination_fixture)').run()
        assert not app.exception
        cards=[m.value for m in app.markdown if 'CBB V1 CANDIDATE PICK' in m.value]
        assert len(cards)==40 and 'Home 0' in cards[0] and 'Home 39' in cards[-1]
        assert len(pd.read_csv(io.StringIO(download.call_args.args[1])))==81
        app.selectbox(key='cbb_page').set_value(3).run()
        assert not app.exception
        cards=[m.value for m in app.markdown if 'CBB V1 CANDIDATE PICK' in m.value]
        assert len(cards)==1 and 'Home 80' in cards[0]
        assert len(pd.read_csv(io.StringIO(download.call_args.args[1])))==81
        app.text_input(key='cbb_search').set_value('Home 0').run()
        assert not app.exception and app.session_state['cbb_page']==1
        assert len(pd.read_csv(io.StringIO(download.call_args.args[1])))==1


@pytest.mark.parametrize('value',[None,'not a timestamp','2026-11-01T14:30:00Z',
    '2026-11-02T04:59:00+00:00','2026-10-30',pd.Timestamp('2026-10-30T00:00',tz='America/Chicago')])
def test_fast_scalar_timestamp_preserves_utc_and_invalid_input_guards(value):
    expected=pd.to_datetime(value,utc=True,errors='coerce')
    actual=ts(value)
    assert pd.isna(actual) if pd.isna(expected) else actual==expected


def test_expired_background_cache_returns_immediately_and_then_publishes_new_data():
    entered,release=Event(),Event()
    calls=[]
    @st.cache_data(ttl=1,refresh_mode='background',show_spinner=False)
    def load_snapshot():
        calls.append(1)
        if len(calls)>1:
            entered.set()
            assert release.wait(3)
        return {'version':len(calls)}
    load_snapshot.clear()
    assert load_snapshot()=={'version':1}
    time.sleep(1.05)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            read=pool.submit(load_snapshot)
            assert entered.wait(1)
            try:
                assert read.result(timeout=.3)=={'version':1}
            finally:release.set()
        deadline=time.monotonic()+1
        while load_snapshot()!= {'version':2}:
            assert time.monotonic()<deadline
            time.sleep(.01)
        assert len(calls)==2
    finally:
        release.set()
        load_snapshot.clear()
