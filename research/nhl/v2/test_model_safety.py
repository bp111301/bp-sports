import unittest
import numpy as np
import pandas as pd
from experiment_models import recent_weights,training_indices,fit_predict

class ModelSafety(unittest.TestCase):
    def fixture(self):
        n=300
        d=pd.DataFrame({'season':np.repeat(['20182019','20192020','20202021','20212022','20222023'],n),'home_win':np.tile(np.arange(n)%2,5)})
        x=pd.DataFrame({'signal':np.tile(np.linspace(-2,2,n),5),'rest':np.tile(np.arange(n)%3,5)})
        return d,x
    def test_training_boundaries_and_recent_window(self):
        d,_=self.fixture()
        self.assertEqual(sorted(d.loc[training_indices(d,'20222023','recent3_logistic'),'season'].unique()),['20192020','20202021','20212022'])
        self.assertTrue((d.loc[training_indices(d,'20212022','v1_reference'),'season']<'20212022').all())
    def test_recency_weights_normalized_and_fixed_half_life(self):
        w=recent_weights(['20182019','20202021','20222023']);self.assertAlmostEqual(w.mean(),1.);self.assertAlmostEqual(w[1]/w[0],2.);self.assertAlmostEqual(w[2]/w[1],2.)
    def test_test_labels_never_change_test_predictions(self):
        d,x=self.fixture();changed=d.copy();changed.loc[changed.season>='20212022','home_win']=1-changed.loc[changed.season>='20212022','home_win']
        for name in ['v1_reference','recent3_logistic','decay2_logistic','small_boosted_tree','linear_tree_blend']:
            p,_=fit_predict(d,x,['signal','rest'],'20212022',name);q,_=fit_predict(changed,x,['signal','rest'],'20212022',name)
            np.testing.assert_array_equal(p,q)
    def test_missing_season_rejected(self):
        d,x=self.fixture()
        with self.assertRaises(ValueError):fit_predict(d,x,['signal'],'20252026','v1_reference')
if __name__=='__main__':unittest.main()
