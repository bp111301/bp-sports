import copy
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from run import VARIANTS, ADJUSTED, ROTATION, prospective_extra_features
from freeze_shadow import fit
from shadow import capture_pairs,grade_pairs,paired_summary,forecast_frame,validate_pairs
import develop as v1

NOW=pd.Timestamp('2026-11-01T22:00Z')
IDS={'control':'control-hash','challenger':'challenger-hash','protocol':'protocol-hash'}


def bundle(features,version,intercept):
    return dict(version=version,features=features,imputer=[0.]*len(features),mean=[0.]*len(features),
                scale=[1.]*len(features),coefficients=[0.]*len(features),intercept=intercept,
                calibration_coefficient=1.,calibration_intercept=0.)


def target(gid='1',date='2026-11-02T20:00Z'):
    start=pd.Timestamp(date)
    return dict(game_id=gid,season=2027,start=start,day=start.floor('D'),home_id='2',away_id='3',
                home='Home',away='Away',neutral=False,forecast=True,y=np.nan,home_score=np.nan,away_score=np.nan,values={})


def pairs():
    frame=forecast_frame([], [target()], {}, NOW)
    return capture_pairs([],frame,bundle(v1.FEATURES,'V1',1.),bundle(VARIANTS['combined'],'shadow',-1.),IDS,NOW,'schedule-hash'),frame


def schedule():
    return pd.DataFrame([dict(game_id=1,season=2027,season_type=2,date='2026-11-02T20:00Z',home_id=2,away_id=3,
                             status_type_name='STATUS_FINAL',status_type_completed=True,time_valid=True,home_score=80,away_score=70)])


def test_pairs_share_context_and_never_overwrite_first_capture():
    ledger,frame=pairs();original=copy.deepcopy(ledger)
    again=capture_pairs(ledger,frame,bundle(v1.FEATURES,'V1',-5.),bundle(VARIANTS['combined'],'shadow',5.),IDS,NOW+pd.Timedelta(hours=1),'new-source')
    assert again==original
    assert ledger[0]['control']['created_at_utc']==ledger[0]['challenger']['created_at_utc']
    assert ledger[0]['control']['features']=={k:ledger[0]['challenger']['features'][k] for k in v1.FEATURES}
    assert not ledger[0]['roster_context']['home_known'] and not ledger[0]['roster_context']['away_known']


def test_changed_model_identity_or_post_tipoff_capture_rejected():
    ledger,frame=pairs()
    with pytest.raises(ValueError,match='model identity'):
        capture_pairs(ledger,frame,bundle(v1.FEATURES,'V1',1.),bundle(VARIANTS['combined'],'shadow',1.),{**IDS,'challenger':'changed'},NOW,'s')
    with pytest.raises(ValueError,match='Post-tipoff'):
        capture_pairs([],frame,bundle(v1.FEATURES,'V1',1.),bundle(VARIANTS['combined'],'shadow',1.),IDS,pd.Timestamp('2026-11-03T00:00Z'),'s')
    with pytest.raises(ValueError,match='24-hour'):
        capture_pairs([],frame,bundle(v1.FEATURES,'V1',1.),bundle(VARIANTS['combined'],'shadow',1.),IDS,pd.Timestamp('2026-10-16T00:00Z'),'s')


def test_paired_grading_uses_only_same_verified_final_and_is_immutable():
    ledger,_=pairs();final=schedule();after=pd.Timestamp('2026-11-03T04:00Z')
    graded,issues=grade_pairs(ledger,final,after,IDS)
    assert not issues
    result=paired_summary(graded)
    assert result['settled_pairs']==1 and result['control']['wins']==1 and result['challenger']['losses']==1
    assert result['challenger_minus_control']['accuracy']==-1
    final.loc[0,'home_score']=20
    assert grade_pairs(graded,final,after,IDS)[0]==graded


