import copy
import unittest
from collect import observation,append_observation,available_at,goalie_id,schedule_games,source_rows,timestamp

class CaptureSafety(unittest.TestCase):
    def setUp(self):
        self.game={'game_id':2026020044,'game_date':'2026-10-06','start_time_utc':'2026-10-06T23:00:00Z','home_team':'TOR','away_team':'NSH'}
        self.side={'goalie_name':'Anthony Stolarz','source_goalie_id':123,'status':'Confirmed','source_reported_at_utc':'2026-10-06T15:00:00Z','report_source_name':'Reporter','report_source_url':'https://example.com/report'}
        self.source={**self.game,'home':self.side,'away':self.side.copy()}
        self.roster=[{'id':8476932,'name':'Anthony Stolarz'}]
    def record(self,source=None,when='2026-10-06T17:00:00Z',roster=None):
        return observation(self.game,source or self.source,'home',self.roster if roster is None else roster,timestamp(when),'https://example.com/board','response','snapshot')
    def test_explicit_confirmation_only(self):
        self.assertTrue(self.record()['confirmed_eligible'])
        for status in ['Likely','Unconfirmed','Expected','confirmed',None]:
            source=copy.deepcopy(self.source);source['home']['status']=status
            self.assertFalse(self.record(source)['confirmed_eligible'])
    def test_post_start_rejected_even_with_old_report_timestamp(self):
        for when in ['2026-10-06T23:00:00Z','2026-10-07T00:00:00Z']:
            with self.assertRaises(ValueError):self.record(when=when)
    def test_future_missing_and_naive_report_times_not_eligible(self):
        for when in ['2026-10-06T18:00:00Z','2026-10-06T15:00:00',None,'invalid']:
            source=copy.deepcopy(self.source);source['home']['source_reported_at_utc']=when
            self.assertFalse(self.record(source)['confirmed_eligible'])
    def test_wrong_matchup_or_start_rejected(self):
        for field,value in [('home_team','BUF'),('game_date','2026-10-05'),('start_time_utc','2026-10-06T22:00:00Z')]:
            source=copy.deepcopy(self.source);source[field]=value
            with self.assertRaises(ValueError):self.record(source)
    def test_ambiguous_and_unresolved_names_not_eligible(self):
        self.assertFalse(self.record(roster=[])['confirmed_eligible'])
        self.assertFalse(self.record(roster=self.roster+[{'id':999,'name':'Anthony Stolarz'}])['confirmed_eligible'])
        self.assertEqual(goalie_id('Lukas Dostal',[{'id':42,'name':'Lukáš Dostál'}]),42)
    def test_duplicate_poll_and_status_changes_preserve_original(self):
        rows=[];first=self.record();self.assertTrue(append_observation(rows,first))
        self.assertFalse(append_observation(rows,self.record(when='2026-10-06T17:30:00Z')))
        source=copy.deepcopy(self.source);source['home']['status']='Likely'
        self.assertTrue(append_observation(rows,self.record(source,when='2026-10-06T18:00:00Z')))
        self.assertIsNone(available_at(rows,self.game['game_id'],'home',timestamp('2026-10-06T18:30:00Z')))
        self.assertTrue(append_observation(rows,self.record(when='2026-10-06T19:00:00Z')))
        self.assertEqual(rows[0],first);self.assertEqual(len(rows),3)
    def test_publication_does_not_backdate_availability(self):
        rows=[self.record()]
        self.assertIsNone(available_at(rows,self.game['game_id'],'home',timestamp('2026-10-06T16:00:00Z')))
        self.assertIsNotNone(available_at(rows,self.game['game_id'],'home',timestamp('2026-10-06T17:01:00Z')))
        self.assertIsNone(available_at(rows,self.game['game_id'],'home',timestamp('2026-10-06T23:00:00Z')))
    def test_schedule_ignores_started_games_playoffs_and_wrong_season(self):
        g={'id':1,'season':20262027,'gameType':2,'startTimeUTC':'2026-10-06T23:00:00Z','gameState':'FUT','homeTeam':{'id':10,'abbrev':'TOR'},'awayTeam':{'id':18,'abbrev':'NSH'}}
        payload={'gameWeek':[{'date':'2026-10-06','games':[g,{**g,'id':2,'gameState':'LIVE'},{**g,'id':3,'gameType':3},{**g,'id':4,'season':20252026}]}]}
        self.assertEqual(len(schedule_games(payload,timestamp('2026-10-06T17:00:00Z'))),1)
        self.assertEqual(schedule_games(payload,timestamp('2026-10-06T23:00:00Z')),[])
    def test_wrong_source_date_fails_closed(self):
        with self.assertRaises(ValueError):source_rows({'date':'2026-10-05','data':[]},'2026-10-06')

if __name__=='__main__':unittest.main()
