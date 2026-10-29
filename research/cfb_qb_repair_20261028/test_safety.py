import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
spec=importlib.util.spec_from_file_location('qb',Path(__file__).with_name('experiment.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def sample():
    p=pd.DataFrame([dict(pos_team_id=1,pos_team='Team name',passer_player_name='A',game_id=10,season=2019,Comp=10,Att=20,Yds=200,Pass_TD=2,Int=1,Sck=2)])
    s=pd.DataFrame([dict(game_id=10,season=2019,start_date='2019-09-01T12:00Z',home_id=1,away_id=2,completed=True)])
    return p,s

def test_numeric_id_and_duplicate_guard():
    p,s=sample();j,r=m.join_sources(p,s)
    assert len(j)==1 and r['identity_retention']==1
    with pytest.raises(ValueError,match='Duplicate player'):m.join_sources(pd.concat([p,p]),s)
    p.pos_team_id=99
    with pytest.raises(ValueError,match='Identity retention'):m.join_sources(p,s)

def test_future_season_and_empty_layer_rejected():
    p,s=sample();p.season=2026
    with pytest.raises(ValueError,match='Live seasons'):m.join_sources(p,s)

def test_raw_count_rates():
    p,_=sample();q=p.copy();q.Att=80;q.Comp=60;q.Yds=400;q.Pass_TD=2;q.Int=0;q.Sck=0
    np.testing.assert_allclose(m.rates(pd.concat([p,q])),[.7,6,.04,.01,2/102])

def test_date_guard_and_primary_tie():
    p,s=sample();q=p.copy();q.passer_player_name='Z';q.Comp=20
    p=pd.concat([q,p],ignore_index=True)
    for team in [2]:
        z=p.copy();z.pos_team_id=team;p=pd.concat([p,z],ignore_index=True)
    j,_=m.join_sources(p,s)
    d=pd.DataFrame([dict(game_id=20,season=2019,start_date='2019-09-03T12:00Z',home_team_id=1,away_team_id=2)])
    x,c,b=m.features(d,j);assert c['both_team_prior_completion_coverage']==1
    np.testing.assert_allclose(x.iloc[0].dropna(),0)
    # Swapping target outcome or adding a future source changes no feature.
    future=j.copy();future['source_date']=pd.Timestamp('2019-09-03',tz='UTC');future['Comp']=0;future['game_id']=11
    xx,_,_=m.features(d.assign(home_win=0),pd.concat([j,future],ignore_index=True))
    pd.testing.assert_frame_equal(x,xx)
    d.start_date='2019-09-02T12:00Z'
    with pytest.raises(ValueError,match='coverage'):m.features(d,j)

def test_training_only_imputation_and_empty_columns():
    train=pd.DataFrame(np.nan,index=range(4),columns=m.FEATURES);train[m.FEATURES[0]]=[0,2,4,np.nan]
    prep,beta=m.offset_fit(train,np.array([.4,.6,.4,.6]),np.array([0,1,0,1]))
    assert prep.named_steps['impute'].statistics_[0]==2
    assert np.all(prep.named_steps['impute'].statistics_[1:]==0)
    assert len(beta)==21
    before=prep.named_steps['impute'].statistics_.copy();prep.transform(train.fillna(1e6));np.testing.assert_array_equal(before,prep.named_steps['impute'].statistics_)

def test_feature_allowlist():
    assert len(m.FEATURES)==20
    assert not any('qb_name' in f or 'starter' in f or 'spread' in f or 'home_win' in f for f in m.FEATURES)
    assert set(m.PASS_COLS)=={'pos_team_id','pos_team','passer_player_name','game_id','season','Comp','Att','Yds','Pass_TD','Int','Sck'}