def test_wrong_identity_pending_game_or_invalid_final_does_not_settle():
    ledger,_=pairs();after=pd.Timestamp('2026-11-03T04:00Z')
    for change in [dict(home_id=99),dict(home_score=70),dict(time_valid=False),dict(status_type_name='STATUS_IN_PROGRESS')]:
        final=schedule()
        for key,value in change.items():final.loc[0,key]=value
        graded,_=grade_pairs(ledger,final,after,IDS)
        assert graded==ledger and paired_summary(graded)['settled_pairs']==0


def test_one_sided_or_mismatched_capture_cannot_enter_paired_metrics():
    ledger,_=pairs();bad=copy.deepcopy(ledger)
    bad[0]['challenger']['created_at_utc']='2026-10-17T22:00:00+00:00'
    with pytest.raises(ValueError,match='context differs'):validate_pairs(bad,IDS)
    bad=copy.deepcopy(ledger);bad[0]['challenger']['status']='settled'
    with pytest.raises(ValueError,match='One-sided'):validate_pairs(bad,IDS)


def test_forecast_only_rows_cannot_update_opponent_or_roster_state():
    first=target();later=target('2','2026-11-10T20:00Z')
    alone=forecast_frame([],[later],{},NOW)
    both=forecast_frame([],[first,later],{('1','2'):{'invented':200.}},NOW)
    np.testing.assert_allclose(alone[VARIANTS['combined']].iloc[0],both[VARIANTS['combined']].iloc[1])
    assert not both.iloc[1].home_rotation_known


def test_forward_state_matches_historical_feature_replay():
    from test_develop import game
    old=game('old','2025-11-02T20:00Z',home='2',away='3',season=2026)
    future=target()
    frame=forecast_frame([old],[future],{('old','2'):{'returner':200.}},NOW)
    replay=v1.build_features([old,{**game('1','2026-11-02T20:00Z',home='2',away='3',season=2027)}]).iloc[-1]
    np.testing.assert_allclose(frame[v1.FEATURES].iloc[0].to_numpy(float),replay[v1.FEATURES].to_numpy(float))
    from run import _extra_features
    historical_target=game('1','2026-11-02T20:00Z',home='2',away='3',season=2027)
    extra_replay=_extra_features([old,historical_target],{('old','2'):{'returner':200.}}).iloc[-1]
    np.testing.assert_allclose(frame[ADJUSTED+ROTATION].iloc[0].to_numpy(float),extra_replay[ADJUSTED+ROTATION].to_numpy(float))
    assert frame.iloc[0].adjusted_off_diff != 0
    assert not frame.iloc[0].home_rotation_known


def test_actual_prior_appearance_enables_rotation_after_embargo_only():
    from test_develop import game
    old=game('old','2025-11-02T20:00Z',home='2',away='3',season=2026)
    recent=game('first','2026-11-02T20:00Z',home='2',away='3',season=2027)
    later=target('next','2026-11-05T20:00Z')
    frame=forecast_frame([old,recent],[later],{('old','2'):{'returner':200.},('first','2'):{'returner':200.}},pd.Timestamp('2026-11-04T20:00Z'))
    assert frame.iloc[0].home_rotation_known
    assert frame.iloc[0].returning_share_diff==.5


def test_shadow_fit_rejects_2026_outcomes_and_portable_inference_matches():
    root=Path(__file__).parent;lock=json.loads((root/'SHADOW_LOCK.json').read_text())
    rng=np.random.default_rng(0);records=[]
    for season in range(2020,2026):
        for i in range(12):records.append(dict(season=season,y=i%2,**dict(zip(VARIANTS['combined'],rng.normal(size=len(VARIANTS['combined']))))))
    frame=pd.DataFrame(records);frozen=fit(frame,lock)
    assert frozen['training_seasons']==list(range(2020,2025)) and frozen['calibration_season']==2025
    frame.loc[0,'season']=2026
    with pytest.raises(ValueError,match='No 2026'):fit(frame,lock)


def test_public_v1_output_path_is_refused(monkeypatch):
    from shadow import main
    monkeypatch.setattr(sys,'argv',['shadow','--output','data/cbb/prospective'])
    with pytest.raises(ValueError,match='public V1 output'):main()
