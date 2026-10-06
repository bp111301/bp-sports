import copy
import numpy as np
import pandas as pd
from baseline import build_features, evaluate, FEATURES, PRIORS

def fixture():
    return pd.DataFrame([
        dict(game_id='1',season=2016,date='2015-10-01',start_time='2015-10-01T20:00Z',home_id='1',away_id='2',home_team='A',away_team='B',neutral=False,y=1,home_stats=[120,90,100,.6,.1,.3,.3,1],away_stats=[90,120,100,.4,.2,.2,.2,0]),
        dict(game_id='2',season=2016,date='2015-10-01',start_time='2015-10-01T22:00Z',home_id='3',away_id='4',home_team='C',away_team='D',neutral=True,y=0,home_stats=PRIORS.tolist(),away_stats=PRIORS.tolist()),
        dict(game_id='3',season=2016,date='2015-10-02',start_time='2015-10-02T20:00Z',home_id='1',away_id='3',home_team='A',away_team='C',neutral=False,y=1,home_stats=PRIORS.tolist(),away_stats=PRIORS.tolist()),
        dict(game_id='4',season=2017,date='2016-10-01',start_time='2016-10-01T20:00Z',home_id='1',away_id='2',home_team='A',away_team='B',neutral=False,y=0,home_stats=PRIORS.tolist(),away_stats=PRIORS.tolist()),
    ])

def test_current_and_future_outcomes_do_not_change_features():
    g=fixture(); original=build_features(g)
    changed=copy.deepcopy(g); changed.at[0,'y']=0; changed.at[0,'home_stats']=[200]*8
    result=build_features(changed)
    np.testing.assert_array_equal(original.iloc[:2][FEATURES],result.iloc[:2][FEATURES])
    changed=copy.deepcopy(g); changed.at[3,'home_stats']=[300]*8
    np.testing.assert_array_equal(original[FEATURES],build_features(changed)[FEATURES])

def test_history_and_rest_use_prior_dates():
    f=build_features(fixture())
    assert f.iloc[0].off_diff==0
    assert f.iloc[2].off_diff>0
    assert f.iloc[2].b2b_diff==0  # both teams played yesterday
    assert f.iloc[2].rest_diff==0

def test_neutral_has_no_elo_home_advantage():
    f=build_features(fixture())
    assert f.iloc[1].home_advantage==0
    assert f.iloc[1].elo_probability==.5

def test_season_resets_rolling_state_but_regresses_elo():
    f=build_features(fixture())
    assert f.iloc[3].off_diff==0
    assert f.iloc[3].history_diff==0
    assert f.iloc[3].elo_diff!=0

def test_input_order_is_irrelevant():
    a=build_features(fixture()); b=build_features(fixture().sample(frac=1,random_state=11))
    pd.testing.assert_frame_equal(a,b)

def test_scaler_and_weights_cannot_see_test_or_future_season_labels():
    rows=[]
    for season in range(2016,2026):
        for i in range(12):
            rows.append(dict(season=season,date=f'{season-1}-11-{i+1:02}',y=i%2,**{k:float(i+(season-2016)*.1) for k in FEATURES},elo_probability=.5))
    f=pd.DataFrame(rows); a=evaluate(f)
    f.loc[f.season>=2023,'y']=1-f.loc[f.season>=2023,'y']
    b=evaluate(f)
    np.testing.assert_array_equal(a[a.season<=2023].baseline_probability,b[b.season<=2023].baseline_probability)

def test_feature_schema_excludes_markets_and_current_scores():
    assert len(FEATURES)==14 and len(set(FEATURES))==14
    assert not any(s in k for k in FEATURES for s in ('score','spread','odds','winner','injury'))

def test_same_team_twice_same_date_is_rejected():
    g=fixture(); g.at[1,'home_id']='1'
    try: build_features(g)
    except AssertionError: return
    raise AssertionError('same-date double team was allowed')
