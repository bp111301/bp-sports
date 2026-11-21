"""New saved NFL picks must not wait for the independent preview refresh."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from compact_board_ui import prepare_compact
from game_status import nfl_saved_start
from overview_ui import prepare

NOW=pd.Timestamp('2026-11-21T16:00Z')
START='2026-11-22T18:00Z'


def fixture():
    game='2026_11_NE_DET'
    availability={'games':{game:dict(kickoff_utc=START,home=dict(team='DET'),away=dict(team='NE'))}}
    prediction=dict(game_id=game,home_team='DET',away_team='NE',v4_pick='DET',v4_adjusted_confidence=.65,
                    captured_at_utc='2026-11-21T15:00Z',settlement_status='pending')
    return game,availability,prediction


def test_overview_and_board_keep_saved_forecasts_visible_without_a_score_or_preview():
    game,schedule,prediction=fixture()
    payload={'nfl':dict(ok=True,data=[prediction]),'nfl_availability':dict(ok=True,data=schedule)}
    original=copy.deepcopy(payload)
    overview,_,_=prepare(payload,NOW)
    compact,_=prepare_compact('NFL',payload,{},NOW)
    assert overview.iloc[0].start==compact.iloc[0].start==pd.Timestamp(START)
    assert compact.iloc[0].date=='2026-11-22'
    assert overview.iloc[0].p==compact.iloc[0].p==.65
    assert not overview.iloc[0].settled and payload==original


def test_wrong_team_missing_or_invalid_schedule_does_not_fabricate_a_start():
    game,schedule,_=fixture()
    assert pd.isna(nfl_saved_start(game,'BUF','NE',schedule))
    assert pd.isna(nfl_saved_start('different','DET','NE',schedule))
    assert pd.isna(nfl_saved_start(game,'DET','NE',None))
    schedule['games'][game]['kickoff_utc']='bad date'
    assert pd.isna(nfl_saved_start(game,'DET','NE',schedule))


def test_verified_score_start_still_takes_precedence():
    game,schedule,prediction=fixture()
    payload={'nfl':dict(ok=True,data=[prediction]),'nfl_availability':dict(ok=True,data=schedule)}
    actual='2026-11-22T18:15Z'
    feed={'games':{'NFL:'+game:dict(sport='NFL',state='scheduled',home_team='DET',away_team='NE',start_time_utc=actual)}}
    compact,_=prepare_compact('NFL',payload,feed,NOW)
    assert compact.iloc[0].start==pd.Timestamp(actual)


def test_score_archive_can_resolve_new_nfl_games_before_previews_are_generated(tmp_path,monkeypatch):
    game,schedule,prediction=fixture()
    data=tmp_path/'data';(data/'ledger').mkdir(parents=True);(data/'current').mkdir()
    (data/'cfb/ledger').mkdir(parents=True)
    pd.DataFrame([prediction]).to_csv(data/'ledger/prediction_ledger.csv',index=False)
    pd.DataFrame(columns=['game_id','home_team','away_team','kickoff_utc']).to_csv(data/'cfb/ledger/prediction_ledger.csv',index=False)
    (data/'matchup_previews.json').write_text(json.dumps(dict(games={})))
    (data/'current/nfl_availability.json').write_text(json.dumps(schedule))
    spec=importlib.util.spec_from_file_location('score_archive',Path('pipeline/build_game_status.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    monkeypatch.setattr(module,'get',lambda url:SimpleNamespace(text='game_id,home_team,away_team,start_time_utc\n',json=lambda:dict(feed_status='enabled',predictions=[])))
    rows,errors=module.targets()
    assert errors==[] and rows[0]['game_id']==game and rows[0]['start_time_utc']==pd.Timestamp(START)
