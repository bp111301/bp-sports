import json
import tempfile
import unittest
from pathlib import Path

from nba_primary import BASE_HASH, INJURY_HASH, merge, publish, stamp


class NBAPrimaryTests(unittest.TestCase):
    def test_release_preserves_old_picks_and_grades_the_new_probability(self):
        start = '2026-11-05T00:00:00+00:00'
        team = dict(home_id='1', away_id='2', start_time_utc=start, home_win_prob=.6,
                    created_at_utc='2026-11-04T16:00:00+00:00', status='settled', actual_home_win=0)
        old = dict(team, game_id='old', start_time_utc='2026-11-04T20:00:00+00:00')
        base = dict(feed_status='enabled', bundle_sha256=BASE_HASH,
                    predictions=[old, dict(team, game_id='new'), dict(team, game_id='late')])
        candidate = dict(team, season=2027, season_type=2, fallback=False, candidate_probability=.43,
                         created_at_utc='2026-11-04T23:10:00+00:00', shadow_sha256=INJURY_HASH,
                         v1_bundle_sha256=BASE_HASH, injury_report=dict(both_known=True, parse_issues=[]))
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            ledger = directory / 'predictions.jsonl'
            ledger.write_text(json.dumps(dict(candidate, game_id='new')) + '\n')
            publish(directory, stamp('2026-11-04T23:20:00+00:00'))
            with ledger.open('a') as stream:
                stream.write(json.dumps(dict(candidate, game_id='late')) + '\n')
            publish(directory, stamp(start))
            picks = json.loads((directory / 'primary.json').read_text())
        self.assertEqual(set(picks['picks']), {'new'})
        legacy, adjusted, fallback = merge(base, picks)['predictions']
        self.assertEqual([r['nba_pick_source'] for r in (legacy, adjusted, fallback)], ['legacy', 'injury', 'team'])
        self.assertEqual([r['home_win_prob'] for r in (legacy, adjusted, fallback)], [.6, .43, .6])
        self.assertEqual(adjusted['actual_home_win'], 0)
        self.assertEqual(adjusted['nba_baseline_probability'], .6)
        self.assertEqual(base['predictions'][1]['home_win_prob'], .6)
        with self.assertRaises(ValueError):
            merge(base, {})
