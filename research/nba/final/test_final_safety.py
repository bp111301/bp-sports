import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from compare_freeze import fit_calibrator,calibrate,compare,FEATURES,NAMES,TEMPERATURES
import evaluate

def fixture():
    rows=[]
    for season in range(2016,2026):
        for i in range(20):
            rows.append(dict(game_id=f'{season}-{i}',season=season,date=f'{season-1}-11-{i+1:02}',y=i%2,**{k:float(i+(season-2016)*.1) for k in FEATURES}))
    return pd.DataFrame(rows)

def test_calibration_and_model_fit_ignore_current_and_future_labels():
    f=fixture();a,_=compare(f)
    f.loc[f.season>=2023,'y']=1-f.loc[f.season>=2023,'y']
    b,_=compare(f)
    for name in NAMES:
        np.testing.assert_array_equal(a[(a.candidate==name)&(a.season<=2023)].probability,b[(b.candidate==name)&(b.season<=2023)].probability)

def test_calibration_uses_only_prior_seasons():
    oof,_=compare(fixture());cal=oof.dropna(subset=['calibration_last_season'])
    assert (cal.calibration_last_season<cal.season).all()
    assert len(NAMES)==9 and len(set(NAMES))==9

def test_temperature_preserves_selected_side():
    p=np.array([.1,.4,.6,.9]); y=np.array([0,1,0,1])
    c=fit_calibrator(p,y,'temperature')
    assert c['temperature'] in TEMPERATURES
    np.testing.assert_array_equal(calibrate(p,c)>=.5,p>=.5)

def test_extreme_probabilities_remain_finite():
    p=np.array([0.,1.,.2,.8]);y=np.array([0,1,1,0])
    for kind in ('platt','temperature'):
        q=calibrate(p,fit_calibrator(p,y,kind))
        assert np.isfinite(q).all() and (q>0).all() and (q<1).all()

def test_holdout_refuses_missing_freeze_before_network(monkeypatch,tmp_path):
    monkeypatch.setattr(evaluate,'MODEL',tmp_path)
    monkeypatch.setattr(evaluate.requests,'get',lambda *a,**k:pytest.fail('network before verified freeze'))
    with pytest.raises(FileNotFoundError):evaluate.main()

def test_default_loader_excludes_holdout():
    from baseline import load_games
    assert list(load_games.__defaults__[0])==list(range(2016,2026))
