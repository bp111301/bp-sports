import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('projection_test',Path(__file__).with_name('evaluate.py'))
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


class ProjectionSafety(unittest.TestCase):
    def test_all_original_winners_preserved_at_extremes_and_ties(self):
        p=np.array([0,.1,.499999,.5,.6,1]);q=np.array([1,.9,.5,0,.2,0])
        out=e.project(p,q)
        np.testing.assert_array_equal(out>=.5,p>=.5)
        np.testing.assert_allclose(out,[.499999,.499999,.499999,.5,.5,.5])

    def test_agreeing_predictions_are_unchanged_and_inputs_not_mutated(self):
        p=np.array([.1,.3,.7,.9]);q=np.array([.2,.4,.6,.8]);before=q.copy()
        np.testing.assert_array_equal(e.project(p,q),q);np.testing.assert_array_equal(q,before)

    def test_nan_out_of_range_and_different_shapes_rejected(self):
        for p,q in [([np.nan],[.6]),([.6],[np.inf]),([-.1],[.6]),([.6],[1.1]),([.5,.6],[.7])]:
            with self.assertRaises(ValueError):e.project(p,q)

    def test_projection_uses_no_outcomes(self):
        p=np.array([.8,.2]);q=np.array([.3,.7])
        np.testing.assert_array_equal(e.project(p,q),[.5,.499999])

    def test_archive_csv_round_trip_preserves_selected_side(self):
        import io
        p=np.array([.1,.9]);q=e.project(p,np.array([.9,.1]))
        reread=pd.read_csv(io.StringIO(pd.DataFrame({'p':q}).to_csv(index=False)))
        np.testing.assert_array_equal(reread.p.to_numpy()>=.5,p>=.5)

    def test_duplicate_mismatched_and_excluded_source_rows_rejected(self):
        rows=pd.DataFrame({'game_id':[1,1],'season':['2024','2024'],'block':['2024:1']*2,
            'candidate':['control','new'],'home_win':[1,1],'probability':[.7,.8]})
        with self.assertRaises(ValueError):e.paired_source(pd.concat([rows,rows.iloc[[0]]]),'new','cfb')
        bad=rows.copy();bad.loc[1,'home_win']=0
        with self.assertRaises(ValueError):e.paired_source(bad,'new','cfb')
        bad=rows.copy();bad['season']='2026'
        with self.assertRaises(ValueError):e.paired_source(bad,'new','cfb')


if __name__=='__main__':unittest.main()
