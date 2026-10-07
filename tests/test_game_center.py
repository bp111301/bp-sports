import copy,json
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
from game_status import espn_game,nhl_game,display_state
from game_center_ui import score_html,context,favorites_mask,confidence_html
NOW=pd.Timestamp('2026-10-07T16:00:00Z')

def event(state='post',completed=True,season=2):
 return {'id':'1','season':{'type':season},'competitions':[{'date':'2026-10-07T00:00:00Z','status':{'type':{'state':state,'completed':completed,'name':'STATUS_FINAL','shortDetail':'Final'}},'competitors':[{'homeAway':'home','score':'55','team':{'location':'Troy','abbreviation':'TROY'}},{'homeAway':'away','score':'34','team':{'location':'Southern Mississippi','abbreviation':'USM'}}]}]}

def test_final_requires_source_confirmation_and_valid_scores():
 r=espn_game('CFB',event(),NOW.isoformat());assert r['state']=='final' and r['home_score']==55 and r['away_score']==34
 assert display_state(r,False,now=NOW)=='Final · awaiting grading'
 assert display_state(r,True,now=NOW)=='Final'
 e=event(completed=False);r=espn_game('CFB',e,NOW.isoformat());assert r['state']!='final'
 e=event();e['competitions'][0]['competitors'][0]['score']='nan';assert espn_game('CFB',e,NOW.isoformat()) is None
 assert espn_game('NBA',event(season=1),NOW.isoformat()) is None
 assert display_state(None,False,'2026-10-06T00:00:00Z',NOW)=='Status unavailable'

def test_live_and_scheduled_are_distinct_and_never_grade_a_pick():
 e=event('in',False);e['competitions'][0]['status']['type']['name']='STATUS_IN_PROGRESS';r=espn_game('CFB',e,NOW.isoformat());assert display_state(r,False,now=NOW)=='Live'
 e['competitions'][0]['status']['type'].update(state='pre',name='STATUS_SCHEDULED');r=espn_game('CFB',e,NOW.isoformat());assert r['home_score'] is None and display_state(r,False,now=NOW)=='Scheduled'
 assert 'actual_home_win' not in r

def test_nhl_extra_time_final_and_nonregular_guard():
 p={'id':9,'gameType':2,'gameState':'OFF','homeTeam':{'abbrev':'SEA','score':2},'awayTeam':{'abbrev':'VGK','score':3},'startTimeUTC':'2026-10-07T02:00:00Z'}
 assert nhl_game(p,NOW.isoformat())['away_score']==3
 p['gameType']=1;assert nhl_game(p,NOW.isoformat()) is None

def test_score_identity_guard_escaping_staleness_and_final_not_counted_as_grade():
 r=espn_game('CFB',event(),NOW.isoformat());feed={'games':{'CFB:1':r}};before=copy.deepcopy(feed)
 rendered=score_html('CFB','1','Troy','Southern Mississippi',False,now=NOW,feed=feed)
 assert '55' in rendered and '34' in rendered and 'awaiting grading' in rendered and 'Source' in rendered
 assert context('CFB','1','Notre Dame','Stanford',feed) is None
 assert feed==before
 r.update(state='live',checked_at_utc='2026-10-07T14:00:00Z');assert 'update delayed' in score_html('CFB','1','Troy','Southern Mississippi',now=NOW,feed=feed)
 bad={**r,'sport':'NHL','home_team':'SEA','away_team':'<script>'};assert '&lt;script&gt;' in score_html('NHL','9','SEA','<script>',now=NOW,feed={'games':{'NHL:9':bad}})

def test_favorites_match_sport_and_alias_without_mutating_predictions():
 frame=pd.DataFrame([{'sport':'NFL','home':'DET','away':'CHI','p':.6},{'sport':'NBA','home':'DET','away':'BOS','p':.7},{'sport':'CFB','home':'Texas Tech','away':'Houston','p':.8}]);before=frame.copy(deep=True)
 m=favorites_mask(frame,None,'home','away',['NFL:DET','CFB:Texas Tech']);assert list(m)==[True,False,True]
 pd.testing.assert_frame_equal(frame,before)
 assert '10.0%' in confidence_html(.9,'CFB') and 'Unusually high' in confidence_html(.9,'CFB')
 assert 'missing power-play' in confidence_html(.9236,'NHL',True)

def test_preferences_bookmark_roundtrip_and_cfb_completed_scores():
 from tests.test_overview_ui import fixture
 with patch('overview_ui.load_overview',return_value=fixture()),patch('game_center_ui.load_scores',return_value={}):
  at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=20).run();assert not at.exception
  at.multiselect(key='bp_favorites').set_value(['NFL:DET','CFB:Texas Tech']).run();assert 'NFL:DET' in str(at.query_params['teams'])
  at.toggle(key='overview_my_teams').set_value(True).run();assert not at.exception
  at.button(key='open_CFB').click().run();assert not at.exception
  at.selectbox(key='cfb_games_view').select('2026-10-06').run();assert not at.exception
  assert any('Troy' in m.value and 'bp-score' in m.value for m in at.markdown)
  at.toggle(key='cfb_my_teams').set_value(True).run();assert not at.exception
  assert any('No games match' in x.value for x in at.info)
