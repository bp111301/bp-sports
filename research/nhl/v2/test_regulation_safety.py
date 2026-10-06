import unittest
import pandas as pd
from experiment_regulation import regulation_labels,strength_features

class RegulationSafety(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame({'game_id':[1,2,3,4],'season':['20212022']*4,'game_date':pd.to_datetime(['2021-10-01','2021-10-02','2021-10-02','2021-10-03']),'home_team':['A']*4,'away_team':['B']*4,'home_score':[3,2,4,4],'away_score':[2,3,1,2],'home_win':[1,0,1,1],'last_period_type':['OT','SO','REG','REG']})
    def test_remove_extra_time_award_only(self):
        q=regulation_labels(self.fixture());self.assertEqual(q.reg_outcome.tolist(),[1,1,2,2]);self.assertEqual(q.reg_home_goals.tolist(),[2,2,4,4]);self.assertEqual(q.reg_away_goals.tolist(),[2,2,1,2])
    def test_current_future_periods_and_scores_cannot_change_prior_features(self):
        d=self.fixture();before=strength_features(d);d.loc[1:,['home_score','away_score','home_win','last_period_type']]=[0,6,0,'REG'];after=strength_features(d)
        pd.testing.assert_frame_equal(before.iloc[:3],after.iloc[:3]);self.assertNotEqual(before.iloc[3].elo_diff,after.iloc[3].elo_diff)
    def test_same_date_outcomes_do_not_enter_features(self):
        q=strength_features(self.fixture());pd.testing.assert_series_equal(q.iloc[1],q.iloc[2],check_names=False)
    def test_invalid_extra_time_score_rejected(self):
        d=self.fixture();d.loc[0,'home_score']=9
        with self.assertRaises(ValueError):regulation_labels(d)
if __name__=='__main__':unittest.main()
