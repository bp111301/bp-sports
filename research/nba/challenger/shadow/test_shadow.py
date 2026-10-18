import copy
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from engine import impact_features,report_candidates,adjusted_probability,validate
from injuries import cutoff_for
from study import availability_features,LOADS


def test_modern_pdf_name_represents_same_legacy_publication_instant():
    names=report_candidates(pd.Timestamp('2026-10-20T22:00Z'))
    assert names[:2]==['Injury-Report_2026-10-20_05PM.pdf','Injury-Report_2026-10-20_05_30PM.pdf']
    assert len(names)==6 and len(set(names))==6


def test_live_importance_matches_research_features_and_excludes_current_date():
    games=pd.DataFrame([dict(game_id=str(i),season=2025,date=f'2025-01-0{i}') for i in [1,2,3]])
    context={str(i):dict(home=dict(known=True,players=[dict(key='homestar',status='Out')]),away=dict(known=True,players=[])) for i in [1,2,3]}
    boxes={str(i):[dict(athlete_id='star',name='homestar',minutes=20.+i,points=10.+i)] for i in [1,2,3]}
    reference=availability_features(games,context,boxes)
    live=[dict(game_id=str(i),date=f'2025-01-0{i}',**p) for i in [1,2,3] for p in boxes[str(i)]]
    for i in [1,2,3]:
        values,listed,matched=impact_features(context[str(i)]['home'],context[str(i)]['away'],live,f'2025-01-0{i}')
        np.testing.assert_allclose([values[c] for c in LOADS],reference.iloc[i-1][LOADS].to_numpy(float))
    changed=copy.deepcopy(live);changed[-1].update(minutes=75.,name='newidentity')
    assert impact_features(context['3']['home'],context['3']['away'],changed,'2025-01-03')==impact_features(context['3']['home'],context['3']['away'],live,'2025-01-03')


def pair():
    return dict(game_id='1',season=2027,season_type=2,start_time_utc='2026-10-20T23:00Z',created_at_utc='2026-10-20T22:05Z',
        availability_cutoff_utc='2026-10-20T22:00Z',history_cutoff='2026-10-19',shadow_sha256='s',v1_bundle_sha256='v',
        control_probability=.6,candidate_probability=.6,fallback=True,listed_players=1,matched_players=1,
        injury_report=dict(both_known=True,parse_issues=[],published_at='2026-10-20T21:30Z',created_at='2026-10-20T21:30:01Z'))


@pytest.mark.parametrize('changes,match',[
    ({'created_at_utc':'2026-10-20T23:00Z'},'Capture'),
    ({'created_at_utc':'2026-10-20T21:59Z'},'Capture'),
    ({'history_cutoff':'2026-10-20'},'Current-date'),
    ({'candidate_probability':.61},'Fallback'),
    ({'season_type':1},'Nonregular'),
    ({'season':2026},'Nonregular'),
    ({'shadow_sha256':'changed'},'Frozen hash'),
])
def test_pair_rejects_leakage_preseason_or_changed_immutable_context(changes,match):
    with pytest.raises(ValueError,match=match):validate([{**pair(),**changes}],[],'s','v')


def test_adjustment_rejects_postcutoff_report_and_low_identity_coverage():
    p=pair();p.update(fallback=False,candidate_probability=.62)
    validate([p],[],'s','v')
    p['injury_report']['created_at']='2026-10-20T22:00:01Z'
    with pytest.raises(ValueError,match='Postcutoff'):validate([p],[],'s','v')
    p=pair();p.update(fallback=False,listed_players=10,matched_players=7)
    with pytest.raises(ValueError,match='identity coverage'):validate([p],[],'s','v')


def test_duplicate_or_retimed_grades_are_rejected():
    p=pair();r=dict(game_id='1',home_score=100,away_score=90,actual_home_win=1,source_state='post_completed',
                  actual_start_time_utc=p['start_time_utc'],settled_at_utc='2026-10-21T02:00Z')
    validate([p],[r],'s','v')
    with pytest.raises(ValueError,match='duplicate grade'):validate([p],[r,r],'s','v')
    with pytest.raises(ValueError,match='Changed start'):validate([p],[{**r,'actual_start_time_utc':'2026-10-20T22:00Z'}],'s','v')


