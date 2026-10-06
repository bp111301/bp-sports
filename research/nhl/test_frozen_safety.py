import unittest
import numpy as np
import pandas as pd
from experiment_goalies import base,adv

class FrozenFeatureSafety(unittest.TestCase):
    def fixture(self):
        d=pd.DataFrame({'game_id':range(8),'season':['20242025']*4+['20252026']*4,'game_date':pd.date_range('2024-10-01',periods=8),'home_team':['A']*8,'away_team':['B']*8,'home_id':[1]*8,'away_id':[2]*8,'home_score':[4,1,3,2,4,2,5,1],'away_score':[2,3,1,4,1,3,2,3],'home_win':[1,0,1,0,1,0,1,0]})
        t=pd.DataFrame([{'gameId':r.game_id,'teamId':team,'season':r.season,'gameDate':r.game_date,**{c:float(i+1) for c in adv.RAW}} for i,(_,r) in enumerate(d.iterrows()) for team in [1,2]])
        return d,t
    def test_excluded_current_future_results_never_change_past_features(self):
        d,t=self.fixture();bx=base.build_features(d);x,_=adv.attach(d,bx,t,20)
        altered=d.copy();altered.loc[altered.index>=4,['home_score','away_score','home_win']]=[0,9,0]
        ta=t.copy();ta.loc[ta.gameId>=4,adv.RAW]=999.
        y,_=adv.attach(altered,base.build_features(altered),ta,20)
        pd.testing.assert_frame_equal(x.iloc[:5],y.iloc[:5])
        self.assertNotEqual(x.iloc[5].elo_diff,y.iloc[5].elo_diff)
    def test_classifier_training_features_unchanged_by_excluded_data(self):
        d,t=self.fixture();before,_=adv.attach(d,base.build_features(d),t,20)
        altered=d.copy();altered.loc[altered.season=='20252026',['home_score','away_score','home_win']]=[99,0,1]
        after,_=adv.attach(altered,base.build_features(altered),t,20)
        pd.testing.assert_frame_equal(before[d.season<'20252026'],after[d.season<'20252026'])
if __name__=='__main__':unittest.main()
