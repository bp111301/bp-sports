import copy
from datetime import date
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import overview_ui as ov
from matchup_details_ui import detail_payload

NOW=pd.Timestamp('2026-10-07T17:00:00Z')

def test_saved_details_keep_probabilities_and_grade_separate_from_score_source():
 r={'game_id':'1','home_team':'Troy','away_team':'Southern Mississippi','home_win_prob':.716,'snapshot_created_utc':'2026-10-06T03:00:00Z','kickoff_utc':'2026-10-07T00:00:00Z','correct':1,'_settled':True}
 before=copy.deepcopy(r);d=detail_payload('CFB',r);assert d['pick']=='Troy' and d['prob']==.716 and d['result']=='Win' and r==before
 r.update(correct=None,_settled=False);assert detail_payload('CFB',r)['result'].startswith('Pending')
 r['home_win_prob']=float('nan')
 with pytest.raises(ValueError):detail_payload('CFB',r)

def test_overview_details_preserve_original_nfl_flags_and_timestamp():
 source={'v4_pick':'DET','v4_adjusted_confidence':.7,'turnover_risk_flag':True,'captured_at_utc':'2026-10-06T03:00:00Z'}
 r=ov.row('nfl1','NFL','nfl','DET','CHI',.7,source['captured_at_utc'],'2026-10-11T17:00:00Z',details=source)
 d=detail_payload('NFL',r);assert d['prob']==.7 and d['preview']['turnover_risk_flag'] is True and d['preview']['captured_at_utc']==pd.Timestamp(source['captured_at_utc'])

def test_central_date_uses_game_night_and_counts_one_primary_forecast():
 rows=[ov.row('h','NHL',g,'SEA','VGK',.92,'2026-10-06T10:00:00Z','2026-10-07T02:00:00Z',True,0) for g in ['reference_control','decay2_logistic','linear_regulation_blend']]
 rows.extend([ov.row('c','CFB','cfb','Troy','SM',.7,'2026-10-06T10:00:00Z','2026-10-07T00:00:00Z',True,1),ov.row('p','NHL','reference_control','DET','OTT',.6,'2026-10-06T10:00:00Z','2026-10-07T04:59:00Z'),ov.row('next','NHL','reference_control','TOR','NSH',.6,'2026-10-06T10:00:00Z','2026-10-07T05:01:00Z')])
 board=pd.DataFrame(rows);before=board.copy(deep=True);shown=ov.select_day(board,date(2026,10,6));m=ov.metrics(shown)
 assert set(shown.game_id)=={'h','c','p'} and m['games']==2 and m['wins']==1 and m['losses']==1 and m['accuracy']==.5
 assert list(ov.select_day(board,date(2026,10,6),'CFB').game_id)==['c']
 assert list(ov.select_day(board,date(2026,10,7)).game_id)==['next']
 pd.testing.assert_frame_equal(board,before)

def test_daily_results_and_game_dialog_work_from_overview():
 from tests.test_overview_ui import fixture
 with patch('overview_ui.load_overview',return_value=fixture()),patch('game_center_ui.load_scores',return_value={}):
  at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=20).run();assert not at.exception
  assert 'DAILY RESULTS' in [t.label for t in at.tabs]
  assert at.date_input(key='daily_date').value is not None
  at.selectbox(key='daily_sport').select('CFB').run();assert not at.exception
  at.button(key='daily_details_CFB_cfb1').click().run();assert not at.exception
  assert any('Matchup synopsis' in m.value for m in at.markdown)
  assert any('Saved pick result: Win' in x.value for x in at.success)
  assert any(m.label=='Saved confidence' and m.value=='70.0%' for m in at.metric)

def test_cfb_completed_board_opens_same_detail_view():
 from tests.test_overview_ui import fixture
 with patch('overview_ui.load_overview',return_value=fixture()):
  at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=20).run()
  at.button(key='open_CFB').click().run();at.selectbox(key='cfb_games_view').select('2026-10-06').run();assert not at.exception
  buttons=[b for b in at.button if b.label.startswith('Game details')];assert len(buttons)==1
  buttons[0].click().run();assert not at.exception
  assert any('Saved pick result: Win' in x.value for x in at.success)
  assert any('55' in m.value and '34' in m.value and 'bp-score' in m.value for m in at.markdown)
