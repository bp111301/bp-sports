import copy
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from injuries import parse_bbox,usable,cutoff_for,report_files,contexts,player_key,load_report
import injuries
from study import availability_features,COUNTS,LOADS,fit_offset,evaluate,VARIANTS
import study


def page_xml(older=False,continuation=False,wrong_team=False):
    # The old report body is 1 point left of its header; new body is 1 point right.
    x=[20,95,170,244,371,499,605];shift=-1 if older else 1
    root=ET.Element('doc')
    def page(header,items):
        p=ET.SubElement(root,'page',width='842',height='595')
        def words(text,left,y):
            for w in text.split():
                ET.SubElement(p,'word',xMin=str(left),xMax=str(left+len(w)*4),yMin=str(y),yMax=str(y+8)).text=w
                left+=len(w)*4+3
        words('Injury Report: 01/03/24 05:30 PM',300,20)
        if header:
            for label,left in zip(['Game Date','Game Time','Matchup','Team','Player Name','Current Status','Reason'],x):words(label,left,55)
        for y,cells in items:
            for text,left in zip(cells,x):words(text,left+shift,y)
        words('Page 1 of 2',280,550)
    page(True,[(80,['01/03/2024','07:00 (ET)','MIL@IND','Milwaukee Bucks','Star, Home','Out','Injury']),
               (110,['','','','','Bench, Two','Questionable','Illness'])])
    if continuation:
        page(False,[(80,['','','','','Another, Player','Probable','Rest']),
                    (110,['','','','Indiana Pacers' if not wrong_team else 'Los Angeles Lakers','Star, Away','Out','Injury'])])
    return ET.tostring(root,encoding='unicode')


@pytest.mark.parametrize('older',[True,False])
def test_pdf_physical_columns_and_headerless_page_continuation(older):
    teams,issues=parse_bbox(page_xml(older=older,continuation=True))
    assert not issues
    home=teams['2024-01-03|MIL@IND|MIL'];away=teams['2024-01-03|MIL@IND|IND']
    assert [p['key'] for p in home['players']]==['homestar','twobench','playeranother']
    assert [p['status'] for p in home['players']]==['Out','Questionable','Probable']
    assert away['players'][0]['key']=='awaystar'


def test_wrong_team_is_not_assigned_to_a_matchup():
    teams,issues=parse_bbox(page_xml(continuation=True,wrong_team=True))
    assert any('team_matchup_mismatch' in x for x in issues)
    assert '2024-01-03|MIL@IND|LAL' not in teams


def test_embedded_and_creation_timestamps_both_precede_cutoff():
    cutoff=pd.Timestamp('2024-01-03T23:00Z')
    r=dict(status='parsed',published_at='2024-01-03T22:30Z',created_at='2024-01-03T22:30:02Z',parse_issues=[])
    assert usable(r,cutoff)
    assert not usable({**r,'created_at':'2024-01-03T23:00:01Z'},cutoff)
    assert not usable({**r,'published_at':'2024-01-03T23:30Z'},cutoff)
    assert not usable({**r,'parse_issues':['unrecognized_team']},cutoff)
    assert not usable({'status':'unavailable'},cutoff)


def test_cutoff_uses_earlier_tipoff_or_evening_limit_and_dst():
    assert cutoff_for('2024-01-04T03:00Z')==pd.Timestamp('2024-01-03T23:00Z')
    assert cutoff_for('2024-03-24T17:00Z')==pd.Timestamp('2024-03-24T16:00Z')
    assert cutoff_for('2024-03-11T02:00Z')==pd.Timestamp('2024-03-10T22:00Z')
    assert cutoff_for('2024-11-04T03:00Z')==pd.Timestamp('2024-11-03T23:00Z')
    assert report_files(pd.Timestamp('2024-01-03T23:00Z'))[0]=='Injury-Report_2024-01-03_05PM.pdf'


def test_other_date_or_matchup_never_becomes_healthy_context():
    report={'teams':{'2024-01-03|MIL@IND|MIL':{'known':True,'players':[]}}}
    game=dict(date='2024-01-04',home_team='IND',away_team='MIL')
    assert not any(c['known'] for c in contexts(game,report))


