import copy,json,unittest
from datetime import datetime,timezone
import pandas as pd
from run import quality,inferred_quality,goalie_inputs,append_pair,settle,summary,weighted_features,FEATURE

class GoalieExperimentSafety(unittest.TestCase):
    def setUp(self):
        self.g=pd.DataFrame([{'gameId':1,'teamAbbrev':'A','playerId':10,'gameDate':pd.Timestamp('2026-10-01'),'season':'20262027','shotsAgainst':30.,'saves':28.,'gamesStarted':1},
            {'gameId':2,'teamAbbrev':'B','playerId':20,'gameDate':pd.Timestamp('2026-10-02'),'season':'20262027','shotsAgainst':30.,'saves':25.,'gamesStarted':1}])
        self.record={'game_id':3,'home_team':'A','away_team':'B','start_time_utc':'2026-10-06T23:00:00Z','created_at_utc':'2026-10-06T22:30:00Z','input_cutoff_utc':'2026-10-06T22:29:00Z','probabilities':{'team_control':.55,'inferred_goalie':.56,'confirmed_goalie':.57},'status':'pending','actual_home_win':None,'settled_at_utc':None,
            'goalie_observations':{s:{'game_id':3,'team':team,'nhl_goalie_id':pid,'status':'Confirmed','confirmed_eligible':True,'report_timestamp_valid':True,'captured_at_utc':'2026-10-06T22:00:00Z','start_time_utc':'2026-10-06T23:00:00Z'} for s,team,pid in [('home','A',10),('away','B',20)]}}
    def test_current_day_and_future_goalie_results_excluded(self):
        date=pd.Timestamp('2026-10-06');original=quality(10,self.g,date)
        bad=pd.DataFrame([{**self.g.iloc[0].to_dict(),'gameId':3,'gameDate':date,'saves':0.,'shotsAgainst':1000.},{**self.g.iloc[0].to_dict(),'gameId':4,'gameDate':date+pd.Timedelta(days=1),'saves':1000.,'shotsAgainst':1000.}])
        self.assertEqual(original,quality(10,pd.concat([self.g,bad]),date))
    def test_player_history_follows_trades_and_expires(self):
        g=self.g.copy();g.loc[0,'teamAbbrev']='OLD';date=pd.Timestamp('2026-10-06')
        self.assertEqual(quality(10,g,date),quality(10,self.g,date));self.assertEqual(quality(10,g,pd.Timestamp('2028-01-01')),.905)
        self.assertEqual(inferred_quality('A','20262027',g,date),.905)
    def test_live_inferred_feature_matches_historical_prior_only_feature(self):
        d=pd.DataFrame({'game_id':[1,2,3],'season':['20262027']*3,'game_date':pd.to_datetime(['2026-10-01','2026-10-02','2026-10-06']),'home_team':['A']*3,'away_team':['B']*3})
        old=weighted_features(d,self.g).loc[2,FEATURE]
        live=inferred_quality('A','20262027',self.g,d.iloc[2].game_date)-inferred_quality('B','20262027',self.g,d.iloc[2].game_date)
        self.assertAlmostEqual(old,live,places=14)
    def test_unknown_player_uses_fixed_prior(self):
        self.assertEqual(quality(999,self.g,pd.Timestamp('2026-10-06')),.905)
    def test_atomic_pair_and_first_predictions_preserved(self):
        rows=[];r=copy.deepcopy(self.record);now=pd.Timestamp(r['created_at_utc'])
        self.assertTrue(append_pair(rows,r,now));changed=copy.deepcopy(r);changed['probabilities']['confirmed_goalie']=.99
        self.assertFalse(append_pair(rows,changed,now));self.assertEqual(rows[0]['probabilities']['confirmed_goalie'],.57)
        missing=copy.deepcopy(r);del missing['probabilities']['team_control']
        with self.assertRaises(ValueError):append_pair([],missing,now)
    def test_window_post_start_and_late_confirmation_rejected(self):
        for created in ['2026-10-06T21:00:00Z','2026-10-06T23:00:00Z']:
            r=copy.deepcopy(self.record);r['created_at_utc']=created;r['input_cutoff_utc']=created
            self.assertFalse(append_pair([],r,pd.Timestamp(created)))
        r=copy.deepcopy(self.record);r['goalie_observations']['home']['captured_at_utc']='2026-10-06T22:31:00Z'
        self.assertFalse(append_pair([],r,pd.Timestamp(r['created_at_utc'])))
    def test_unconfirmed_or_wrong_team_not_paired(self):
        for key,value in [('status','Likely'),('confirmed_eligible',False),('team','X'),('report_timestamp_valid',False),('nhl_goalie_id',None)]:
            r=copy.deepcopy(self.record);r['goalie_observations']['home'][key]=value
            self.assertFalse(append_pair([],r,pd.Timestamp(r['created_at_utc'])))
    def test_settlement_preserves_probability_and_same_population(self):
        rows=[copy.deepcopy(self.record)];before=json.dumps(rows[0]['probabilities']);now=datetime(2026,10,7,tzinfo=timezone.utc)
        complete=pd.DataFrame({'game_id':[3],'start_time_utc':pd.to_datetime(['2026-10-06T23:00:00Z']),'home_win':[1]})
        settle(rows,complete,now);self.assertEqual(before,json.dumps(rows[0]['probabilities']))
        result=summary(rows,[],now);self.assertEqual([m['games'] for m in result['metrics']],[1,1,1])
        self.assertFalse(result['automatic_promotion'])
    def test_changed_actual_start_invalidates_settlement(self):
        rows=[copy.deepcopy(self.record)];complete=pd.DataFrame({'game_id':[3],'start_time_utc':pd.to_datetime(['2026-10-06T22:00:00Z']),'home_win':[1]});now=datetime(2026,10,7,tzinfo=timezone.utc)
        settle(rows,complete,now);self.assertEqual(rows[0]['status'],'invalid_timing');self.assertEqual(summary(rows,[],now)['metrics'],[])

if __name__=='__main__':unittest.main()
