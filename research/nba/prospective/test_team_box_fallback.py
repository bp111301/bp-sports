import copy
import io
import json
from pathlib import Path
import pandas as pd
import pytest
from team_box_fallback import complete_boxes, summary_pair, COLUMNS
from capture_health import failure_reason

def payload():
    return json.loads((Path(__file__).parent/'fixtures/final_team_box.json').read_text())

def game():
    return dict(game_id=401909093,season=2027,season_type=2,date='2026-10-22T23:00Z',
        home_id=20,away_id=5,home_score=114,away_score=106,home_abbreviation='PHI',away_abbreviation='CLE',
        status_type_state='post',status_type_completed=True,neutral_site=False,notes_headline='')

def test_final_summary_matches_archive_schema_and_turnover_definition():
    rows=summary_pair(payload(),game());sides={r['team_home_away']:r for r in rows}
    assert sides['home']['turnovers']==16  # frozen archive uses player turnovers, not total/team turnovers
    assert sides['away']['turnovers']==21
    assert sides['home']['team_score']==114 and sides['away']['team_score']==106
    assert set(rows[0])==set(COLUMNS)

@pytest.mark.parametrize('change',['live','wrong_game','wrong_season','wrong_home','score','missing_stat','points'])
def test_unverified_summary_cannot_enter_history(change):
    p=payload();c=p['header']['competitions'][0]
    if change=='live': c['status']['type'].update(completed=False,state='in')
    elif change=='wrong_game': p['header']['id']='999'
    elif change=='wrong_season': p['header']['season']['type']=1
    elif change=='wrong_home': c['competitors'][0]['team']['id']='1'
    elif change=='score': c['competitors'][0]['score']='115'
    elif change=='missing_stat': p['boxscore']['teams'][0]['statistics']=[]
    elif change=='points': p['boxscore']['teams'][0]['statistics'][0]['displayValue']='38-87'
    with pytest.raises((ValueError,KeyError)): summary_pair(p,game())

def test_fallback_cache_is_append_only_and_validated_again(tmp_path):
    schedule=pd.DataFrame([game()]);original=schedule.copy(deep=True);calls=[]
    def fetch(url): calls.append(url);return json.dumps(payload()).encode()
    path=tmp_path/'boxes.jsonl'
    fixed=complete_boxes(schedule,None,fetch,path);before=path.read_bytes()
    assert len(pd.read_parquet(io.BytesIO(fixed)))==2 and len(calls)==1
    cached=complete_boxes(schedule,None,fetch,path)
    assert len(calls)==1 and path.read_bytes()==before
    pd.testing.assert_frame_equal(pd.read_parquet(io.BytesIO(fixed)),pd.read_parquet(io.BytesIO(cached)))
    pd.testing.assert_frame_equal(schedule,original)
    with pytest.raises(ValueError): complete_boxes(pd.DataFrame([{**game(),'home_score':115}]),None,fetch,path)
    assert path.read_bytes()==before

def test_valid_archive_is_used_without_source_call_and_same_history_features(tmp_path):
    import run as live
    rows=summary_pair(payload(),game());buf=io.BytesIO();pd.DataFrame(rows).to_parquet(buf,index=False)
    schedule=pd.DataFrame([game()])
    def unexpected(url): raise AssertionError('Valid archive should not need fallback')
    kept=complete_boxes(schedule,buf.getvalue(),unexpected)
    fetched=complete_boxes(schedule,None,lambda url:json.dumps(payload()).encode(),tmp_path/'cache.jsonl')
    left=live.current_history(schedule,kept);right=live.current_history(schedule,fetched)
    pd.testing.assert_frame_equal(left,right)
    pd.testing.assert_frame_equal(live.build_features(left),live.build_features(right))

def test_health_fails_for_silent_forecast_block_and_missing_games():
    good=dict(feed_status='enabled',operational_status='ready',prediction_blocked_reason=None,missing_upcoming_game_ids=[])
    assert failure_reason(good) is None
    assert failure_reason({**good,'prediction_blocked_reason':'Waiting for team boxes'})
    assert failure_reason({**good,'missing_upcoming_game_ids':['401909100']})
    assert failure_reason({**good,'operational_status':'blocked'})
