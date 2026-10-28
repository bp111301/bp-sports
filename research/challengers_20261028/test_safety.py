import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np,pandas as pd
import cfb,nhl,capture_cfb_inputs as receipts

class ConstantModel:
    def __init__(self,p):self.p=p
    def predict_proba(self,x):return np.tile([1-self.p,self.p],(len(x),1))

class ChallengerSafety(unittest.TestCase):
    def test_cfb_rejects_live_labels_and_duplicate_ids(self):
        with patch.object(cfb.base,'load_data',return_value=pd.DataFrame({'season':[2026]})):
            with self.assertRaises(ValueError):cfb.guarded_data('unused')
        with patch.object(cfb.base,'load_data',return_value=pd.DataFrame({'season':[2025,2025],'game_id':[1,1]})):
            with self.assertRaises(ValueError):cfb.guarded_data('unused')
    def test_cfb_training_excludes_target_and_uses_last_three_only(self):
        d=pd.DataFrame({'season':range(2015,2026)})
        self.assertEqual(d.loc[cfb.training_index(d,2023,True),'season'].tolist(),[2020,2021,2022])
        self.assertTrue(d.loc[cfb.training_index(d,2023),'season'].lt(2023).all())
    def test_symmetric_calibration_never_flips_winner(self):
        p=np.array([.05,.2,.4,.5,.6,.8,.95]);s=cfb.calibrate(p,[0,0,1,0,1,1,1]);q=cfb.apply_calibration(p,s)
        self.assertTrue(.25<=s<=2);np.testing.assert_array_equal(q>=.5,p>=.5)
        np.testing.assert_allclose(cfb.apply_calibration(1-p,s),1-q,atol=1e-12)
    def test_nhl_indicator_free_pipeline_has_no_learned_missingness_columns(self):
        x=pd.DataFrame({'a':[1.,2.,np.nan,1.,2.,3.],'pp':[.1,np.nan,.2,.1,.2,.3]});m=nhl.learner(['a','pp']);m.fit(x,[0,1,0,0,1,1])
        self.assertEqual(m.named_steps['prep'].transform(x).shape,(6,2))
    def test_nhl_isolated_missing_pp_uses_fallback(self):
        x=pd.DataFrame({f:[0.,0.] for f in nhl.base.FEATURES});x['pp_rate_20_diff']=[np.nan,.1];before=x.copy(deep=True)
        p=nhl.predict_guarded((ConstantModel(.92),ConstantModel(.55)),x,list(x),['pp_rate_20_diff'])
        np.testing.assert_allclose(p,[.55,.92]);pd.testing.assert_frame_equal(x,before)
    def test_nhl_selection_rejects_failed_season_even_if_extractor_returns_it(self):
        with tempfile.TemporaryDirectory() as temp:
            for y in range(2018,2025):
                for report in ['summary','powerplay','penaltykill']:Path(temp,f'{report}_{y}{y+1}.csv').write_text('placeholder')
            with patch.object(nhl.adv,'load_team_stats',return_value=pd.DataFrame({'season':['20252026']})):
                with self.assertRaises(ValueError):nhl.selection_data(temp)
    def test_nhl_rolling_features_never_see_target_game_stats(self):
        t=pd.DataFrame({'season':['20242025']*4,'teamId':[1]*4,'gameId':[1,2,3,4],'gameDate':pd.date_range('2024-10-01',periods=4)})
        for f in nhl.adv.RAW:t[f]=[.1,.2,.3,.4]
        before=nhl.adv.rolling_table(t,20)
        t.loc[3,nhl.adv.RAW]=999.
        pd.testing.assert_frame_equal(before,nhl.adv.rolling_table(t,20))
    def test_official_shootout_pair_recovers_correct_winner(self):
        common=dict(season='20242025',gameId=1,gameDate=pd.Timestamp('2024-10-01'),gamesPlayed=1,goalsFor=2,goalsAgainst=2)
        h={**common,'homeRoad':'H','teamId':1,'opponentTeamAbbrev':'B','wins':1,'winsInShootout':1};a={**common,'homeRoad':'R','teamId':2,'opponentTeamAbbrev':'A','wins':0,'winsInShootout':0}
        d=nhl.historical_games(pd.DataFrame([h,a]));self.assertEqual((d.iloc[0].home_score,d.iloc[0].away_score,d.iloc[0].home_win),(3.,2.,1))
        with self.assertRaises(ValueError):nhl.historical_games(pd.DataFrame([h,{**a,'goalsAgainst':4}]))
    def fixture(self):
        now=pd.Timestamp('2026-10-29T00:02Z');raw={'game_id':1,'season':2026,'week':9,'home_pregame_elo':1500,'away_pregame_elo':1450}
        for f in cfb.pri.BLEND_BASES:
            for side in ['home','away']:raw[side+'_'+f]=.1;raw['prev_'+side+'_'+f]=.2
        pred=pd.DataFrame([dict(game_id=1,prediction_id='CFBV1_2026_1',snapshot_created_utc='2026-10-29T00:01Z',kickoff_utc='2026-10-29T01:00Z',home_team='A',away_team='B',home_win_prob=.75)])
        bundle={'version':'CFB_V1','prior_k':7.,'context_features':['elo_diff','home_field'],'prior_features':['blend_off_epa_diff','home_field'],'context_model':ConstantModel(.6),'prior_model':ConstantModel(.8),'context_weight':.25,'prior_weight':.75}
        return now,pred,pred.copy(deep=True),pd.DataFrame([raw]),bundle
    def test_receipts_match_components_and_never_change_forecasts(self):
        now,pred,ledger,raw,bundle=self.fixture();before=pred.copy(deep=True)
        rows=receipts.receipt_payloads(pred,ledger,raw,bundle,{'source':'digest'},'frozenhash',now)
        self.assertEqual(rows[0]['receipt_role'],'official_first_capture_inputs');self.assertEqual(rows[0]['component_probabilities'],{'context':.6,'prior':.8});self.assertIn('elo_diff',rows[0]['feature_vectors']['context']);pd.testing.assert_frame_equal(pred,before)
        with self.assertRaises(ValueError):receipts.receipt_payloads(pred.assign(home_win_prob=.76),ledger,raw,bundle,{},'hash',now)
    def test_refresh_receipt_never_claims_original_inputs(self):
        now,pred,ledger,raw,bundle=self.fixture();ledger.snapshot_created_utc='2026-10-28T00:01Z'
        rows=receipts.receipt_payloads(pred,ledger,raw,bundle,{},'hash',now)
        self.assertEqual(rows[0]['receipt_role'],'later_refresh_inputs_not_original_forecast')
    def test_stale_or_late_capture_rejected(self):
        now,pred,ledger,raw,bundle=self.fixture()
        for changed_now in [now+pd.Timedelta(hours=1),now+pd.Timedelta(minutes=15)]:
            with self.assertRaises(ValueError):receipts.receipt_payloads(pred,ledger,raw,bundle,{},'hash',changed_now)
    def test_receipts_append_only_and_idempotent(self):
        now,pred,ledger,raw,bundle=self.fixture();rows=receipts.receipt_payloads(pred,ledger,raw,bundle,{},'hash',now)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'receipts.jsonl';self.assertEqual(receipts.append_receipts(path,rows),1);before=path.read_bytes();self.assertEqual(receipts.append_receipts(path,rows),0);self.assertEqual(path.read_bytes(),before)
            with self.assertRaises(ValueError):receipts.append_receipts(path,[{**rows[0],'home_win_prob':.99}])
            self.assertEqual(path.read_bytes(),before)
    def test_coverage_surfaces_missing_fcs_and_fbs_inputs(self):
        now,pred,ledger,raw,bundle=self.fixture();schedule=pd.DataFrame([dict(game_id=i,start_date='2026-10-29T01:00Z',fbs_game=i!=3,fbs_participant=True) for i in [1,2,3]])
        c=receipts.coverage(schedule,raw,pred,now);self.assertEqual(c['groups']['fbs_vs_fbs']['missing_feature_game_ids'],['2']);self.assertEqual(c['groups']['fbs_vs_fcs']['missing_feature_game_ids'],['3'])
if __name__=='__main__':unittest.main()
