import copy
import numpy as np
import pandas as pd
import pytest
from develop import FEATURES
from test_develop import game
from prospective import capture, forecast_features, grade, summary, targets

NOW=pd.Timestamp('2026-10-14T00:00Z')


def schedule():
    return pd.DataFrame([dict(game_id=1,season=2027,season_type=2,date='2026-11-02T20:00Z',
        home_id=2,away_id=3,home_display_name='Home',away_display_name='Away',neutral_site=False,
        home_conference_id=8,away_conference_id=23,away_non_div1_team=False,time_valid=True,
        status_type_name='STATUS_SCHEDULED',status_type_completed=False,home_score=None,away_score=None)])


def bundle():
    return dict(version='test',features=FEATURES,imputer=[0.]*len(FEATURES),mean=[0.]*len(FEATURES),
                scale=[1.]*len(FEATURES),coefficients=[0.]*len(FEATURES),intercept=1.,
                calibration_coefficient=1.,calibration_intercept=0.)


def ledger():
    upcoming,_,_=targets(schedule(),NOW)
    frame=forecast_features([game('old','2025-11-01T12:00Z',season=2026)],upcoming,NOW)
    return capture([],frame,bundle(),'sha',NOW,'schedule-sha'),frame


def test_only_verified_regular_season_tipoffs_are_captured():
    s=schedule();extra=s.iloc[0].to_dict();extra.update(game_id=2,time_valid=False)
    third={**extra,'game_id':3,'time_valid':True,'season_type':1}
    unknown={**extra,'game_id':4,'time_valid':np.nan}
    rows,coverage,excluded=targets(pd.DataFrame([s.iloc[0].to_dict(),extra,third,unknown]),NOW)
    assert len(rows)==1 and coverage['source_games_in_horizon']==4
    assert excluded['tipoff_time_unconfirmed']==2 and excluded['not_target_regular_season']==1


def test_capture_is_immutable_and_future_targets_do_not_update_team_state():
    saved,frame=ledger();original=copy.deepcopy(saved)
    assert capture(saved,frame,{**bundle(),'intercept':-5.},'sha',NOW+pd.Timedelta(hours=1),'changed-source')==original
    upcoming,_,_=targets(schedule(),NOW)
    later={**upcoming[0],'game_id':'later','start':pd.Timestamp('2026-11-10T20:00Z'),'day':pd.Timestamp('2026-11-10T00:00Z')}
    first=forecast_features([],upcoming,NOW)
    both=forecast_features([],upcoming+[later],NOW)
    np.testing.assert_allclose(first[FEATURES].iloc[0].to_numpy(),both[FEATURES].iloc[1].to_numpy())


def test_live_feature_builder_matches_historical_replay():
    from develop import build_features
    past=[game('old','2025-11-01T12:00Z',home='2',away='3',season=2026)]
    target=game('1','2026-11-02T20:00Z',home='2',away='3',season=2027)
    historical=build_features(past+[target]).iloc[-1]
    upcoming,_,_=targets(schedule(),NOW)
    live=forecast_features(past,upcoming,NOW).iloc[0]
    np.testing.assert_allclose(historical[FEATURES].to_numpy(dtype=float),live[FEATURES].to_numpy(dtype=float))


def test_grading_requires_final_identity_and_pregame_capture():
    saved,_=ledger();s=schedule();final_time=pd.Timestamp('2026-11-03T04:00Z')
    pending,issues=grade(saved,s,final_time);assert pending==saved and not issues
    s.loc[0,['status_type_name','status_type_completed','home_score','away_score']]=['STATUS_FINAL',True,80,70]
    graded,issues=grade(saved,s,final_time);assert not issues and summary(graded)['wins']==1
    assert graded[0]['home_win_prob']==saved[0]['home_win_prob']
    s.loc[0,'home_score']=20
    unchanged,_=grade(graded,s,final_time);assert unchanged==graded
    wrong=s.copy();wrong.loc[0,'home_id']=9
    rejected,issues=grade(saved,wrong,final_time);assert rejected==saved and issues
    late=copy.deepcopy(saved);late[0]['created_at_utc']='2026-11-02T21:00Z'
    rejected,issues=grade(late,s,final_time);assert rejected==late and issues


@pytest.mark.parametrize('home_points,away_points',[(80,70),(65,78)])
def test_neutral_reversal_grades_scores_in_saved_orientation(home_points,away_points):
    saved,_=ledger();saved[0]['neutral_site']=True;original=copy.deepcopy(saved)
    s=schedule();s.loc[0,['neutral_site','status_type_name','status_type_completed','home_score','away_score']]=[True,'STATUS_FINAL',True,home_points,away_points]
    normal,issues=grade(saved,s,pd.Timestamp('2026-11-03T04:00Z'));assert not issues
    reverse=s.copy();reverse.loc[0,['home_id','away_id','home_score','away_score']]=[3,2,away_points,home_points]
    source_original=reverse.copy(deep=True)
    graded,issues=grade(saved,reverse,pd.Timestamp('2026-11-03T04:00Z'))
    assert not issues and graded==normal
    assert graded[0]['home_score']==home_points and graded[0]['away_score']==away_points
    assert graded[0]['actual_winner']==('Home' if home_points>away_points else 'Away')
    assert saved==original
    pd.testing.assert_frame_equal(reverse,source_original)
    for key,value in original[0].items():
        if key!='status':assert graded[0][key]==value
    assert grade(graded,s,pd.Timestamp('2026-11-04T04:00Z'))[0]==graded


def test_neutral_reversal_clears_pending_warning_without_changing_forecast():
    saved,_=ledger();saved[0]['neutral_site']=True
    s=schedule();s.loc[0,['neutral_site','home_id','away_id']]=[True,3,2]
    pending,issues=grade(saved,s,NOW)
    assert not issues and pending==saved


@pytest.mark.parametrize('saved_neutral,source_neutral',[(False,True),(True,False),(True,np.nan),(True,None)])
def test_reversal_requires_verified_neutral_venue_on_both_sides(saved_neutral,source_neutral):
    saved,_=ledger();saved[0]['neutral_site']=saved_neutral
    s=schedule();s['neutral_site']=s['neutral_site'].astype(object);s.loc[0,['neutral_site','home_id','away_id']]=[source_neutral,3,2]
    pending,issues=grade(saved,s,NOW)
    assert pending==saved and issues[0]['reason']=='result_identity_mismatch'


@pytest.mark.parametrize('field,value',[('home_id',9),('season',2026),('season_type',1)])
def test_neutral_reversal_still_rejects_different_teams_or_season(field,value):
    saved,_=ledger();saved[0]['neutral_site']=True
    s=schedule();s.loc[0,['neutral_site','home_id','away_id']]=[True,3,2];s.loc[0,field]=value
    pending,issues=grade(saved,s,NOW)
    assert pending==saved and issues[0]['reason']=='result_identity_mismatch'
