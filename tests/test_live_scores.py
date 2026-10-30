import copy
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from game_status import espn_game
from live_scores import collect_scores, merge_games

NOW = pd.Timestamp('2026-10-30T01:45Z')


def event(gid='1', sport='NFL', season=2, state='in'):
    names = {'NFL':('GB','CAR'), 'NHL':('TB','WPG'), 'CFB':('Troy','Southern Mississippi'),
             'NBA':('NO','SAC'), 'CBB':('Villanova Wildcats','Notre Dame Fighting Irish')}
    home, away = names[sport]
    return dict(id=gid,season=dict(type=season),competitions=[dict(date='2026-10-29T23:00Z',
        status=dict(type=dict(state=state,completed=state=='post',name='STATUS_FINAL' if state=='post' else 'STATUS_IN_PROGRESS')),
        competitors=[dict(homeAway=side,score=score,team=dict(abbreviation=name,location=name,displayName=name))
                     for side,name,score in [('home',home,'14'),('away',away,'7')]])])


def test_direct_poll_checks_all_five_sports_and_maps_existing_game_ids():
    nfl=espn_game('NFL',event(), '2026-10-30T00:00Z')
    nhl=espn_game('NHL',event('2','NHL'), '2026-10-30T00:00Z')
    archive=dict(updated_at_utc='2026-10-30T00:00Z',games={
        'NFL:2026_09_CAR_GB':{**nfl,'game_id':'2026_09_CAR_GB','home_score':0},
        'NHL:2026020195':{**nhl,'game_id':'2026020195','home_score':0}})
    before=copy.deepcopy(archive)
    def fetcher(url):
        sport=next(s for s, path in [('NFL','football/nfl'),('CFB','football/college-football'),
            ('NHL','hockey/nhl'),('NBA','basketball/nba'),('CBB','basketball/mens-college-basketball')] if path in url)
        return {'events':[event('2' if sport=='NHL' else '1',sport)]} if 'dates=20261029&' in url else {'events':[]}
    result=collect_scores(archive,NOW,fetcher)
    assert archive==before
    assert result['mode']=='direct_live' and not result['errors']
    assert len(result['source_checks'])==10
    assert {c['sport'] for c in result['source_checks']}=={'NFL','CFB','NHL','NBA','CBB'}
    assert result['games']['NFL:2026_09_CAR_GB']['home_score']==14
    assert result['games']['NHL:2026020195']['home_team']=='TBL'
    assert result['games']['CBB:1']['home_team']=='Villanova Wildcats'
    assert '/mens-college-basketball/' in result['games']['CBB:1']['source_url']
    assert not any('actual_home_win' in row for row in result['games'].values())


def test_failed_source_keeps_old_game_timestamp_and_reports_partial_status():
    old=espn_game('NBA',event(sport='NBA'),'2026-10-30T00:00Z')
    archive=dict(updated_at_utc='2026-10-30T00:00Z',games={'NBA:1':old})
    def fetcher(url):
        if '/nba/' in url:raise OSError('unavailable')
        return {'events':[]}
    result=collect_scores(archive,NOW,fetcher)
    assert result['mode']=='partial_live' and len(result['errors'])==2
    assert result['games']['NBA:1']==old
    failed=collect_scores(archive,NOW,lambda url: (_ for _ in ()).throw(OSError('offline')))
    assert failed['mode']=='saved_fallback'
    assert failed['updated_at_utc']==archive['updated_at_utc']


def test_id_mapping_does_not_cross_game_dates_or_reverse_teams_or_regress_finals():
    game=espn_game('NFL',event(),'2026-10-30T00:00Z')
    old={**game,'game_id':'previous','start_time_utc':'2026-10-22T23:00Z','home_score':0}
    result=merge_games({'NFL:previous':old},[game])
    assert result['NFL:previous']==old
    reversed_game={**game,'home_team':'CAR','away_team':'GB'}
    assert merge_games({'NFL:old':game},[reversed_game])['NFL:old']==game
    final={**game,'state':'final'}
    assert merge_games({'NFL:1':final},[game])['NFL:1']==final
    assert espn_game('CBB',event(sport='CBB',season=1),NOW.isoformat()) is None
    hockey={**game,'sport':'NHL','game_id':'hockey','home_team':'DET','away_team':'CHI'}
    basketball={**hockey,'sport':'NBA','game_id':'basketball','home_score':100}
    assert merge_games({'NBA:basketball':basketball},[hockey])['NBA:basketball']==basketball


def test_omitted_college_game_is_resolved_by_id_and_wrong_teams_are_rejected():
    old=espn_game('CFB',event('42','CFB'),'2026-10-30T00:00Z')
    archive=dict(updated_at_utc='2026-10-30T00:00Z',games={'CFB:42':old})
    def fetcher(url):return {'header':event('42','CFB',state='post')} if '/summary?' in url else {'events':[]}
    result=collect_scores(archive,NOW,fetcher)
    assert result['games']['CFB:42']['state']=='final'
    assert not result['errors']
    def wrong(url):return {'header':event('41','CFB',state='post')} if '/summary?' in url else {'events':[]}
    rejected=collect_scores(archive,NOW,wrong)
    assert rejected['games']['CFB:42']==old and rejected['errors']


def test_fragment_rerun_reuses_fresh_cache_instead_of_clearing_and_refetching():
    with patch('game_center_ui.load_scores',return_value={'updated_at_utc':NOW.isoformat(),'games':{}}):
        app=AppTest.from_string("from game_center_ui import render_score_refresh\nrender_score_refresh()")
        app.session_state['bp_score_version']='2026-10-30T00:00Z'
        with patch('game_center_ui.st.cache_data.clear',side_effect=AssertionError('must retain fresh cache')):
            app.run(timeout=10)
        assert not app.exception
        assert app.session_state['bp_score_version']==NOW.isoformat()


def test_backup_score_targets_include_regular_season_cbb(tmp_path,monkeypatch):
    from pipeline import build_game_status as builder
    for folder in ['data/ledger','data/cfb/ledger']:(tmp_path/folder).mkdir(parents=True,exist_ok=True)
    (tmp_path/'data/matchup_previews.json').write_text('{"games":{}}')
    for path in ['data/ledger/prediction_ledger.csv','data/cfb/ledger/prediction_ledger.csv']:
        (tmp_path/path).write_text('game_id,home_team,away_team,kickoff_utc\n')
    row=dict(game_id='42',season_type=2,home_team='Villanova Wildcats',away_team='Notre Dame Fighting Irish',start_time_utc='2026-11-01T14:30Z')
    class Response:
        text='game_id,home_team,away_team,start_time_utc\n'
        def json(self):return dict(feed_status='research_preview',predictions=[row,{**row,'game_id':'preseason','season_type':1}])
    monkeypatch.setattr(builder,'ROOT',tmp_path)
    monkeypatch.setattr(builder,'get',lambda url:Response())
    rows,errors=builder.targets()
    assert not errors
    assert any(r['sport']=='CBB' and r['game_id']=='42' for r in rows)
    assert not any(r['game_id']=='preseason' for r in rows)
