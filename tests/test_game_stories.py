"""Game stories describe verified past results; probabilities stay untouched."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from preview_data import game,profile,previous_meetings,basketball_schedule_games
from matchup_preview_ui import matchup_story,comparison_rows,comparison_html,valid_latest_context


def fixture(sport='CFB'):
    home,away=('DET','CHI') if sport=='NFL' else ('Home Team','Away Team')
    games=[game(sport,str(i),home,'Other Team',f'2026-10-{i+1:02}T19:00Z',30,10,True) for i in range(6)]
    games += [game(sport,'away',away,'Other Team','2026-10-06T19:00Z',21,28,True),
              game(sport,'meeting',home,away,'2025-11-01T19:00Z',24,17,True)]
    cutoff,start='2026-10-10T12:00Z','2026-10-11T19:00Z'
    form=lambda name:profile(games[:-1],sport,name,cutoff,start)
    context=dict(sport=sport,game_id='next',home_team=home,away_team=away,cutoff_utc=cutoff,start_time_utc=start,
                 home_form=form(home),away_form=form(away),previous_meetings=previous_meetings(games,sport,home,away,cutoff,start))
    row=dict(game_id='next',home_team=home,away_team=away,home_win_prob=.7,created_at_utc=cutoff,start_time_utc=start,
             v4_pick=home,v4_adjusted_confidence=.7,captured_at_utc=cutoff)
    return row,context,games


@pytest.mark.parametrize('sport',['NFL','CFB','NHL','NBA','CBB'])
def test_story_compares_both_sides_and_uses_only_verified_previous_meeting(sport):
    row,context,_=fixture(sport);before=copy.deepcopy((row,context))
    text=' '.join(matchup_story(sport,row,context))
    assert '30.0' in text and '28.0' in text and '21.0' in text and '10.0' in text
    assert '24–17' in text and 'Nov 1, 2025' in text
    assert '5–0 in 5' in text and '0–1 in 1' in text
    assert (row,context)==before
    assert comparison_rows(sport,context)[1][0]==('Goals' if sport=='NHL' else 'Points')+' scored / game'


def test_recent_form_is_limited_to_five_prior_finals_and_excludes_same_day():
    _,context,games=fixture()
    late=game('CFB','same','Home Team','Other Team','2026-10-10T10:00Z',999,0,True)
    form=profile(games[:-1]+[late],'CFB','Home Team','2026-10-10T12:00Z','2026-10-11T19:00Z')
    assert form['games']==6 and form['recent_sample']==5
    assert form['recent_scored_per_game']==30 and form['scored_per_game']==30
    assert form['recent_games'][0]['game_id']=='5'
    assert game('CFB','bad','Home Team','Other Team','2026-10-01T19:00Z',30.5,10,True) is None


def test_prior_meetings_reject_same_day_future_other_opponents_and_duplicates():
    _,_,games=fixture()
    same_day=game('CFB','today','Home Team','Away Team','2026-10-10T10:00Z',99,0,True)
    future=game('CFB','future','Home Team','Away Team','2026-10-12T19:00Z',0,99,True)
    found=previous_meetings(games+games+[same_day,future],'CFB','Home Team','Away Team','2026-10-10T12:00Z','2026-10-11T19:00Z')
    assert [r['game_id'] for r in found]==['meeting']


def test_missing_context_and_head_to_head_do_not_invent_stats_or_meetings():
    row,context,_=fixture()
    context['previous_meetings']=[]
    assert 'previous meeting' not in ' '.join(matchup_story('CFB',row,context))
    text=' '.join(matchup_story('CFB',row,None))
    assert '70.0%' in text and 'not available' in text and '30.0 points' not in text


def test_latest_context_cannot_use_different_game_kickoff_or_postgame_stats():
    row,context,_=fixture();now='2026-10-10T13:00Z'
    assert valid_latest_context(context,'CFB',row,now)==context
    for change in [{'game_id':'wrong'},{'start_time_utc':'2026-10-12T19:00Z'},{'cutoff_utc':'2026-10-11T19:01Z'}]:
        assert valid_latest_context({**context,**change},'CFB',row,now) is None


def test_comparison_escapes_team_names_and_preserves_record_sample():
    row,context,_=fixture();row['away_team']='<script>alert(1)</script>'
    text=comparison_html('CFB',row,context)
    assert '<script>' not in text and '&lt;script&gt;' in text
    assert '6–0' in text and '+20.0' in text


@pytest.mark.parametrize('sport',['NBA','CBB'])
def test_basketball_story_archive_requires_regular_season_final_and_correct_year(sport):
    base=dict(game_id=1,season=2027,season_type=2,status_type_state='post',status_type_completed=True,
              date='2026-10-06T19:00Z',home_score=90,away_score=80,home_abbreviation='DET',away_abbreviation='CHI',
              home_display_name='Home Team',away_display_name='Away Team')
    rows=[base,{**base,'game_id':2,'status_type_completed':False},{**base,'game_id':3,'season_type':1},
          {**base,'game_id':4,'season':2026},{**base,'game_id':5,'home_score':float('nan')}]
    found=basketball_schedule_games(pd.DataFrame(rows),sport,2027)
    assert len(found)==1 and found[0]['home_score']==90


def test_cbb_compact_opens_shared_story_and_stats_dialog():
    from matchup_details_ui import detail_payload,render_details
    row,context,_=fixture('CBB')
    row.update(created_at_utc='2026-10-10T12:00Z',status='pending')
    payload=detail_payload('CBB',row)
    with patch('matchup_preview_ui.load_previews',return_value={'CBB:next':context}),patch('game_center_ui.load_scores',return_value={}):
        import matchup_details_ui
        matchup_details_ui._story_fixture=payload
        app=AppTest.from_string('import matchup_details_ui as ui\nui.render_details(ui._story_fixture,now="2026-10-10T13:00Z")').run()
    assert not app.exception
    assert any('Matchup synopsis' in m.value for m in app.markdown)
    assert any('story-compare' in m.value for m in app.markdown)
    assert any(m.label=='Saved confidence' and m.value=='70.0%' for m in app.metric)


def test_story_loader_prefers_current_feed_and_retains_saved_fallback(tmp_path,monkeypatch):
    import io
    import matchup_preview_ui as ui
    saved=tmp_path/'stories.json';saved.write_text(json.dumps({'games':{'old':{'version':1}}}))
    monkeypatch.setattr(ui,'PREVIEW_PATH',saved)
    monkeypatch.setattr(ui,'urlopen',lambda *a,**k:io.BytesIO(b'{"games":{"new":{"version":2}}}'))
    ui.load_previews.clear()
    try:
        assert ui.load_previews()=={'new':{'version':2}}
        ui.load_previews.clear()
        def outage(*args,**kwargs):raise TimeoutError('source delayed')
        monkeypatch.setattr(ui,'urlopen',outage)
        assert ui.load_previews()=={'old':{'version':1}}
    finally:ui.load_previews.clear()


def test_preview_source_retries_temporary_errors_without_changing_any_predictions(monkeypatch):
    import requests
    from pipeline import build_matchup_previews as builder
    calls=[];waits=[]
    response=requests.Response();response.status_code=502
    def fetch(*args,**kwargs):
        calls.append(args[0])
        if len(calls)==1:raise requests.HTTPError(response=response)
        good=requests.Response();good.status_code=200;good._content=b'{}';return good
    monkeypatch.setattr(builder.requests,'get',fetch);monkeypatch.setattr(builder.time,'sleep',waits.append)
    assert builder.get('https://example.test/results').status_code==200
    assert len(calls)==2 and waits==[1]
