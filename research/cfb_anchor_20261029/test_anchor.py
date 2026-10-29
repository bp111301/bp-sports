import importlib.util,inspect
from pathlib import Path
import numpy as np,pandas as pd,pytest
s=importlib.util.spec_from_file_location('anchor',Path(__file__).with_name('evaluate.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_preserves_every_parent_winner_and_reference_on_agreement():
 r=np.array([0,.49,.5,1,.9,.1]);q=np.array([.1,.8,.4,.99,.1,.9]);a=m.anchor(r,q);same=(r>=.5)==(q>=.5)
 np.testing.assert_array_equal(a>=.5,q>=.5);np.testing.assert_array_equal(a[same],r[same]);np.testing.assert_array_equal(a[~same],q[~same])
def test_invalid_vectors_fail_without_mutating_inputs():
 r=np.array([.1,.9]);q=np.array([.2,.8]);m.anchor(r,q);np.testing.assert_array_equal(r,[.1,.9]);np.testing.assert_array_equal(q,[.2,.8])
 for a,b in [([np.nan],[.5]),([1.1],[.5]),([.5],[-.1]),([.5],[np.inf]),([.1,.2],[.5]),([[.5]],[[.5]])]:
  with pytest.raises(ValueError):m.anchor(a,b)
def test_no_outcome_input_and_roundtrip_winners(tmp_path):
 assert list(inspect.signature(m.anchor).parameters)==['reference','challenger'];p=m.anchor([.49,.5,.4],[.8,.3,.45]);f=tmp_path/'p.csv';pd.DataFrame({'p':p}).to_csv(f,index=False);np.testing.assert_array_equal(pd.read_csv(f).p>=.5,p>=.5)
def sample():return pd.DataFrame([dict(game_id=1,season=2019,home_win=1,block='2019:1',training_max_season=2018,candidate=n,probability=p) for n,p in [('control',.6),(m.PARENT,.7)]])
def test_source_cohort_label_and_training_boundaries():
 d=sample();m.paired(d)
 for f in [pd.concat([d,d.iloc[[0]]]),d.iloc[[0]],d.assign(training_max_season=2019),d.assign(season=2026)]:
  with pytest.raises(ValueError):m.paired(f)
 d.loc[1,'home_win']=0
 with pytest.raises(ValueError):m.paired(d)
