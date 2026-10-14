import copy
import json
from pathlib import Path
import numpy as np
import pandas as pd
from evaluate_holdout import gate, predict_bundle


def test_gate_requires_every_precommitted_check():
    lock=json.loads(Path(__file__).with_name('EVALUATION_LOCK.json').read_text())
    stats={'games':5500,'accuracy':.72,'brier':.18,'log_loss':.54,
           'neutral':{'games':500,'brier':.21},'early_season':{'games':900,'brier':.20}}
    report={'models':{'team_stats':stats,'elo':{'accuracy':.71},'elo_logistic':copy.deepcopy(stats)}}
    assert all(gate(report,lock).values())
    report['models']['team_stats']['neutral']['brier']=.25
    assert not gate(report,lock)['neutral_brier']


def test_portable_bundle_preserves_missing_value_and_scaling_behavior():
    bundle={'features':['a'],'imputer':[2.],'mean':[1.],'scale':[2.], 'coefficients':[2.],
            'intercept':0.,'calibration_coefficient':1.,'calibration_intercept':0.}
    result=predict_bundle(bundle,pd.DataFrame({'a':[np.nan,1.,2.]}))
    np.testing.assert_allclose(result,[1/(1+np.exp(-1)),.5,1/(1+np.exp(-1))])
