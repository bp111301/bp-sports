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
