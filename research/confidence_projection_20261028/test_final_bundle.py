import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
s=importlib.util.spec_from_file_location('final_fit',Path(__file__).with_name('fit_final.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Fixed:
    def predict_proba(self,x):
        p=np.array([.9,.1,.5,.5])[:len(x)]
        return np.column_stack([1-p,p])

def bundle(sport):return {'sport':sport,'feature_columns':['a','b'],'model':Fixed()}

def test_both_recipes_keep_reference_winners():
    x=pd.DataFrame({'a':[1,2,np.nan,4],'b':[0,0,0,0]});ref=np.array([.3,.7,.5,.49])
    for sport in ['cfb','nhl']:
        p=m.predict_features(bundle(sport),x,ref);np.testing.assert_array_equal(p>=.5,ref>=.5)
        assert np.isfinite(p).all()

def test_exact_column_order_and_invalid_reference():
    x=pd.DataFrame({'a':[1],'b':[2]})
    with pytest.raises(ValueError,match='order'):m.predict_features(bundle('cfb'),x[['b','a']],[.5])
    for ref in [[np.nan],[2],[],[.1,.2]]:
        with pytest.raises(ValueError,match='reference'):m.predict_features(bundle('nhl'),x,ref)
    x.a=np.inf
    with pytest.raises(ValueError,match='Infinite'):m.predict_features(bundle('cfb'),x,[.5])
