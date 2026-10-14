import unittest
import pandas as pd
from compact_board_ui import prepare_compact, date_options, compact_html
from overview_ui import FROZEN_NHL

class CompactBoardTests(unittest.TestCase):
    def test_saved_probability_is_preserved_when_live_scores_change(self):
        now=pd.Timestamp('2026-10-14T02:00Z')
        record=dict(game_id='g',bundle_sha256=FROZEN_NHL,candidate='reference_control',status='pending',home_team='DET',away_team='NJD',home_win_prob=.6,created_at_utc='2026-10-12T12:00Z',start_time_utc='2026-10-14T00:00Z')
        payload={'nhl':{'ok':True,'data':[record]}}
        board,_=prepare_compact('NHL',payload,{},now)
        changed={'games':{'NHL:g':dict(sport='NHL',home_team='DET',away_team='NJD',state='live',home_score=1,away_score=5,start_time_utc='2026-10-14T00:00Z',detail='3rd')}}
        refreshed,_=prepare_compact('NHL',payload,changed,now)
        self.assertEqual(board.iloc[0].p,refreshed.iloc[0].p)
        self.assertFalse(refreshed.iloc[0].settled)
        self.assertIn('60.0%',compact_html(refreshed.iloc[0],changed,now))
        self.assertIn('PENDING',compact_html(refreshed.iloc[0],changed,now))

    def test_cbb_dates_use_central_and_reject_bad_snapshot_identity(self):
        now=pd.Timestamp('2026-10-14T00:00Z')
        record=dict(game_id='c',season=2027,season_type=2,bundle_sha256='fixed',home_team='Home',away_team='Away',home_win_prob=.7,created_at_utc='2026-10-13T23:00Z',start_time_utc='2026-11-03T00:00Z',status='pending')
        feed=dict(bundle_sha256='fixed',predictions=[record,{**record,'game_id':'bad','bundle_sha256':'different'},{**record,'game_id':'late','created_at_utc':'2026-11-03T01:00Z'}])
        board,_=prepare_compact('CBB',{}, {},now,feed)
        self.assertEqual(len(board),1)
        self.assertEqual(board.iloc[0].date,'2026-11-02')
        dates,default=date_options(board,now)
        self.assertEqual(default,'2026-11-02')
        self.assertIn('2026-10-13',dates)

    def test_final_score_does_not_claim_a_grade_before_settlement(self):
        now=pd.Timestamp('2026-10-14T02:00Z')
        record=dict(game_id='g',bundle_sha256=FROZEN_NHL,candidate='reference_control',status='pending',home_team='DET',away_team='NJD',home_win_prob=.6,created_at_utc='2026-10-12T12:00Z',start_time_utc='2026-10-14T00:00Z')
        board,_=prepare_compact('NHL',{'nhl':{'ok':True,'data':[record]}},{},now)
        output=compact_html(board.iloc[0],{},now)
        self.assertIn('PENDING',output)
        self.assertNotIn('>WIN<',output)

    def test_settled_ledger_final_overrides_stale_live_score(self):
        now=pd.Timestamp('2026-10-14T02:00Z')
        record=dict(game_id='g',bundle_sha256=FROZEN_NHL,candidate='reference_control',status='settled',home_team='DET',away_team='NJD',home_win_prob=.6,created_at_utc='2026-10-12T12:00Z',start_time_utc='2026-10-14T00:00Z',home_score=4,away_score=5,actual_home_win=0)
        stale={'games':{'NHL:g':dict(sport='NHL',home_team='DET',away_team='NJD',state='live',home_score=1,away_score=2,start_time_utc='2026-10-14T00:00Z',detail='3rd')}}
        board,_=prepare_compact('NHL',{'nhl':{'ok':True,'data':[record]}},stale,now)
        output=compact_html(board.iloc[0],stale,now)
        self.assertIn('NHL · Final',output)
        self.assertIn('<strong>5</strong>',output)
        self.assertNotIn('3rd',output)

if __name__=='__main__':unittest.main()
