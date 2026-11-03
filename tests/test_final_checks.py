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

def test_pending_dates_accept_both_ledger_timestamp_formats():
    dates=m.pending_dates(pd.Series(['2026-10-07T00:00:00.000Z','2026-10-07 00:00:00+00:00','2026-10-08T00:00:00Z',None]),NOW)
    assert dates=={pd.Timestamp('2026-10-06').date()}

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

def test_cfb_fetches_omitted_scoreboard_games_by_id(monkeypatch):
    now=pd.Timestamp('2026-10-25T13:00Z')
    pending=pd.DataFrame([
        dict(game_id=1,schedule_kickoff_utc='2026-10-24T19:30Z',kickoff_utc='2026-10-24T19:30Z'),
        dict(game_id=42,schedule_kickoff_utc='2026-10-24T23:30Z',kickoff_utc='2026-10-24T23:30Z'),
        dict(game_id=43,schedule_kickoff_utc='2026-10-26T23:30Z',kickoff_utc='2026-10-26T23:30Z'),
        dict(game_id=42,schedule_kickoff_utc='2026-10-24T23:30Z',kickoff_utc='2026-10-24T23:30Z'),
    ])
    monkeypatch.setattr(m,'espn_events',lambda sport,dates:[dict(id=str(i)) for i in range(1,26)])
    calls=[]
    def get(url):
        calls.append(url)
        return dict(header=dict(id='42',competitions=[dict(id='42',status=dict(type=dict(completed=True,state='post')))]))
    monkeypatch.setattr(m,'get',get)
    events={e['id']:e for e in m.cfb_pending_events(pending,now)}
    assert len(events)==26 and events['42']['competitions'][0]['status']['type']['completed']
    assert len(calls)==1 and calls[0].endswith('event=42')
    assert '43' not in events

def test_cfb_direct_lookup_rejects_wrong_event_identity(monkeypatch):
    import pytest
    pending=pd.DataFrame([dict(game_id=42,schedule_kickoff_utc='2026-10-24T23:30Z',kickoff_utc='2026-10-24T23:30Z')])
    monkeypatch.setattr(m,'espn_events',lambda sport,dates:[])
    for header in [dict(id='41',competitions=[dict(id='42')]),dict(id='42',competitions=[dict(id='41')]),dict(id='42',competitions=[])]:
        monkeypatch.setattr(m,'get',lambda url:dict(header=header))
        with pytest.raises(ValueError,match='identity mismatch'):
            list(m.cfb_pending_events(pending,pd.Timestamp('2026-10-25T13:00Z')))


def basketball_event(gid='42',completed=True,**changes):
    competition=dict(id=gid,date=P['start_time_utc'],neutralSite=True,timeValid=True,
                     status=dict(type=dict(name='STATUS_FINAL' if completed else 'STATUS_IN_PROGRESS',state='post' if completed else 'in',completed=completed)),
                     competitors=[dict(homeAway='home',team=dict(id='2'),score='80'),dict(homeAway='away',team=dict(id='3'),score='70')])
    competition.update(changes)
    return dict(id=gid,season=dict(year=2027,type=2),competitions=[competition])


def test_basketball_lookup_falls_back_for_omitted_games_and_ignores_future(monkeypatch):
    rows=[dict(game_id='42',start_time_utc=P['start_time_utc']),dict(game_id='43',start_time_utc='2026-10-08T23:00Z')]
    calls=[]
    def get(url):
        calls.append(url)
        return {'events':[]} if '/scoreboard?' in url else {'header':basketball_event()}
    monkeypatch.setattr(m,'get',get)
    result=m.basketball_schedule('cbb',rows,NOW)
    assert len(result)==1 and result.iloc[0].game_id=='42'
    assert len(calls)==2 and calls[1].endswith('event=42')
    assert '&groups=50' in calls[0]


def test_basketball_lookup_rejects_wrong_event_identity(monkeypatch):
    import pytest
    monkeypatch.setattr(m,'get',lambda url:{'events':[]} if '/scoreboard?' in url else {'header':basketball_event('99')})
    with pytest.raises(ValueError,match='identity mismatch'):
        m.basketball_schedule('nba',[dict(game_id='42',start_time_utc=P['start_time_utc'])],NOW)