def test_frozen_residual_applies_fixed_v1_offset_and_training_scaling():
    frozen=dict(fit=dict(features=['x'],mean=[10.],scale=[2.],coefficients=[.1,-.2]))
    expected=1/(1+np.exp(-(np.log(.6/.4)+.1-.2*(14-10)/2)))
    assert adjusted_probability(.6,dict(x=14.),frozen)==pytest.approx(expected)


def test_collector_saves_pair_once_and_appends_only_confirmed_final(tmp_path,monkeypatch):
    import importlib.util
    import json
    from datetime import datetime,timezone
    spec=importlib.util.spec_from_file_location('shadow_collector_fixture',Path(__file__).with_name('run.py'))
    app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
    class Clock(datetime):
        instant=datetime(2026,10,20,22,5,tzinfo=timezone.utc)
        @classmethod
        def now(cls,tz=None):return cls.instant
    class Model:
        def predict_proba(self,frame):return np.array([[.4,.6]])
    frozen=dict(v1_bundle_sha256='v',fit=dict(features=LOADS,mean=[0.]*len(LOADS),scale=[1.]*len(LOADS),coefficients=[.1]+[0.]*len(LOADS)))
    monkeypatch.setattr(app,'ROOT',tmp_path);monkeypatch.setattr(app,'OUT',tmp_path/'shadow');monkeypatch.setattr(app,'datetime',Clock)
    monkeypatch.setattr(app,'verify_models',lambda:(frozen,dict(bundle_sha256='s'),dict(models=dict(linear=Model()))))
    row=dict(game_id=1,season=2027,season_type=2,date='2026-10-20T23:00Z',home_id=2,away_id=3,home_abbreviation='BOS',away_abbreviation='NOP',
             neutral_site=False,notes_headline='',status_type_state='pre',status_type_completed=False,home_score=0,away_score=0)
    monkeypatch.setattr(app.v1,'fetch_sources',lambda *args:(pd.DataFrame([row]),None,[dict(url='fixture',sha256='fixture')]))
    history=pd.DataFrame([dict(date='2026-04-01',season=2026)])
    monkeypatch.setattr(app.v1,'load_games',lambda *args:(history,[]))
    monkeypatch.setattr(app.v1,'current_history',lambda *args:pd.DataFrame())
    monkeypatch.setattr(app.v1,'forecast_features',lambda *args:(pd.Series({k:0. for k in app.v1.FEATURES}),'2026-04-01'))
    players=[dict(game_id='old',date='2026-04-01',athlete_id='star',name='homestar',minutes=30.,points=20.)]
    monkeypatch.setattr(app,'player_state',lambda *args:(players,True))
    report=dict(filename='fixture.pdf',sha256='fixture',published_at='2026-10-20T21:30Z',created_at='2026-10-20T21:30:01Z',parse_issues=[])
    home=dict(known=True,players=[dict(key='homestar',name='Home Star',status='Out')]);away=dict(known=True,players=[])
    monkeypatch.setattr(app,'report_for',lambda *args:(report,home,away,[report]))
    app.main();path=app.OUT/'predictions.jsonl';original=path.read_bytes()
    prediction=json.loads(original);assert not prediction['fallback'] and prediction['candidate_probability']!=prediction['control_probability']
    app.main();assert path.read_bytes()==original and not (app.OUT/'results.jsonl').exists()
    Clock.instant=datetime(2026,10,21,3,tzinfo=timezone.utc)
    row.update(status_type_state='post',status_type_completed=True,home_score=110,away_score=100)
    app.main();assert path.read_bytes()==original
    results=(app.OUT/'results.jsonl').read_bytes();assert json.loads(results)['actual_home_win']==1
    app.main();assert (app.OUT/'results.jsonl').read_bytes()==results
    dashboard=json.loads((app.OUT/'dashboard.json').read_text());assert dashboard['record']['candidate']['games']==1
