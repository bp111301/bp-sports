from pathlib import Path
from unittest.mock import patch
import copy
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import overview_ui as ov
NOW=pd.Timestamp.now(tz='UTC')
def fixture():
 created=(NOW-pd.Timedelta(days=2)).isoformat();past=(NOW-pd.Timedelta(days=1)).isoformat();future=(NOW+pd.Timedelta(hours=1)).isoformat()
 nfl=dict(game_id='nfl1',home_team='DET',away_team='CHI',v4_pick='DET',v4_adjusted_confidence=.6,captured_at_utc=created,settlement_status='final',actual_home_score=24,actual_away_score=10)
 cfb=dict(game_id='cfb1',home_team='Troy',away_team='Southern Mississippi',home_win_prob=.7,predicted_winner='Troy',snapshot_created_utc=created,kickoff_utc=past,schedule_kickoff_utc=past,correct=1,actual_winner='Troy')
 nhl=[dict(game_id='nhl1',home_team='TOR',away_team='NSH',candidate=k,home_win_prob=.6,created_at_utc=created,start_time_utc=future,status='pending',actual_home_win=None,bundle_sha256=ov.FROZEN_NHL) for k in ('reference_control','decay2_logistic','linear_regulation_blend')]
 data={'nfl':[nfl,{**nfl,'captured_at_utc':past,'v4_adjusted_confidence':.9}],'cfb':[cfb],'shadow':[],'nhl':nhl,'goalie':[], 'nba':dict(feed_status='enabled',bundle_sha256=ov.FROZEN_NBA,updated_at_utc=created,predictions=[]),'nfl_update':dict(captured_at_utc=created),'cfb_update':dict(generated_at_utc=created),'shadow_update':{},'nhl_update':dict(as_of_utc=created),'goalie_update':dict(as_of_utc=created)}
 return {k:dict(ok=True,data=v) for k,v in data.items()}

def test_repeated_nfl_updates_and_parallel_nhl_models_do_not_inflate_primary_record():
 board,available,updates=ov.prepare(fixture(),NOW);assert len(board[board.group=='nfl'])==1
 assert ov.metrics(board[board.group=='nfl'])['wins']==1
 assert board[board.group=='nfl'].iloc[0].p==.6
 primary=board[board.apply(lambda r:ov.PRIMARY[r.sport]==r.group,axis=1)];assert len(primary)==3 and ov.metrics(primary)['games']==2

def test_late_snapshots_and_future_settlements_excluded():
 data=fixture()['nhl']['data'];late=copy.deepcopy(data[0]);late['created_at_utc']=late['start_time_utc'];assert ov.normalize('nhl',[late],NOW)==[]
 future=copy.deepcopy(data[0]);future.update(status='settled',actual_home_win=1);assert ov.normalize('nhl',[future],NOW)==[]

def test_nba_wrong_model_and_legacy_shadow_not_accepted():
 with pytest.raises(ValueError):ov.normalize('nba',dict(feed_status='enabled',bundle_sha256='wrong',predictions=[]),NOW)
 r=fixture()['cfb']['data'][0];r.update(settled=False,bundle_sha256=ov.FROZEN_SHADOW,bundle_frozen_at_utc=NOW.isoformat());assert ov.normalize('shadow',[r],NOW)==[]


def test_metrics_use_saved_probability_and_confidence_not_pending_outcomes():
 board,_,_=ov.prepare(fixture(),NOW);m=ov.metrics(board[board.group=='cfb']);assert m['games']==1 and m['brier']==pytest.approx(.09)
 assert ov.metrics(board[board.group=='reference_control'])['accuracy'] is None

def test_unavailable_sport_remains_unknown_and_navigation_works():
 data=fixture();data['cfb']={'ok':False,'data':None}
 with patch('overview_ui.load_overview',return_value=data):
  at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=15).run();assert not at.exception
  assert at.radio(key='bp_sport').value=='Overview'
  assert any('unavailable for CFB' in w.value for w in at.warning)
  assert any('Official prospective record' in m.value and 'Feed unavailable' in m.value for m in at.markdown)
  assert not any('historical test' in m.value.lower() for m in at.markdown)
  at.button(key='open_NFL').click().run();assert at.radio(key='bp_sport').value=='NFL' and not at.exception

def test_tonight_uses_verified_cfb_schedule_instead_of_original_placeholder():
 data=fixture();r=data['cfb']['data'][0];r.update(correct=None,actual_winner=None,kickoff_utc=(NOW-pd.Timedelta(days=1)).isoformat(),schedule_kickoff_utc=(NOW+pd.Timedelta(hours=1)).isoformat())
 board,_,_=ov.prepare(data,NOW);assert board[board.group=='cfb'].iloc[0].start==NOW+pd.Timedelta(hours=1)

def test_game_center_separates_today_results_and_pending_at_central_midnight():
    now=pd.Timestamp('2026-10-07T04:30:00Z')
    rows=[ov.row('a','NHL','reference_control','SEA','VGK',.92,now-pd.Timedelta(days=1),now-pd.Timedelta(hours=2),True,0),ov.row('b','CFB','cfb','Troy','SM',.7,now-pd.Timedelta(days=1),now-pd.Timedelta(minutes=5)),ov.row('c','NHL','reference_control','DET','OTT',.6,now-pd.Timedelta(days=1),now+pd.Timedelta(hours=2))]
    board=pd.DataFrame(rows);board['confidence']=board.p.where(board.p.ge(.5),1-board.p)
    assert list(ov.select_games(board,'Today','All sports','',now).game_id)==['a','b']
    assert list(ov.select_games(board,'Results','All sports','',now).game_id)==['a']
    assert list(ov.select_games(board,'Awaiting finals','All sports','',now).game_id)==['b']
    assert list(ov.select_games(board,'Upcoming','NHL','det',now).game_id)==['c']
    html=ov.game_cards(board,now)
    assert 'desk-state loss' in html and 'Final winner: VGK' in html
    assert 'Awaiting final' in html and 'Result pending · excluded from record' in html

def test_game_cards_escape_teams_and_show_audit_without_changing_probability():
    now=pd.Timestamp('2026-10-07T14:00:00Z')
    r=ov.row('2026020051','NHL','reference_control','SEA','<script>',.923646349229591,now-pd.Timedelta(days=1),now-pd.Timedelta(hours=12),True,0)
    board=pd.DataFrame([r]);board['confidence']=board.p
    html=ov.game_cards(board,now)
    assert '&lt;script&gt;' in html and '<script>' not in html
    assert '92.4%' in html and 'missing power-play feature' in html and 'desk-state loss' in html
    assert board.iloc[0].p==.923646349229591
