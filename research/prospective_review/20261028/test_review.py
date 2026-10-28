import unittest
import pandas as pd
import review as r

class ReviewChecks(unittest.TestCase):
    def frame(self):
        return pd.DataFrame([dict(game_id='1',p=.8,y=1.,settled=True,start=pd.Timestamp('2026-10-20T20:00Z'),created=pd.Timestamp('2026-10-20T19:00Z')),dict(game_id='2',p=.6,y=0.,settled=True,start=pd.Timestamp('2026-10-21T20:00Z'),created=pd.Timestamp('2026-10-21T19:00Z'))])
    def test_probability_metrics_use_saved_values(self):
        d=self.frame();before=d.copy(deep=True);m=r.metric(d)
        self.assertEqual((m['n'],m['wins'],m['losses']),(2,1,1))
        self.assertAlmostEqual(m['brier'],.2)
        pd.testing.assert_frame_equal(d,before)
    def test_unsettled_future_and_invalid_rows_are_excluded(self):
        d=self.frame();bad=pd.concat([d.assign(settled=False),d.assign(start=pd.Timestamp('2026-10-30T20:00Z')),d.assign(p=1.1),d.assign(created=d.start),d.assign(y=None)],ignore_index=True)
        self.assertEqual(len(r.clean(pd.concat([d,bad],ignore_index=True))),2)
    def test_pairing_uses_same_game_ids_and_requires_same_outcome(self):
        a=self.frame();b=a.copy().iloc[::-1];b.loc[b.game_id.eq('1'),'p']=.4
        m=r.compare(a,b);self.assertEqual(m['n'],2);self.assertEqual(m['winner_disagreements'],1);self.assertEqual(m['control_only_correct'],1)
        with self.assertRaises(AssertionError):r.compare(a,b.assign(y=1.))
    def test_duplicate_paired_ids_are_rejected(self):
        d=self.frame()
        with self.assertRaises(pd.errors.MergeError):r.compare(d,pd.concat([d,d]))
    def test_audit_detects_timing_and_invalid_settled_labels(self):
        d=self.frame();d.loc[0,'created']=d.loc[0,'start'];d.loc[1,'y']=None
        a=r.audit(d);self.assertEqual(a['invalid_timing_or_probability'],1);self.assertEqual(a['invalid_settled_labels'],1)

if __name__=='__main__':unittest.main()
