"""Started games, mismatched teams and late snapshots never earn final results."""
import importlib.util
from pathlib import Path
import pandas as pd
import hashlib,json

spec=importlib.util.spec_from_file_location('final_checks',Path(__file__).resolve().parents[1]/'pipeline/check_finals.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
NOW=pd.Timestamp('2026-10-07T03:00Z')
P=dict(home_team='DET',away_team='OTT',created_at_utc='2026-10-06T22:00Z',start_time_utc='2026-10-06T23:00Z')
A=dict(home_team='DET',away_team='OTT',completed=True,start_time_utc='2026-10-06T23:00Z',home_score=3,away_score=2)

def test_only_confirmed_final_with_matching_teams_and_pregame_capture():
    assert m.final_valid(P,A,NOW)
    for changes in [dict(completed=False),dict(home_team='BUF'),dict(home_score=None),dict(home_score=-1),dict(home_score=float('nan')),dict(start_time_utc='2026-10-06T21:00Z'),dict(start_time_utc='2026-10-07T04:00Z')]:
        assert not m.final_valid(P,{**A,**changes},NOW)
    assert not m.final_valid({**P,'created_at_utc':'bad'},A,NOW)
    assert not m.final_valid({**P,'created_at_utc':P['start_time_utc']},A,NOW)

def test_metrics_use_preserved_probabilities():
    rows=[dict(home_win_prob=.8,actual_home_win=1),dict(home_win_prob=.6,actual_home_win=0)]
    r=m.metrics(rows)
    assert r['games']==2 and r['correct']==1 and r['accuracy']==.5
    assert abs(r['brier']-.2)<1e-12
    assert m.metrics([])['accuracy'] is None

def test_nhl_grades_once_and_preserves_saved_predictions(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    for folder in ['model/nhl/v2_research','model/nhl/goalie_experiment','data/nhl/v2_research','data/nhl/goalie_experiment']:
        Path(folder).mkdir(parents=True)
    sha=hashlib.sha256(b'frozen').hexdigest()
    for folder,file in [('v2_research','watchlist.joblib'),('goalie_experiment','frozen_bundle.joblib')]:
        Path(f'model/nhl/{folder}/{file}').write_bytes(b'frozen')
        Path(f'model/nhl/{folder}/manifest.json').write_text(json.dumps(dict(bundle_sha256=sha)))
        Path(f'data/nhl/{folder}/summary.json').write_text('{}')
    row={**P,'game_id':1,'candidate':'reference_control','home_win_prob':.6,'bundle_sha256':sha,'status':'pending','actual_home_win':None,'settled_at_utc':None}
    lp=Path('data/nhl/v2_research/prediction_ledger.csv');pd.DataFrame([row]).to_csv(lp,index=False)
    pair={**P,'game_id':1,'bundle_sha256':sha,'probabilities':dict(team_control=.6,inferred_goalie=.65,confirmed_goalie=.7),'status':'pending','actual_home_win':None,'settled_at_utc':None}
    pp=Path('data/nhl/goalie_experiment/paired_ledger.jsonl');pp.write_text(json.dumps(pair)+'\n')
    monkeypatch.setattr(m,'get',lambda url:dict(id=1,homeTeam=dict(abbrev='DET',score=3),awayTeam=dict(abbrev='OTT',score=2),startTimeUTC=P['start_time_utc'],gameState='FINAL'))
    m.nhl(NOW)
    graded=pd.read_csv(lp).iloc[0].to_dict();paired=json.loads(pp.read_text())
    assert graded['status']=='settled' and paired['actual_home_win']==1
    for key in ['home_win_prob','created_at_utc','start_time_utc','bundle_sha256']:assert graded[key]==row[key]
    assert paired['probabilities']==pair['probabilities']
    csv_before=lp.read_bytes();pair_before=pp.read_bytes();m.nhl(NOW+pd.Timedelta(minutes=15))
    assert lp.read_bytes()==csv_before and pp.read_bytes()==pair_before