def fixture():
    games=pd.DataFrame([dict(game_id=str(i),season=2024,date=f'2024-01-0{i}') for i in [1,2,3]])
    contexts={str(i):dict(home=dict(known=True,players=[dict(key='homestar',status='Out')]),away=dict(known=True,players=[])) for i in [1,2,3]}
    players={str(i):[dict(athlete_id='star',name='homestar',minutes=30.,points=20.)] for i in [1,2,3]}
    return games,contexts,players


def test_player_importance_uses_only_earlier_dates_and_names():
    games,context,players=fixture();original=availability_features(games,context,players)
    changed=copy.deepcopy(players);changed['2'][0].update(minutes=50.,points=40.);changed['3'][0].update(name='future',minutes=60.)
    result=availability_features(games,context,changed)
    np.testing.assert_allclose(original.iloc[:2][COUNTS+LOADS],result.iloc[:2][COUNTS+LOADS])
    assert original.iloc[0].matched_impact_players==0
    assert original.iloc[1].minutes_Out_diff==30
    assert original.iloc[2].minutes_Out_diff!=result.iloc[2].minutes_Out_diff


def test_questionable_is_separate_from_out_and_unknown_is_explicit():
    games,context,players=fixture();context['2']['home']['players'][0]['status']='Questionable'
    context['2']['away']['known']=False
    frame=availability_features(games,context,players)
    assert not frame.iloc[1].both_known
    assert frame.iloc[1].minutes_Questionable_diff==30 and frame.iloc[1].minutes_Out_diff==0


def test_future_season_is_rejected():
    games,context,players=fixture();games.loc[0,'season']=2026
    with pytest.raises(ValueError,match='future input'):availability_features(games,context,players)


def test_offset_fit_does_not_use_test_labels_or_test_scaling():
    rng=np.random.default_rng(2)
    train=pd.DataFrame(dict(season=np.repeat([2021,2022],300),y=rng.integers(0,2,600),baseline_probability=np.repeat(.6,600),x=rng.normal(size=600)))
    test=pd.DataFrame(dict(season=[2023,2023],y=[1,0],baseline_probability=[.6,.7],x=[50.,60.]))
    p,fit=fit_offset(train,test,['x']);changed=test.copy();changed.y=1-changed.y
    q,again=fit_offset(train,changed,['x'])
    np.testing.assert_allclose(p,q)
    assert fit==again and abs(fit['mean'][0]-train.x.mean())<1e-12
    with pytest.raises(ValueError,match='Nonchronological'):fit_offset(train.assign(season=2023),test,['x'])
    with pytest.raises(ValueError,match='Insufficient'):fit_offset(train.iloc[:100],test,['x'])


def test_name_normalization_preserves_suffix_identity():
    assert player_key('Carey Jr., Vernon')==player_key('Vernon Carey Jr.')
    assert player_key('Payton II, Gary')!=player_key('Gary Payton')


def test_missing_report_predictions_fall_back_exactly_for_every_candidate(monkeypatch):
    monkeypatch.setattr(study.v1,'bootstrap',lambda frame:{'fixture_only':True})
    rows=[]
    for season in [2021,2022,2023,2024,2025]:
        count=300 if season<2023 else 4
        for i in range(count):
            row=dict(season=season,date=f'{season}-01-03',y=i%2,
                     both_known=season<2023 or i<2,baseline_probability=.6000000000000001 if i%2 else .4)
            row.update({c:float(i%3) for c in COUNTS+LOADS});rows.append(row)
    _,predictions=evaluate(pd.DataFrame(rows))
    missing=predictions[~predictions.both_known]
    assert len(missing)==6
    for candidate in VARIANTS:
        assert np.array_equal(missing[candidate].to_numpy(),missing.baseline_probability.to_numpy())


def test_offline_source_audit_never_downloads_or_invents_a_report(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Offline mode attempted network')
    monkeypatch.setattr(injuries.requests,'get',forbidden)
    report=load_report('Injury-Report_2024-01-03_05PM.pdf',tmp_path,offline=True)
    assert report['status']=='not_retrieved'
    assert not usable(report,pd.Timestamp('2024-01-03T23:00Z'))
    assert 'sha256' not in report and 'teams' not in report
