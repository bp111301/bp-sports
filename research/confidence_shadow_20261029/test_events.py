import importlib.util
from pathlib import Path
import json
import pandas as pd
import pytest
s=importlib.util.spec_from_file_location('events',Path(__file__).with_name('events.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def forecast():return dict(forecast_key='cfb:1',sport='cfb',game_id=1,home_id=2,away_id=3,game_state='STATUS_SCHEDULED',captured_at_utc='2026-10-29T12:01Z',input_snapshot_at_utc='2026-10-29T12:00Z',start_time_utc='2026-10-29T13:00Z',reference_home_win_prob=.7,challenger_home_win_prob=.6,reference_bundle_sha256='a'*64,challenger_bundle_sha256='b'*64,input_snapshot_sha256='c'*64)
def test_reject_late_stale_unknown_state_and_winner_flip():
 r=forecast();assert m.validate_forecast(r,'2026-10-29T12:02Z')==r
 for updates in [dict(captured_at_utc='2026-10-29T13:00Z'),dict(input_snapshot_at_utc='2026-10-29T11:00Z'),dict(start_time_utc=None),dict(game_state='LIVE'),dict(challenger_home_win_prob=.3),dict(reference_home_win_prob=float('nan')),dict(input_snapshot_sha256='bad')]:
  with pytest.raises(ValueError):m.validate_forecast({**r,**updates},'2026-10-29T12:02Z')
def test_append_exact_replay_only_and_no_partial_mutation(tmp_path):
 p=tmp_path/'events.jsonl';r=forecast();assert m.append(p,[r],'forecast_key')==1;before=p.read_bytes();assert m.append(p,[r],'forecast_key')==0
 with pytest.raises(ValueError):m.append(p,[{**r,'forecast_key':'new'},{**r,'challenger_home_win_prob':.8}],'forecast_key')
 assert p.read_bytes()==before
 item=json.loads(p.read_text());item['game_id']=999;p.write_text(json.dumps(item)+'\n')
 with pytest.raises(ValueError,match='integrity'):m.read_events(p,'forecast_key')
def official():return dict(game_id=1,home_id=2,away_id=3,state='FINAL',start_time_utc='2026-10-29T13:00Z',home_score=24,away_score=10)
def test_settlement_final_identity_timing_and_append_only(tmp_path):
 f=forecast();f['event_sha256']=m.digest(f);p=tmp_path/'settled.jsonl';r=m.settlement(f,official(),'2026-10-29T17:00Z');assert r['actual_home_win']==1
 m.append(p,[r],'forecast_key')
 for updates in [dict(state='LIVE'),dict(game_id=2),dict(home_id=7),dict(start_time_utc='2026-10-29T14:00Z'),dict(home_score=10),dict(home_score=float('nan')),dict(home_score=-1),dict(home_score=1.5)]:
  with pytest.raises(ValueError):m.settlement(f,{**official(),**updates},'2026-10-29T17:00Z')
 with pytest.raises(ValueError):m.settlement(f,official(),'2026-10-29T12:00Z')
 with pytest.raises(ValueError):m.append(p,[{**r,'actual_home_win':0}],'forecast_key')
def test_reference_away_tie_boundary():
 r=forecast();r.update(reference_home_win_prob=.49,challenger_home_win_prob=.499999)
 m.validate_forecast(r,'2026-10-29T12:02Z')
 with pytest.raises(ValueError):m.validate_forecast({**r,'challenger_home_win_prob':.5},'2026-10-29T12:02Z')
