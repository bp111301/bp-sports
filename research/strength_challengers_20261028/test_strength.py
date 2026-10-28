"""Temporal and identity safety checks for the new scoring features."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location('strength_experiment', Path(__file__).with_name('experiment.py'))
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


class StrengthSafety(unittest.TestCase):
    def games(self):
        return pd.DataFrame({'game_id':[1,2,3,4,5], 'date':['2020-01-01','2020-01-02','2020-01-03','2020-01-04','2020-01-05'],
            'home_id':[1,3,1,2,1], 'away_id':[2,4,3,4,4],
            'home_score':[10.,2.,3.,1.,4.], 'away_score':[0.,1.,1.,2.,2.], 'home_field':[0.]*5})

    def test_target_future_and_previous_day_outcomes_cannot_change_own_feature(self):
        d = self.games()
        original, _ = e.strength_features(d, 'cfb')
        changed = d.copy()
        changed.loc[changed.index >= 1, 'home_score'] = 99
        altered, _ = e.strength_features(changed, 'cfb')
        np.testing.assert_array_equal(original.loc[:2].to_numpy(), altered.loc[:2].to_numpy())
        self.assertNotEqual(original.at[4, 'strength_diff'], altered.at[4, 'strength_diff'])

    def test_same_day_features_invariant_to_row_order(self):
        d = self.games()
        d.loc[1, 'date'] = d.loc[0, 'date']
        original, _ = e.strength_features(d, 'nhl')
        shuffled, _ = e.strength_features(d.sample(frac=1, random_state=4), 'nhl')
        np.testing.assert_allclose(original.to_numpy(), shuffled.loc[original.index].to_numpy(), rtol=0, atol=1e-14)

    def test_old_results_expire_and_boundaries_prove_exclusion(self):
        d = self.games()
        d.loc[4, 'date'] = '2022-01-01'
        x, boundaries = e.strength_features(d, 'cfb')
        self.assertEqual(x.at[4, 'strength_diff'], 0)
        for b in boundaries:
            if b['training_max_date']:
                self.assertGreaterEqual((pd.Timestamp(b['target_date'])-pd.Timestamp(b['training_max_date'])).days, 2)

    def test_missing_or_duplicate_game_identity_rejected(self):
        d = self.games()
        with self.assertRaises(ValueError):
            e.strength_features(pd.concat([d, d.iloc[[0]]]), 'nhl')
        d.loc[0, 'home_id'] = np.nan
        with self.assertRaises(ValueError):
            e.strength_features(d, 'cfb')

    def test_strength_accounts_for_opponent_and_neutral_site(self):
        d = self.games().iloc[[0,2]].copy()
        x, _ = e.strength_features(d, 'cfb')
        self.assertGreater(x.iloc[1].strength_diff, 0)
        d.loc[0, 'home_field'] = 1.
        neutral_adjusted, _ = e.strength_features(d, 'cfb')
        self.assertLess(neutral_adjusted.iloc[1].strength_diff, x.iloc[1].strength_diff)


if __name__ == '__main__':
    unittest.main()
