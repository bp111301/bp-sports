import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copy
import pandas as pd
import pytest
import run as live

NOW = pd.Timestamp('2026-10-25T08:00:00Z')
def game(gid='1', day='2026-10-24', y=1):
    return dict(game_id=gid,season=2027,date=day,start_time=day+'T23:00:00Z',home_id='1',away_id='2',home_team='ATL',away_team='BOS',neutral=False,y=y,home_score=110,away_score=100,home_stats=[110,100,100,.5,.1,.2,.2,y],away_stats=[100,110,100,.5,.1,.2,.2,1-y])
def schedule():
    return dict(game_id=2,season=2027,season_type=2,date='2026-10-25T23:00Z',home_id=1,away_id=2,home_abbreviation='ATL',away_abbreviation='BOS',neutral_site=False,notes_headline='',status_type_state='pre',status_type_completed=False,home_score=0,away_score=0)
def prediction():
    return dict(game_id='2',season=2027,season_type=2,home_id='1',away_id='2',bundle_sha256='fixed',created_at_utc='2026-10-25T08:00Z',start_time_utc='2026-10-25T23:00Z',history_cutoff='2026-10-24',home_win_prob=.6)

def test_future_and_same_date_outcomes_cannot_change_forecast():
    r=schedule(); history=pd.DataFrame([game()])
    first,_=live.forecast_features(history,r)
    extra=game('3','2026-10-25',0); extra['home_id']='3';extra['away_id']='4'
    later=game('4','2026-10-26',0)
    second,_=live.forecast_features(pd.concat([history,pd.DataFrame([extra,later])]),r)
    assert first[live.FEATURES].tolist()==second[live.FEATURES].tolist()

def test_forecast_features_match_original_date_batched_engine():
    history=pd.DataFrame([game()]); r=schedule(); f,_=live.forecast_features(history,r)
    known=game('2','2026-10-25',1)
    original=live.build_features(pd.concat([history,pd.DataFrame([known])])).iloc[-1]
    assert f[live.FEATURES].tolist()==original[live.FEATURES].tolist()

def test_preseason_playoffs_and_cup_final_excluded():
    r=schedule(); assert live.regular(r)
    for update in [dict(season_type=1),dict(season_type=3),dict(season=2026),dict(home_id=100),dict(notes_headline='NBA Cup Championship')]:
        assert not live.regular({**r,**update})

def test_settlement_requires_final_valid_pregame_and_matching_teams():
    p=prediction(); r=schedule(); now=pd.Timestamp('2026-10-26T08:00Z')
    assert not live.settle([p],[],pd.DataFrame([r]),now)
    r.update(status_type_state='post',status_type_completed=True,home_score=120,away_score=110)
    result=live.settle([p],[],pd.DataFrame([r]),now); assert result[0]['actual_home_win']==1
    assert not live.settle([p],result,pd.DataFrame([r]),now)
    assert not live.settle([p],[],pd.DataFrame([{**r,'date':'2026-10-25T07:00Z'}]),now)
    assert not live.settle([p],[],pd.DataFrame([{**r,'away_score':120}]),now)
    with pytest.raises(AssertionError):live.settle([p],[],pd.DataFrame([{**r,'home_id':3}]),now)

def test_duplicate_or_post_tipoff_forecasts_are_rejected():
    p=prediction();live.validate([p],[],'fixed')
    with pytest.raises(AssertionError):live.validate([p,p],[],'fixed')
    with pytest.raises(AssertionError):live.validate([{**p,'created_at_utc':p['start_time_utc']}],[],'fixed')
    with pytest.raises(AssertionError):live.validate([p],[],'different')

def test_completed_games_without_boxes_block_new_predictions():
    r=schedule();r.update(status_type_state='post',status_type_completed=True,home_score=100,away_score=90)
    with pytest.raises(ValueError):live.current_history(pd.DataFrame([r]),None)
    assert live.current_history(pd.DataFrame([schedule()]),None).empty

def test_logs_append_without_changing_original_forecast(tmp_path):
    path=tmp_path/'predictions.jsonl';p=prediction();live.append(path,[p]);first=path.read_bytes()
    live.append(path,[{**p,'game_id':'3'}]); assert path.read_bytes().startswith(first)
    assert live.read_log(path)[0]==p
