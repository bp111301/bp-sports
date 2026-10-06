import copy
import numpy as np
from baseline import FEATURES
from test_safety import fixture
from tournament import window_features, EXTRA, ADJUSTED, FATIGUE, run_candidate, eligibility, CANDIDATES

def games():
    g=fixture()
    g['home_extra']=[[.5,.1,.2,.3,.4,.25] for _ in range(len(g))]
    g['away_extra']=[[.4,.2,.3,.2,.3,.35] for _ in range(len(g))]
    return g

def test_all_windows_ignore_current_and_future_stats():
    g=games();changed=copy.deepcopy(g)
    changed.at[0,'home_extra']=[5.]*6;changed.at[0,'home_stats']=[300.]*8
    changed.at[0,'y']=0
    for window in (10,20,30,None):
        a=window_features(g,window);b=window_features(changed,window)
        np.testing.assert_array_equal(a.iloc[:2][FEATURES+EXTRA+ADJUSTED+FATIGUE],b.iloc[:2][FEATURES+EXTRA+ADJUSTED+FATIGUE])

def test_adjustment_uses_opponent_quality_before_date():
    f=window_features(games(),20)
    # First game's residuals: home offense 120−108=12; home defense 90−108=−18.
    # Other team's previous date was entirely league prior, so residuals are zero.
    assert np.isclose(f.iloc[2].adjusted_off,12/6)
    assert np.isclose(f.iloc[2].adjusted_def,-18/6)

def test_window20_preserves_original_features():
    from baseline import build_features
    np.testing.assert_allclose(window_features(games(),20)[FEATURES],build_features(games())[FEATURES],rtol=0,atol=0)

def test_extra_histories_reset_each_season():
    f=window_features(games(),None)
    np.testing.assert_array_equal(f.iloc[3][EXTRA+ADJUSTED].to_numpy(dtype=float),np.zeros(8))
    assert f.iloc[3].games3_diff==0 and f.iloc[3].games5_diff==0

def test_fatigue_excludes_current_game():
    f=window_features(games(),20)
    assert f.iloc[0].home_rest==7 and f.iloc[0].home_b2b==0
    assert f.iloc[2].home_rest==0 and f.iloc[2].home_b2b==1
    assert f.iloc[2].games3_diff==0

def test_exact_bounded_candidate_set():
    assert len(CANDIDATES)==12 and len({x[0] for x in CANDIDATES})==12
    assert sum(x[3] for x in CANDIDATES)==1

def test_selection_rejects_accuracy_loss_and_unstable_recent_seasons():
    control={'pooled':dict(brier=.22,log_loss=.63,correct=5414)}
    control.update({s:dict(brier=.22) for s in range(2019,2026)})
    candidate=copy.deepcopy(control);candidate['pooled']=dict(brier=.219,log_loss=.629,correct=5414)
    for s in range(2019,2026): candidate[s]['brier']=.219
    assert eligibility(candidate,control,list(range(2019,2026)))['eligible']
    candidate['pooled']['correct']=5413
    assert not eligibility(candidate,control,list(range(2019,2026)))['eligible']
    candidate['pooled']['correct']=5414;candidate[2025]['brier']=.221
    assert not eligibility(candidate,control,list(range(2019,2026)))['eligible']

def test_weighted_fit_does_not_see_test_labels():
    import pandas as pd
    rows=[]
    for season in range(2016,2026):
        for i in range(10):
            rows.append(dict(game_id=f'{season}-{i}',season=season,date=f'{season-1}-11-{i+1:02}',y=i%2,**{k:float(i+(season-2016)*.1) for k in FEATURES}))
    f=pd.DataFrame(rows);a=run_candidate(f,FEATURES,True)
    f.loc[f.season>=2023,'y']=1-f.loc[f.season>=2023,'y']
    b=run_candidate(f,FEATURES,True)
    np.testing.assert_array_equal(a[a.season<=2023].probability,b[b.season<=2023].probability)
