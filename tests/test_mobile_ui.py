"""Game status, Central-date slate controls and the shared mobile card contract."""
import copy
from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import overview_ui as ov
from compact_board_ui import compact_html

NOW=pd.Timestamp('2026-11-16T04:30:00Z')  # Still November 15 in Central time.


def slate():
    rows=[];games={}
    for kind in ['upcoming','live','won','lost','awaiting','postponed','unknown']:
        settled=kind in ('won','lost')
        start='2026-11-16T05:00Z' if kind=='upcoming' else '2026-11-16T02:00Z'
        row=ov.row(kind,'NHL','reference_control','DET','NJD',.7,'2026-11-14T12:00Z',start,settled,1 if kind=='won' else 0 if settled else None,
                   dict(home_score=4,away_score=2) if kind=='won' else dict(home_score=2,away_score=4) if settled else {})
        rows.append(row)
        if kind!='unknown':
            state='final' if kind in ('won','lost','awaiting') else 'scheduled' if kind=='upcoming' else kind
            games['NHL:'+kind]=dict(sport='NHL',home_team='DET',away_team='NJD',state=state,start_time_utc=start,home_score=4,away_score=2,detail='3rd')
    board=pd.DataFrame(rows);board['confidence']=.7
    return board,{'games':games}


def test_status_counts_use_verified_states_include_ungraded_finals_and_keep_unknowns():
    board,feed=slate();before=board.copy(deep=True)
    # A stale live overlay must not take a graded game out of Final.
    feed['games']['NHL:won']['state']='live'
    shown,counts=ov.filter_slate(board,feed,NOW)
    assert counts=={'All':7,'Live':1,'Upcoming':1,'Final':3}
    assert shown.set_index('game_id').loc['unknown','slate_status']=='Other'
    assert shown.set_index('game_id').loc['postponed','slate_status']=='Other'
    pd.testing.assert_frame_equal(board,before)
    empty,counts=ov.filter_slate(board.iloc[:0],feed,NOW)
    assert empty.empty and counts==dict(All=0,Live=0,Upcoming=0,Final=0)


@pytest.mark.parametrize('sport',['NFL','CFB','NHL','NBA','CBB'])
def test_shared_cards_show_saved_pick_and_grade_without_inventing_settlement(sport):
    board,feed=slate()
    for i,r in board.iterrows():
        r=r.copy();r.sport=sport
        status=feed['games'].get('NHL:'+r.game_id)
        mapped={'games':{sport+':'+r.game_id:{**status,'sport':sport}}} if status else {}
        before=copy.deepcopy(r.to_dict())
        with patch('nfl_availability_ui.load_availability',return_value={}):
            card=compact_html(r,mapped,NOW)
        assert 'SAVED PICK' in card and '70.0%' in card and 'WIN PROBABILITY' in card
        assert '\n' not in card
        if r.game_id=='won':assert 'Pick won' in card
        elif r.game_id=='lost':assert 'Pick lost' in card
        elif r.game_id=='awaiting':
            assert 'Final · Awaiting grading' in card
            assert 'Pick won' not in card and 'Pick lost' not in card
        elif r.game_id=='upcoming':assert 'Scheduled' in card and '11:00 PM CT' in card
        elif r.game_id=='live':assert 'Live' in card and '<strong>4</strong>' in card
        assert r.to_dict()==before


def test_overview_defaults_to_today_before_records_and_filters_the_selected_central_date():
    board,feed=slate()
    records=[]
    for r in board.to_dict('records'):
        records.append(dict(game_id=r['game_id'],home_team=r['home'],away_team=r['away'],candidate='reference_control',bundle_sha256=ov.FROZEN_NHL,
                            home_win_prob=r['p'],created_at_utc=r['created'].isoformat(),start_time_utc=r['start'].isoformat(),status='settled' if r['settled'] else 'pending',actual_home_win=r['y']))
    payload={'nhl':dict(ok=True,data=records)}
    with patch('overview_ui.load_overview',return_value=payload),patch('game_center_ui.load_scores',return_value=feed),patch('overview_ui.load_scores',return_value=feed):
        app=AppTest.from_string(f'import overview_ui as ov\nov.render_overview("{NOW.isoformat()}")').run()
        assert not app.exception
        assert app.tabs[0].label=='GAMES' and app.tabs[1].label=='SEASON RECORDS'
        assert app.selectbox(key='desk_view').value=='Today'
        assert app.date_input(key='desk_date').value==date(2026,11,15)
        assert app.radio(key='desk_status').options==['All (7)','Live (1)','Upcoming (1)','Final (3)']
        app.radio(key='desk_status').set_value('Final').run()
        cards=[m.value for m in app.tabs[0].markdown if 'class="bp-mini"' in m.value]
        assert len(cards)==3 and any('Awaiting grading' in c for c in cards)
        app.radio(key='desk_status').set_value('All').run()
        assert len([m for m in app.tabs[0].markdown if 'class="bp-mini"' in m.value])==7
        app.date_input(key='desk_date').set_value(date(2026,11,16)).run()
        assert not app.exception and app.selectbox(key='desk_view').value=='Selected date'
        assert app.radio(key='desk_status').options==['All (0)','Live (0)','Upcoming (0)','Final (0)']
        app.selectbox(key='desk_view').set_value('Today').run()
        assert not app.exception and app.date_input(key='desk_date').value==date(2026,11,15)


def test_card_with_unavailable_confidence_and_tied_result_remains_readable():
    board,feed=slate();r=board.iloc[0].copy();r.confidence=None
    assert 'Unavailable' in compact_html(r,feed,NOW)
    r.details={'settlement_status':'tie','actual_home_score':20,'actual_away_score':20}
    r.sport='NFL'
    with patch('nfl_availability_ui.load_availability',return_value={}):
        card=compact_html(r,{},NOW)
    assert 'Tie · excluded from record' in card and 'Pick won' not in card
