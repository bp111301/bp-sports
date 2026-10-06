import unittest
import pandas as pd
import numpy as np
from build_ledger import append_prediction,forecast_inputs,adv
class LedgerSafety(unittest.TestCase):
    def test_no_post_start_prediction(self):
        rows=[];record={'game_id':1,'candidate':'test','start_time_utc':'2026-10-06T18:00:00Z'}
        self.assertFalse(append_prediction(rows,record,'2026-10-06T18:00:00Z'));self.assertEqual(rows,[])
    def test_first_record_is_immutable(self):
        rows=[];record={'game_id':1,'candidate':'test','start_time_utc':'2026-10-06T18:00:00Z','home_win_prob':.6}
        self.assertTrue(append_prediction(rows,record,'2026-10-06T17:00:00Z'))
        self.assertFalse(append_prediction(rows,{**record,'home_win_prob':.9},'2026-10-06T17:30:00Z'));self.assertEqual(rows[0]['home_win_prob'],.6)
    def test_future_score_and_future_stats_do_not_enter_features(self):
        h=pd.DataFrame({'game_id':[1,2,3],'season':['20212022']*3,'game_date':pd.to_datetime(['2021-10-01','2021-10-02','2021-10-03']),'home_team':['A']*3,'away_team':['B']*3,'home_id':[1]*3,'away_id':[2]*3,'home_score':[3,2,4],'away_score':[2,3,1],'home_win':[1,0,1],'last_period_type':['REG']*3})
        t=pd.DataFrame([{'gameId':r.game_id,'teamId':team,'gameDate':r.game_date,'season':r.season,**{c:1. for c in adv.RAW}} for _,r in h.iterrows() for team in [1,2]])
        target={**h.iloc[-1].to_dict(),'game_id':4,'game_date':pd.Timestamp('2021-10-04')}
        a,b=forecast_inputs(h,t,target)
        target.update(home_score=100,away_score=0,home_win=1)
        bad=pd.DataFrame([{'gameId':4,'teamId':team,'gameDate':target['game_date'],'season':target['season'],**{c:999. for c in adv.RAW}} for team in [1,2]])
        c,d=forecast_inputs(h,pd.concat([t,bad],ignore_index=True),target)
        pd.testing.assert_frame_equal(a,c);pd.testing.assert_frame_equal(b,d)
        self.assertTrue(a.shots_for_20_diff.notna().all())
if __name__=='__main__':unittest.main()