def test_summary_missing_time_flag_needs_confirmed_final_and_exact_saved_tipoff(monkeypatch):
    pending=[dict(game_id='42',start_time_utc=P['start_time_utc'])]
    for completed,start,flag,expected in [(True,P['start_time_utc'],None,True),(False,P['start_time_utc'],None,False),
                                          (True,'2026-10-06T23:30Z',None,False),(True,P['start_time_utc'],False,False)]:
        event=basketball_event(completed=completed,date=start)
        if flag is None:event['competitions'][0].pop('timeValid')
        else:event['competitions'][0]['timeValid']=flag
        monkeypatch.setattr(m,'get',lambda url:{'events':[event]})
        assert bool(m.basketball_schedule('cbb',pending,NOW).iloc[0].time_valid)==expected


def test_nba_final_check_appends_once_without_loading_or_changing_forecasts(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);directory=Path('data/nba/prospective');directory.mkdir(parents=True)
    model=Path('model/nba/v1');model.mkdir(parents=True)
    digest=hashlib.sha256(b'frozen').hexdigest();(model/'frozen_bundle.joblib').write_bytes(b'frozen')
    (model/'manifest.json').write_text(json.dumps(dict(bundle_sha256=digest)))
    p={**P,'game_id':'42','home_id':'2','away_id':'3','season':2027,'season_type':2,'bundle_sha256':digest,'home_win_prob':.7}
    pp=directory/'predictions.jsonl';pp.write_text(json.dumps(p)+'\n');before=pp.read_bytes()
    (directory/'results.jsonl').write_text('');(directory/'dashboard.json').write_text(json.dumps({'prediction_blocked_reason':'keep this source warning'}))
    monkeypatch.setattr(m,'get',lambda url:{'events':[basketball_event()]})
    m.nba(NOW)
    assert pp.read_bytes()==before
    result=json.loads((directory/'results.jsonl').read_text());assert result['actual_home_win']==1 and result['home_score']==80
    dashboard=json.loads((directory/'dashboard.json').read_text())
    assert dashboard['record']['games']==1 and dashboard['record']['correct']==1
    assert dashboard['prediction_blocked_reason']=='keep this source warning'
    settled=(directory/'results.jsonl').read_bytes();m.nba(NOW+pd.Timedelta(minutes=5))
    assert (directory/'results.jsonl').read_bytes()==settled and pp.read_bytes()==before


def test_cbb_fast_check_preserves_forecasts_and_existing_source_warnings(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.chdir(tmp_path);directory=Path('data/cbb/prospective');directory.mkdir(parents=True)
    root=Path('research/cbb/results');root.mkdir(parents=True);(root/'candidate_bundle.json').write_bytes(b'frozen')
    digest=hashlib.sha256(b'frozen').hexdigest()
    p={**P,'game_id':'42','home_team_id':'2','away_team_id':'3','bundle_sha256':digest,'home_win_prob':.7,'status':'pending'}
    (directory/'prediction_ledger.json').write_text(json.dumps([p]))
    warning=dict(game_id='future',reason='result_identity_mismatch')
    original=dict(bundle_sha256=digest,predictions=[p],grading_issues=[warning],capture_blocked_reason='waiting_for_stats')
    (directory/'dashboard.json').write_text(json.dumps(original));(directory/'summary.json').write_text(json.dumps(original))
    def grade(rows,schedule,now):
        assert schedule.iloc[0].home_id=='2' and schedule.iloc[0].status_type_completed
        return [{**rows[0],'status':'settled','actual_home_win':1}],[]
    monkeypatch.setattr(m,'module',lambda path:SimpleNamespace(grade=grade,summary=lambda rows:dict(saved_games=1,settled_games=1,pending_games=0)))
    monkeypatch.setattr(m,'get',lambda url:{'events':[basketball_event()]})
    m.cbb(NOW);result=json.loads((directory/'dashboard.json').read_text())
    assert result['predictions'][0]['status']=='settled'
    assert all(result['predictions'][0][k]==v for k,v in p.items() if k!='status')
    assert result['grading_issues']==[warning] and result['capture_blocked_reason']=='waiting_for_stats'
