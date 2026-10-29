import copy
import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd
from confidence_audit import audit_ledger, summarize, wilson

NOW = '2026-10-28T23:58:00Z'


def nhl():
    return pd.DataFrame([{'game_id':1,'candidate':'a','home_win_prob':.8,
        'created_at_utc':'2026-10-26T10:00Z','start_time_utc':'2026-10-27T00:00Z',
        'settled_at_utc':'2026-10-27T03:00Z','status':'settled','actual_home_win':0},
        {'game_id':2,'candidate':'a','home_win_prob':.2,
        'created_at_utc':'2026-10-26T10:00Z','start_time_utc':'2026-10-27T00:00Z',
        'settled_at_utc':'2026-10-27T03:00Z','status':'settled','actual_home_win':0}])


class ConfidenceAudit(unittest.TestCase):
    def test_confidence_is_selected_side_and_input_is_unchanged(self):
        d=nhl();original=d.copy(deep=True);r=audit_ledger(d,'NHL','a',NOW)
        self.assertAlmostEqual(r['overall']['mean_confidence'],.8)
        self.assertEqual(r['overall']['accuracy'],.5)
        pd.testing.assert_frame_equal(d,original)

    def test_candidate_separation_and_pending_exclusion(self):
        d=nhl();other=d.copy();other['candidate']='b';other['actual_home_win']=1
        pending=d.iloc[[0]].copy();pending['game_id']=3;pending['status']='pending';pending['actual_home_win']=np.nan;pending['settled_at_utc']=None
        r=audit_ledger(pd.concat([d,other,pending]),'NHL','a',NOW)
        self.assertEqual(r['overall']['games'],2);self.assertEqual(r['pending_games'],1)

    def test_duplicate_late_and_invalid_settlements_rejected(self):
        d=nhl()
        with self.assertRaises(ValueError):audit_ledger(pd.concat([d,d.iloc[[0]]]),'NHL','a',NOW)
        for key,value in [('created_at_utc','2026-10-27T00:00Z'),('settled_at_utc','2026-10-29T00:00Z'),('actual_home_win',2),('home_win_prob',float('inf')),('status','unknown')]:
            bad=d.copy();bad.loc[0,key]=value
            with self.assertRaises(ValueError):audit_ledger(bad,'NHL','a',NOW)

    def test_bin_boundaries_and_empty_buckets(self):
        r=summarize([.5,.6,.7,.8,.9,1],[0,1,0,1,0,1])
        self.assertEqual([b['games'] for b in r['buckets']],[1,1,1,1,2])
        self.assertTrue(all(b['limited_sample'] for b in r['buckets']))
        self.assertEqual(summarize([],[])['overall']['games'],0)

    def test_wilson_endpoints_and_small_sample_uncertainty(self):
        lo,hi=wilson(1,1);self.assertLess(lo,.5);self.assertAlmostEqual(hi,1)
        lo,hi=wilson(0,1);self.assertAlmostEqual(lo,0);self.assertGreater(hi,.5)

    def test_cfb_grade_mismatch_rejected(self):
        d=nhl().iloc[[0]].drop(columns=['candidate','actual_home_win','created_at_utc','start_time_utc']).copy()
        d['model_version']='CFB_V1';d['snapshot_created_utc']='2026-10-26T10:00Z';d['kickoff_utc']='2026-10-27T00:00Z'
        d['status']='SETTLED';d['home_team']='H';d['away_team']='A';d['actual_winner']='A';d['correct']=0
        self.assertEqual(audit_ledger(d,'CFB',now=NOW)['overall']['wins'],0)
        d['correct']=1
        with self.assertRaises(ValueError):audit_ledger(d,'CFB',now=NOW)


if __name__=='__main__':unittest.main()
