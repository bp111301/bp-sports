import copy
import pandas as pd
from game_status import espn_game,nhl_game
from recap_data import espn_recap,nhl_recap,recap_paragraphs
from matchup_preview_ui import valid_latest_context

NOW='2026-10-15T12:00:00Z'

def summary():
    event={'id':'1','season':{'type':2},'competitions':[{'date':'2026-10-14T23:00Z','status':{'type':{'state':'post','completed':True,'shortDetail':'Final'}},'competitors':[
        {'homeAway':'home','score':'3','team':{'location':'Sam Houston'},'linescores':[{'value':0},{'value':3},{'value':0},{'value':0}]},
        {'homeAway':'away','score':'16','team':{'location':'Western Kentucky'},'linescores':[{'value':7},{'value':3},{'value':3},{'value':3}]}]}]}
    box={'teams':[{'team':{'location':'Sam Houston'},'statistics':[{'name':'totalYards','displayValue':'177'},{'name':'turnovers','displayValue':'1'}]},
                  {'team':{'location':'Western Kentucky'},'statistics':[{'name':'totalYards','displayValue':'276'},{'name':'turnovers','displayValue':'0'}]}],
         'players':[{'team':{'location':'Western Kentucky'},'statistics':[{'name':'passing','keys':['passingYards','passingTouchdowns'],'athletes':[{'athlete':{'displayName':'Example QB'},'stats':['127','1']}]}]}]}
    return {'header':event,'boxscore':box}

def test_verified_recap_uses_box_score_and_actual_game_flow_without_mutation():
    p=summary();before=copy.deepcopy(p);expected=espn_game('CFB',p['header'],NOW)
    r=espn_recap('CFB',p,expected,NOW);text=' '.join(recap_paragraphs(r))
    assert 'Western Kentucky beat Sam Houston 16–3' in text and 'led 10–3 at halftime' in text
    assert '276 total yards' in text and '177' in text and 'Example QB' in text
    assert p==before and 'prob' not in r and 'correct' not in r

def test_nonfinal_preseason_identity_and_score_mismatch_never_get_detailed_recaps():
    p=summary();expected=espn_game('CFB',p['header'],NOW)
    for changes in ({'home_team':'Notre Dame'},{'home_score':99},{'start_time_utc':'2026-10-13T23:00Z'}):
        assert espn_recap('CFB',p,{**expected,**changes},NOW) is None
    p['header']['competitions'][0]['status']['type']['completed']=False
    assert espn_recap('CFB',p,expected,NOW) is None
    p=summary();p['header']['season']['type']=1
    assert espn_recap('CFB',p,expected,NOW) is None

def test_missing_detail_is_explicit_and_never_invents_a_story():
    p=summary();p['boxscore']={};p['header']['competitions'][0]['competitors'][0]['linescores']=[]
    expected=espn_game('CFB',p['header'],NOW);text=' '.join(recap_paragraphs(espn_recap('CFB',p,expected,NOW)))
    assert 'fuller recap is pending' in text and 'halftime' not in text and 'comeback' not in text

def test_hockey_overtime_shootout_and_goalie_stats_are_sourced():
    p={'id':2,'gameType':2,'gameState':'OFF','startTimeUTC':'2026-10-14T23:00Z','periodDescriptor':{'periodType':'OT'},
       'homeTeam':{'abbrev':'DET','score':3,'sog':31},'awayTeam':{'abbrev':'BUF','score':2,'sog':25},
       'playerByGameStats':{'homeTeam':{'goalies':[{'name':{'default':'Example Goalie'},'saves':23,'shotsAgainst':25}]}}}
    expected=nhl_game(p,NOW);r=nhl_recap(p,expected,NOW);text=' '.join(recap_paragraphs(r))
    assert 'in overtime' in text and '23 of 25' in text and '31 shots on goal' in text
    p['periodDescriptor']['periodType']='SO';assert 'in a shootout' in ' '.join(recap_paragraphs(nhl_recap(p,expected,NOW)))

def test_latest_editorial_context_can_follow_prediction_but_must_remain_pregame():
    row={'game_id':'1','home_team':'DET','away_team':'CHI','captured_at_utc':'2026-10-12T12:00Z'}
    c={'game_id':'1','sport':'NFL','home_team':'DET','away_team':'CHI','cutoff_utc':'2026-10-15T12:00Z','start_time_utc':'2026-10-18T17:00Z'}
    assert valid_latest_context(c,'NFL',row,NOW)==c
    for changes in ({'cutoff_utc':'2026-10-18T17:00Z'},{'cutoff_utc':'2026-10-16T12:00Z'},{'game_id':'2'},{'home_team':'GB'}):
        assert valid_latest_context({**c,**changes},'NFL',row,NOW) is None
