from datetime import datetime,timezone
import importlib.util
from pathlib import Path
import pandas as pd
import pytest

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

n=module('pipeline/nfl_availability.py','availability')
gate=module('pipeline/nfl_pregame_gate.py','pregame_gate')
builder=module('pipeline/build_predictions.py','frozen_builder')

def table(name,status='Out'):
    return '<div class="d3-o-section-sub-title">'+name+'</div><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in ['Player','Position','Injuries','Practice Status','Game Status'])+'</tr></thead><tbody><tr><td>Star Player</td><td>QB</td><td>Ankle</td><td>DNP</td><td>'+status+'</td></tr></tbody></table>'

def fixture():
    return '<h1>Official Latest NFL Injury Report for Players - Week 6 of the 2026 Season</h1><section class="nfl-o-injury-report__unit"><span class="nfl-c-matchup-strip__team-abbreviation">AZ</span><span class="nfl-c-matchup-strip__team-abbreviation">LAR</span>'+table('Cardinals')+table('Rams','Questionable')+'</section>'

def test_official_paired_tables_keep_players_on_correct_team_and_normalize_aliases():
    teams,_,_=n.injury_tables(fixture(),2026,6)
    assert teams['ARI']['players'][0]['status']=='Out'
    assert teams['LA']['players'][0]['status']=='Questionable'
    assert teams['ARI']['matchup']==['ARI','LA']
    with pytest.raises(ValueError,match='different season/week'):n.injury_tables(fixture(),2026,7)

def test_empty_inactive_section_is_pending_and_no_cross_team_spill():
    raw='<h3>TEXANS</h3><ul><li>QB Star Player</li><li>OT Blocker</li></ul><h3>JAGUARS</h3><h2>EARLY GAMES</h2><ul><li>QB Other Player</li></ul>'
    result=n.inactive_teams(raw)
    assert len(result['HOU'])==2 and 'JAX' not in result
    assert n.inactive_teams('<h3>49ERS</h3><ul><li>WR Pass Catcher</li></ul>')['SF'][0]['name']=='Pass Catcher'

@pytest.mark.parametrize('status,blocked,uncertain',[('Out',True,False),('Inactive',True,False),('Questionable',False,True),('Doubtful',False,True)])
def test_qb_states_distinguish_confirmed_absence_from_uncertainty(status,blocked,uncertain):
    injuries={'BAL':dict(matchup=['BAL','CLE'],players=[dict(name='Lamar Jackson',position='QB',status=status)])}
    context=n.team_context('BAL','CLE',injuries,{},'Lamar Jackson')
    assert context['qb_review_required']==blocked and context['qb_uncertain']==uncertain
    assert not n.team_context('BAL','CLE',injuries,{},'Tyler Huntley')['qb_review_required']

def test_wrong_matchup_and_absent_reports_never_mean_healthy_or_active():
    result=n.team_context('BAL','CLE',{'BAL':dict(matchup=['BAL','ATL'],players=[])},{},'Tyler Huntley')
    assert not result['injury_report_available'] and not result['inactives_published'] and result['qb_status']=='Unknown'

def test_inactive_list_overrides_questionable_without_inventing_active_status():
    result=n.team_context('BAL','CLE',{'BAL':dict(matchup=['BAL','CLE'],players=[dict(name='Lamar Jackson',position='QB',status='Questionable')])},
                          {'BAL':[dict(name='Lamar Jackson',position='QB',status='Inactive')]},'Lamar Jackson')
    assert result['qb_review_required'] and result['inactives_published'] and result['qb_status']=='Inactive'

def test_only_explicit_qb_announcement_with_unique_identity_is_resolved():
    players=pd.DataFrame([dict(gsis_id='00-0035993',display_name='Tyler Huntley',position='QB')])
    title='Ravens QB Lamar Jackson (ankle) out Sunday vs. Browns; Tyler Huntley to start again'
    assert n.resolve_qb(title,'BAL','CLE',players)['qb_id']=='00-0035993'
    assert n.resolve_qb(title.replace('to start','expected to start'),'BAL','CLE',players) is None
    assert n.resolve_qb(title,'BAL','ATL',players) is None
    assert n.resolve_qb(title,'BAL','CLE',pd.concat([players,players.assign(gsis_id='different')])) is None

def game(date='2026-10-18',time='09:30',season=2026,kind='REG'):
    return dict(season=season,game_type=kind,gameday=date,gametime=time,home_score='',away_score='')

def test_gate_uses_london_and_other_actual_kickoffs_without_weekday_assumptions():
    now=datetime(2026,10,18,12,30,tzinfo=timezone.utc)
    assert gate.should_run([game()],now)
    assert not gate.should_run([game()],datetime(2026,10,18,14,30,tzinfo=timezone.utc))
    assert not gate.should_run([game()],datetime(2026,10,18,9,tzinfo=timezone.utc))
    assert gate.should_run([game('2026-10-19','20:15')],datetime(2026,10,19,23,15,tzinfo=timezone.utc))

def test_january_uses_prior_season_and_preseason_does_not_open_gate():
    now=datetime(2027,1,9,20,tzinfo=timezone.utc)
    assert gate.season_for(now)==2026
    assert gate.should_run([game('2027-01-09','16:00')],now)
    assert not gate.should_run([game('2027-01-09','16:00',kind='PRE')],now)

def test_unresolved_qb_late_and_future_captures_cannot_enter_eligible_ledger():
    now=pd.Timestamp('2026-10-18T16:00Z')
    good=dict(game_id='good',qb_input_review_required=False,kickoff_utc='2026-10-18T17:00Z',captured_at_utc='2026-10-18T15:59Z')
    frame=pd.DataFrame([good,{**good,'game_id':'out','qb_input_review_required':True},
                        {**good,'game_id':'started','kickoff_utc':now.isoformat()},
                        {**good,'game_id':'future','captured_at_utc':'2026-10-18T16:01Z'}])
    original=frame.copy(deep=True)
    assert builder.eligible_snapshots(frame,now).game_id.tolist()==['good']
    pd.testing.assert_frame_equal(frame,original)
