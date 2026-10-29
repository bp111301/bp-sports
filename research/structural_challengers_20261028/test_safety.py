import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('struct',Path(__file__).with_name('experiment.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_train_only_imputation():
    x=pd.DataFrame({'a':[0,2,np.nan,1000],'empty':[np.nan]*4,'team':['a','b','a','c']})
    tr,te,imp,num=m.prepare(x,[0,1,2],[3],['team'])
    assert imp.statistics_[0]==1 and imp.statistics_[1]==0
    assert list(tr.a)==[0,2,1] and list(te.a)==[1000]
    assert list(te['empty'])==[0] and te.team.iloc[0]=='c'

def test_temporal_fold_and_date_overlap_guard():
    d=pd.DataFrame({'season':[2018,2019],'game_id':[1,2],'start_date':['2018-10-01','2019-10-01']})
    tr,te=m.fold(d,2019,'cfb');assert list(tr)==[0] and list(te)==[1]
    d.loc[0,'start_date']='2019-11-01'
    with pytest.raises(ValueError,match='overlaps'):m.fold(d,2019,'cfb')

def test_sigma_excludes_current_and_future():
    h={2016:np.ones(210)*10,2017:np.ones(210)*20,2018:np.ones(210)*999}
    sigma,years,n=m.margin_sigma(h,2018)
    assert years==[2016,2017] and n==420
    assert np.isclose(sigma,np.sqrt(250))
    assert m.margin_sigma({2017:np.zeros(210)},2018)[0]==5

def test_poisson_probability_and_invalid_rates():
    a=m.poisson_probability([1,2,3],[3,2,1]);b=m.poisson_probability([3,2,1],[1,2,3])
    np.testing.assert_allclose(a+b,1);assert np.isclose(a[1],.5) and (a>0).all() and (a<1).all()
    with pytest.raises(ValueError,match='rates'):m.poisson_probability([np.nan],[1])
    with pytest.raises(ValueError,match='rates'):m.poisson_probability([0],[1])

def test_fixed_catboost_configuration():
    p=m.params(3,5)
    assert p['boosting_type']=='Ordered' and p['has_time'] and p['iterations']==400
    assert p['thread_count']==1 and not p['allow_writing_files'] and not p['use_best_model']
    assert p['bootstrap_type']=='No' and p['random_strength']==0

def test_duplicate_team_date_rejected():
    t=pd.DataFrame({'gameDate':['2020-01-01']*2,'season':['20192020']*2,'teamId':[1,1]})
    with pytest.raises(ValueError,match='Duplicate NHL'):m.nhl_features(pd.DataFrame(),t)

def test_all_empty_training_rows_kept():
    x=pd.DataFrame({'n':[np.nan]*4,'cat':['a']*4});tr,te,_,_=m.prepare(x,[0,1],[2,3],['cat'])
    assert len(tr)==len(te)==2 and np.all(tr.n==0) and np.all(te.n==0)

def test_cfb_calendar_day_and_excluded_outcomes():
    bases=set(m.e.cfb.base.PAIR_BASES+m.e.cfb.pri.BLEND_BASES+m.e.EXTRA_BASES)
    data={f'{prefix}{side}_{f}':[1.] for prefix in ['', 'prev_'] for side in ['home','away'] for f in bases}
    data.update({f'{side}_{f}':[1.] for side in ['home','away'] for f in ['pregame_elo','opp_elo_roll_avg','talent','team_talent_weighted','ovr_rtprod','hc_tenure']})
    data.update(season=[2019],season_type=['postseason'],week=[1],start_date=['2019-12-20T18:00Z'],home_team_id=[1],away_team_id=[2],home_conference=['A'],away_conference=['B'])
    d=pd.DataFrame(data);a,cats,_=m.cfb_features(d)
    b,_,_=m.cfb_features(d.assign(start_date='2019-12-20T00:00Z',home_points=999,away_points=0,home_qb_name='future QB',spread=30))
    pd.testing.assert_frame_equal(a,b)
    assert a.effective_week.iloc[0]==8 and a.source_week.iloc[0]==1
    assert not set(a)&{'home_points','away_points','home_qb_name','spread'}
