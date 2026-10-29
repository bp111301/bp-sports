import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('confidence_experiment',Path(__file__).with_name('experiment.py'))
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


class CalibrationSafety(unittest.TestCase):
    def test_no_winner_changes_at_extremes_or_tie(self):
        p=np.tile([.05,.2,.4,.5,.6,.8,.95],40);y=np.tile([0,1,0,1,1,0,1],40)
        m=e.fit_mapping(p,y);q=e.apply_mapping(p,m)
        np.testing.assert_array_equal(p>=.5,q>=.5)
        self.assertTrue(np.all((q>=0)&(q<=1)));self.assertTrue(np.all(q[p==.5]==.5))

    def test_monotone_and_side_symmetric(self):
        p=np.linspace(.01,.99,400);y=(np.arange(400)%3!=0).astype(int)
        m=e.fit_mapping(p,y)
        q=e.apply_mapping(np.linspace(.5,1,100),m)
        self.assertTrue(np.all(np.diff(q)>=0))
        test=np.array([.01,.2,.4,.6,.8,.99])
        np.testing.assert_allclose(e.apply_mapping(test,m),1-e.apply_mapping(1-test,m),atol=1e-15)

    def test_small_samples_rejected(self):
        with self.assertRaises(ValueError):e.fit_mapping([.8]*199,[1]*199)

    def test_result_provenance_and_fold_boundaries(self):
        import json,hashlib
        for sport in ['cfb','nhl']:
            r=json.loads((e.ROOT/f'runtime/confidence_20261028/{sport}/results.json').read_text())
            self.assertFalse(r['live_labels_used'])
            self.assertEqual(r['protocol_sha256'],hashlib.sha256((e.HERE/'PROTOCOL.md').read_bytes()).hexdigest())
            for fold in r['fit_boundaries']:
                self.assertTrue(all(s<fold['test_season'] for s in fold['training_seasons']))
                self.assertLessEqual(len(fold['training_seasons']),3)
            self.assertTrue(all(s['winner_changes']==0 for s in r['scores'].values()))


if __name__=='__main__':unittest.main()
