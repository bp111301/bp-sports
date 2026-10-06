import unittest
import numpy as np
import pandas as pd
from calibrate_leader import chronological,fit_calibrator,apply_calibrator,bucket_table
class CalibrationSafety(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame({'season':['20212022']*6+['20222023']*6+['20232024']*6,'game_date':['2021-01-01']*18,'game_id':range(18),'home_win_prob':[.2,.35,.45,.6,.7,.85]*3,'home_win':[0,1,0,1,1,0]*3})
    def test_current_future_labels_cannot_change_current_calibration(self):
        d=self.fixture();altered=d.copy();altered.loc[altered.season>='20222023','home_win']=1-altered.loc[altered.season>='20222023','home_win']
        for method in ['temperature','sigmoid']:
            before,audit=chronological(d,method);after,_=chronological(altered,method)
            np.testing.assert_array_equal(before.loc[before.season<='20222023','calibrated_prob'],after.loc[after.season<='20222023','calibrated_prob'])
            self.assertEqual(audit[1]['calibration_seasons'],['20212022'])
    def test_temperature_preserves_picks(self):
        p=np.array([.01,.2,.49,.5,.51,.9,.99])
        for t in [.25,1,4]:
            q=apply_calibrator({'method':'temperature','temperature':t},p)
            np.testing.assert_array_equal(p>=.5,q>=.5)
    def test_warmup_is_unmodified(self):
        d=self.fixture()
        for method in ['raw','temperature','sigmoid']:
            q,_=chronological(d,method);np.testing.assert_array_equal(q.iloc[:6].home_win_prob,q.iloc[:6].calibrated_prob)
    def test_bucket_totals_and_exact_boundaries(self):
        d=pd.DataFrame({'calibrated_prob':[.5,.55,.6,.9,1.],'home_win':[1,1,0,1,1]})
        buckets=bucket_table(d);self.assertEqual(sum(z['games'] for z in buckets),5);self.assertEqual(sum(z['wins'] for z in buckets),4)
    def test_raw_identity_and_invalid_fit(self):
        p=np.array([0,.2,1]);np.testing.assert_array_equal(apply_calibrator({'method':'raw'},p),p)
        with self.assertRaises(ValueError):fit_calibrator('temperature',[.3,.7],[1,1])
if __name__=='__main__':unittest.main()
