import importlib.util
from pathlib import Path
import pandas as pd,numpy as np,pytest
s=importlib.util.spec_from_file_location('failure_audit',Path(__file__).with_name('audit.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def example():
 d=pd.DataFrame({'game_id':[1,2,3,4],'season':[2019]*4,'week':[1,5,9,1],'season_type':['regular','regular','regular','postseason'],'home_win':[1,1,0,0],'reference_probability':[.6,.4,.2,.7],'candidate_probability':[.7,.6,.3,.4],'weighted_talent_diff':[0,np.nan,2,np.nan],'context':[1,1,np.nan,1]})
 return m.enrich(d,['weighted_talent_diff','context'])
def test_partition_counts_and_loss_contributions():
 d=example();whole=m.metrics(d);parts=m.grouped(d,['pick_effect']);assert sum(r['games'] for r in parts)==whole['games'];assert sum(r['net_extra_wins'] for r in parts)==whole['net_extra_wins'];assert np.isclose(sum(r['total_brier_delta'] for r in parts),whole['total_brier_delta'])
 assert set(d.stage)=={'regular_1_4','regular_5_8','regular_9_plus','postseason'}
def test_metadata_alignment_and_duplicate_rejection():
 meta=pd.DataFrame({'game_id':[1],'season':[2019],'home_win':[1]});p=pd.DataFrame([{'game_id':1,'season':2019,'home_win':1,'candidate':c,'probability':.6} for c in ['control',m.NAME]])
 m.load_predictions(p,meta)
 for bad in [pd.concat([p,p.iloc[[0]]]),p.iloc[[0]],p.assign(season=2026),p.assign(probability=np.nan)]:
  with pytest.raises(ValueError):m.load_predictions(bad,meta)
def test_missingness_and_broken_vs_fixed_picks_are_distinct():
 d=example();assert list(d.missing_context)==['0','1','1','1'];assert m.metrics(d)['fixed_original_errors']==2 and m.metrics(d)['broke_original_correct']==0
