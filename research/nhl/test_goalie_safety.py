import unittest
import pandas as pd
from experiment_goalies_weighted import weighted_features, PRIOR_SV, PRIOR_SHOTS

class GoalieSafety(unittest.TestCase):
    def setUp(self):
        self.d = pd.DataFrame({'game_id':[1,2,3,4], 'season':['20212022']*4,
            'game_date':pd.to_datetime(['2021-10-01','2021-10-02','2021-10-02','2021-10-03']),
            'home_team':['A']*4,'away_team':['B']*4})
        self.g = pd.DataFrame({'gameId':[1,1,2,3,4], 'teamAbbrev':['A']*5,
            'playerId':[10]*5, 'shotsAgainst':[30,2,30,30,30],
            'saves':[27,0,30,30,30], 'gamesStarted':[1,0,1,1,1]})
    def test_current_future_and_starter_changes_do_not_change_past_features(self):
        before = weighted_features(self.d,self.g)
        altered = self.g.copy()
        altered.loc[altered.gameId>=2,['saves','shotsAgainst','playerId','gamesStarted']] = [0,100,99,0]
        after = weighted_features(self.d,altered)
        pd.testing.assert_frame_equal(before.iloc[:3],after.iloc[:3])
    def test_shot_weighted_shrinkage(self):
        result = weighted_features(self.d,self.g)
        expected = (27 + PRIOR_SHOTS*PRIOR_SV)/(32+PRIOR_SHOTS)-PRIOR_SV
        self.assertAlmostEqual(result.iloc[1].weighted_goalie_probable_diff,expected)
    def test_row_order_does_not_change_output(self):
        pd.testing.assert_frame_equal(weighted_features(self.d,self.g),weighted_features(self.d,self.g.iloc[::-1]))
    def test_same_day_games_share_identical_prior_information(self):
        result = weighted_features(self.d,self.g)
        self.assertTrue((result.iloc[1]==result.iloc[2]).all())

if __name__ == '__main__':
    unittest.main()
