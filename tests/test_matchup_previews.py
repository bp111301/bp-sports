import copy
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from preview_data import game,profile,nhl_games,nba_games
from matchup_preview_ui import synopsis,valid_context


def test_profile_excludes_same_day_future_games_and_duplicates():
    earlier=game('CFB',1,'Notre Dame','Rice','2026-10-01T19:00Z',30,10,True)
    same_day=game('CFB',2,'Notre Dame','Stanford','2026-10-06T14:00Z',35,7,True)
    later=game('CFB',3,'Notre Dame','USC','2026-10-10T19:00Z',0,99,True)
    result=profile([earlier,earlier,same_day,later],'CFB','Notre Dame','2026-10-06T20:00Z','2026-10-10T19:00Z')
    assert result['games']==1 and result['wins']==1 and result['last']['opponent']=='Rice'
    assert result['scored_per_game']==30


def test_preseason_and_nonfinal_results_never_enter_context():
    def nhl(kind,state):return {'id':1,'gameType':kind,'gameState':state,'startTimeUTC':'2026-10-01T19:00Z','homeTeam':{'abbrev':'SEA','score':3},'awayTeam':{'abbrev':'VGK','score':2}}
    assert nhl_games({'games':[nhl(1,'OFF'),nhl(2,'LIVE')]})==[]
    assert len(nhl_games({'games':[nhl(2,'OFF')]}))==1
    assert nba_games({'events':[{'seasonType':{'type':1}}]})==[]
    assert game('NFL',1,'DET','CHI','2026-10-01',float('nan'),10,True) is None


def test_context_cannot_explain_an_earlier_or_different_forecast():
    row={'home_team':'Notre Dame','away_team':'Stanford','snapshot_created_utc':'2026-10-06T12:00Z'}
    context={'sport':'CFB','home_team':'Notre Dame','away_team':'Stanford','cutoff_utc':'2026-10-07T12:00Z','start_time_utc':'2026-10-10T19:00Z'}
    assert valid_context(context,'CFB',row) is None
    context['cutoff_utc']='2026-10-06T12:00Z';assert valid_context(context,'CFB',row)==context
    context['away_team']='Rice';assert valid_context(context,'CFB',row) is None


def test_synopsis_uses_saved_probability_and_actual_form_without_mutation():
    r={'home_team':'Notre Dame','away_team':'Stanford','home_win_prob':.72};before=copy.deepcopy(r)
    games=[game('CFB',1,'Notre Dame','Rice','2026-10-01T19:00Z',30,10,True)]
    form=profile(games,'CFB','Notre Dame','2026-10-06T12:00Z','2026-10-10T19:00Z')
    context={'home_form':form,'away_form':None,'venue':'Notre Dame Stadium'}
    text=' '.join(synopsis('CFB',r,context))
    assert '72.0%' in text and '28.0%' in text and '30–10 win over Rice' in text and 'Notre Dame Stadium' in text
    assert r==before and 'quarterback' not in text.lower()


def test_nfl_flags_are_explained_and_missing_results_are_explicit():
    row={'home_team':'DET','away_team':'CHI','v4_pick':'DET','v4_adjusted_confidence':.6,'turnover_risk_flag':True}
    text=' '.join(synopsis('NFL',row))
    assert 'turnover matchup reduced confidence' in text and 'not available' in text


def test_board_navigation_requests_reset_but_filters_do_not():
    from tests.test_overview_ui import fixture
    with patch('overview_ui.load_overview',return_value=fixture()):
        at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=15).run()
        at.button(key='open_CFB').click().run()
        assert not at.exception and at.radio(key='bp_sport').value=='CFB'
        assert at.session_state['bp_navigation_revision']==1
        assert at.session_state['bp_navigation_rendered_revision']==1
        at.run();assert at.session_state['bp_navigation_revision']==1
        at.radio(key='bp_sport').set_value('NFL').run()
        assert not at.exception and at.session_state['bp_navigation_revision']==2
