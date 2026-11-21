import copy
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import nfl_availability_ui as ui

NOW=pd.Timestamp('2026-10-18T16:05Z')

def fixture():
    row=dict(game_id='g',sport='NFL',home='CLE',away='BAL',p=.3,confidence=.7,created=pd.Timestamp('2026-10-15T13:00Z'),settled=False,
             details=dict(captured_at_utc='2026-10-15T13:00Z',v4_pick='BAL',v4_adjusted_confidence=.7))
    latest=dict(home_team='CLE',away_team='BAL',captured_at_utc='2026-10-18T16:01Z',kickoff_utc='2026-10-18T17:00Z',v4_pick='BAL',
                v4_adjusted_confidence=.6,bundle_version='BP_V4_2026_FROZEN_20261005')
    entry=dict(game_id='g',kickoff_utc='2026-10-18T17:00Z',checked_at_utc='2026-10-18T16:00Z',latest_forecast=latest,qb_review_required=False,
               home=dict(team='CLE',injury_report_available=True,inactives_published=False,assumed_qb='Deshaun Watson',players=[]),
               away=dict(team='BAL',injury_report_available=True,inactives_published=False,assumed_qb='Tyler Huntley',players=[]))
    return row,dict(games=dict(g=entry))

def test_latest_pregame_display_does_not_mutate_first_snapshot_or_record():
    row,payload=fixture();original=copy.deepcopy(row);projected=ui.project_row(row,payload,NOW)
    assert projected['p']==pytest.approx(.4) and projected['details']['display_uses_latest_pregame']
    assert row==original and projected['details']['original_snapshot_captured_at_utc']=='2026-10-15T13:00Z'
    settled={**row,'settled':True};assert ui.project_row(settled,payload,NOW)==settled

@pytest.mark.parametrize('field,value',[
    ('captured_at_utc','2026-10-18T17:01Z'),('captured_at_utc','2026-10-18T16:10Z'),
    ('bundle_version','other'),('home_team','ATL'),('kickoff_utc','2026-10-18T15:00Z'),('v4_adjusted_confidence',1.1)])
def test_postkickoff_future_wrong_model_or_matchup_refresh_is_rejected(field,value):
    row,payload=fixture();payload['games']['g']['latest_forecast'][field]=value
    assert ui.project_row(row,payload,NOW)==row

def test_late_report_cannot_relabel_earlier_prediction_as_news_aware():
    row,payload=fixture();payload['games']['g']['checked_at_utc']='2026-10-18T16:02Z'
    assert ui.project_row(row,payload,NOW)==row

def test_qb_block_missing_reports_and_preliminary_status_are_clear():
    row,payload=fixture();entry=payload['games']['g'];entry['qb_review_required']=True
    assert ui.project_row(row,payload,NOW)==row and ui.checked_label(entry,NOW)=='QB input needs review'
    entry['qb_review_required']=False;assert ui.checked_label(entry,NOW)=='Inactives pending'
    entry['home']['injury_report_available']=False;assert ui.checked_label(entry,NOW)=='Injury report unavailable'

def test_official_report_panel_renders_with_pending_inactives(monkeypatch):
    _,payload=fixture();payload['games']['g']['away']['players']=[dict(name='Lamar Jackson',position='QB',status='Out')]
    monkeypatch.setattr(ui,'load_availability',lambda:payload)
    def panel():
        import nfl_availability_ui
        nfl_availability_ui.render_availability('g')
    app=AppTest.from_function(panel).run()
    assert not app.exception and len(app.dataframe)==1


def test_detailed_nfl_card_does_not_advertise_a_reviewed_probability(monkeypatch):
    from pathlib import Path
    import overview_ui
    monkeypatch.setattr(overview_ui,'load_overview',lambda keys=None: {})
    # This state must remain testable even after the saved real-world slate ends.
    game='review_fixture'
    pred=pd.DataFrame([dict(game_id=game,home_team='LV',away_team='SEA',v4_pick='SEA',v3_pick='SEA',
                           v4_adjusted_confidence=.616,v4_core_confidence=.60,v3_confidence=.58,
                           prediction_status='EARLY_LOCK',qb_status_flag='')])
    read_csv=pd.read_csv
    def fixture_csv(path,*args,**kwargs):
        if isinstance(path,str) and path=='data/current/website_feed.csv':return pred.copy(deep=True)
        return read_csv(path,*args,**kwargs)
    monkeypatch.setattr(pd,'read_csv',fixture_csv)
    import streamlit as st
    st.cache_data.clear()
    monkeypatch.setattr(ui,'load_availability',lambda: {'games':{game:{'qb_review_required':True}}})
    app=AppTest.from_file(Path('app.py').resolve(),default_timeout=30).run()
    app.radio(key='bp_sport').set_value('NFL').run()
    app.radio(key='bp_board_view').set_value('Detailed').run()
    assert not app.exception
    card=next(m.value for m in app.markdown if 'class="card"' in m.value and game in m.value)
    assert 'QB INPUT NEEDS REVIEW' in card and '>Review<span>' in card
    assert 'LOCKED SNAPSHOT' not in card and 'ADJUSTED CONFIDENCE' in card
    assert 'class="model-strip"' not in card and 'class="fill"' not in card
    st.cache_data.clear()
    # Blank optional sections must not terminate the Markdown HTML block.
    assert not any(not line.strip() for line in card.splitlines())
