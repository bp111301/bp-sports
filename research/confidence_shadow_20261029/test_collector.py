import importlib.util
from pathlib import Path
import numpy as np,pandas as pd,pytest,gzip,json
s=importlib.util.spec_from_file_location('collector',Path(__file__).with_name('collect.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def history():return pd.DataFrame([dict(game_id=1,season=2026,start_date='2026-10-20',home_team_id=1,away_team_id=2,home_points=30,away_points=10,neutral_site='false'),dict(game_id=2,season=2026,start_date='2026-10-22',home_team_id=2,away_team_id=1,home_points=10,away_points=20,neutral_site='true')])
def test_single_target_strength_matches_registered_recipe_and_excludes_future():
 h=history();t=dict(game_id=3,season=2026,start_date='2026-10-25',home_team_id=1,away_team_id=2,home_points=0,away_points=0,neutral_site=False)
 value,b=m.strength_at(h,t)
 d=pd.concat([h,pd.DataFrame([t])],ignore_index=True);g=d.rename(columns={'start_date':'date','home_team_id':'home_id','away_team_id':'away_id','home_points':'home_score','away_points':'away_score'});g['home_field']=m.e.cfb.base.build_matrix(d).home_field
 expected,_=m.fit.s.strength_features(g,'cfb');assert np.isclose(value,expected.iloc[-1].strength_diff,atol=1e-12,rtol=0)
 future=pd.DataFrame([{**t,'game_id':4,'start_date':'2026-10-24','home_points':999,'away_points':0}]);future2=pd.DataFrame([{**t,'game_id':5,'start_date':'2026-10-26','home_points':999,'away_points':0}])
 assert m.strength_at(pd.concat([h,future,future2],ignore_index=True),t)[0]==value
 assert b['source_games']==2

def test_snapshot_content_address_and_no_overwrite(tmp_path,monkeypatch):
 monkeypatch.setattr(m,'OUT',tmp_path);monkeypatch.setattr(m,'ROOT',tmp_path);snapshot={'sport':'cfb','targets':[{'x':1.2345678901234567}]};digest,p=m.save_snapshot(snapshot)
 path=tmp_path/'inputs'/f'{digest}.json.gz';raw=gzip.decompress(path.read_bytes());assert json.loads(raw)==snapshot
 assert m.hashlib.sha256(raw).hexdigest()==digest
 m.save_snapshot(snapshot);path.write_bytes(gzip.compress(b'bad'))
 with pytest.raises(ValueError,match='rewrite'):m.save_snapshot(snapshot)

def test_empty_report_has_no_invented_results():
 report=m.report({},{});assert report['results']['cfb']['paired_settled_games']==0
 assert report['results']['nhl']['metrics']['reference']['overall']['games']==0
 assert not report['results']['cfb']['minimum_review_sample_reached']

def test_reference_dependency_guard():
 worker=m.module('refworker',Path(__file__).with_name('reference_worker.py'))
 with pytest.raises(ValueError,match='environment'):worker.run({'sport':'cfb'},'unused')

def test_one_sport_failure_preserves_other_sports_valid_capture(tmp_path,monkeypatch):
 monkeypatch.setattr(m,'OUT',tmp_path);t=m.now();start=t+pd.Timedelta(days=1)
 r=dict(forecast_key='isolation:cfb:1',sport='cfb',game_id=1,home_id=2,away_id=3,game_state='STATUS_SCHEDULED',captured_at_utc=t.isoformat(),input_snapshot_at_utc=t.isoformat(),start_time_utc=start.isoformat(),reference_home_win_prob=.7,challenger_home_win_prob=.6,reference_bundle_sha256='a'*64,challenger_bundle_sha256='b'*64,input_snapshot_sha256='c'*64)
 monkeypatch.setattr(m,'cfb_inputs',lambda existing:({'sport':'cfb'}, {}, {'new_targets':1}))
 def failed(existing):raise ValueError('known source delay')
 monkeypatch.setattr(m,'nhl_inputs',failed);monkeypatch.setattr(m,'forecasts',lambda *args:[r]);monkeypatch.setattr(m.sys,'argv',['collect','--reference-python','unused'])
 with pytest.raises(SystemExit):m.main()
 assert len(m.events.read_events(tmp_path/'forecasts.jsonl','forecast_key'))==1
 health=json.loads((tmp_path/'health.json').read_text());assert health['errors'][0]['sport']=='nhl' and health['sports']['cfb']['new_paired_forecasts']==1
