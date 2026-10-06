import unittest
import numpy as np
import pandas as pd
from experiment_factors import contextual_features,quality_features,distance

class FactorSafety(unittest.TestCase):
    def setUp(self):
        self.d=pd.DataFrame({'game_id':[2021020001,2021020002,2021020003,2021020004,2021020005], 'season':['20212022']*5,'game_date':pd.to_datetime(['2021-10-01','2021-10-02','2021-10-02','2021-10-03','2021-10-04']), 'home_team':['A']*5,'away_team':['B']*5,'home_id':[1]*5,'away_id':[2]*5,'home_score':[4]*5,'away_score':[2]*5,'home_win':[1]*5})
        self.q=pd.DataFrame([{'gameId':r.game_id,'gameDate':r.game_date.strftime('%Y%m%d'),'team':team,'xGoalsFor':gf,'xGoalsAgainst':ga} for _,r in self.d.iterrows() for team,gf,ga in [('A',3.,1.),('B',1.,3.)]])
    def test_current_and_future_scores_cannot_change_past_context(self):
        before=contextual_features(self.d);changed=self.d.copy();changed.loc[changed.index>=1,['home_score','away_score','home_win']]=[0,9,0]
        after=contextual_features(changed)
        pd.testing.assert_frame_equal(before.iloc[:3],after.iloc[:3])
    def test_same_day_context_uses_same_prior_outcomes(self):
        x=contextual_features(self.d)
        pd.testing.assert_series_equal(x.iloc[1],x.iloc[2],check_names=False)
    def test_quality_current_future_and_row_order(self):
        before,_=quality_features(self.d,self.q)
        q=self.q.copy();q.loc[q.gameId>=2021020004,['xGoalsFor','xGoalsAgainst']]=[100,0]
        after,_=quality_features(self.d,q)
        pd.testing.assert_frame_equal(before.iloc[:4],after.iloc[:4])
        shuffled,_=quality_features(self.d,self.q.iloc[::-1]);pd.testing.assert_frame_equal(before,shuffled)
        self.assertNotEqual(before.iloc[4].xg_for20_diff,after.iloc[4].xg_for20_diff)
    def test_quality_coverage_and_duplicate_rejection(self):
        _,coverage=quality_features(self.d,self.q);self.assertEqual(coverage,1.)
        with self.assertRaises(ValueError):quality_features(self.d,pd.concat([self.q,self.q.iloc[:1]]))
    def test_vendor_date_does_not_override_primary_game_identity(self):
        q=self.q.copy();q['gameDate']='20211005'
        expected,_=quality_features(self.d,self.q);actual,coverage=quality_features(self.d,q)
        pd.testing.assert_frame_equal(expected,actual);self.assertEqual(coverage,1.)

    def test_distance_and_congestion(self):
        self.assertEqual(distance((0,0),(0,0)),0.)
        self.assertAlmostEqual(distance((0,0),(0,1)),111.195,places=2)
        d=self.d.copy();d.loc[0,'home_team']='C';d.loc[0,'away_team']='D'
        x=contextual_features(d);self.assertEqual(x.iloc[1].games7_diff,0.)
        self.assertTrue(np.isnan(x.iloc[1].travel_km_diff))
    def test_season_reset(self):
        d=self.d.copy();d.loc[3:,'season']='20222023';x=contextual_features(d)
        self.assertTrue(np.isnan(x.iloc[3].opp_elo20_diff));self.assertEqual(x.iloc[3].games7_diff,0.)

if __name__=='__main__':unittest.main()
