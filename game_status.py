"""Presentation-only score feed. Never grades a prediction or changes its probability."""
import math
import pandas as pd
from preview_data import team,game_id,stamp

STATES={'scheduled','live','final','postponed','canceled','delayed','suspended'}

def score(value):
    if isinstance(value,dict):value=value.get('value',value.get('displayValue'))
    try:n=float(value)
    except (TypeError,ValueError):return None
    return int(n) if math.isfinite(n) and n>=0 and n.is_integer() else None

def espn_game(sport,event,checked):
    try:
        c=event['competitions'][0];s=c['status']['type'];season=c.get('type',{})
        # CFB/NBA season type 2 is the regular season; NFL uses 2 as well.
        if int(event.get('season',{}).get('type',-1))!=2:return None
        t={x['homeAway']:x for x in c['competitors']};name=str(s.get('name','')).upper()
        state='final' if s.get('completed') is True and s.get('state')=='post' else 'live' if s.get('state')=='in' else 'scheduled'
        for word in ('postponed','canceled','cancelled','delayed','suspended'):
            if word.upper() in name:state='canceled' if word=='cancelled' else word
        def identity(side):
            v=t[side]['team'];return team(sport,v.get('location',v.get('displayName'))) if sport=='CFB' else team(sport,v['abbreviation'])
        h,a=score(t['home'].get('score')),score(t['away'].get('score'))
        if state=='scheduled':h=a=None
        if state=='final' and (h is None or a is None):return None
        return dict(game_id=game_id(event['id']),sport=sport,home_team=identity('home'),away_team=identity('away'),start_time_utc=stamp(c['date']).isoformat(),state=state,home_score=h,away_score=a,detail=str(s.get('shortDetail',s.get('description',''))),checked_at_utc=checked,source_url=f'https://www.espn.com/{"college-football" if sport=="CFB" else sport.lower()}/game/_/gameId/{event["id"]}')
    except (KeyError,ValueError,TypeError,IndexError):return None

def nhl_game(payload,checked):
    try:
        if int(payload.get('gameType',-1))!=2:return None
        raw=payload['gameState'];state={'FUT':'scheduled','PRE':'scheduled','LIVE':'live','CRIT':'live','FINAL':'final','OFF':'final','PPD':'postponed','SUSP':'suspended'}.get(raw)
        if state is None:return None
        h,a=score(payload['homeTeam'].get('score')),score(payload['awayTeam'].get('score'))
        if state=='scheduled':h=a=None
        if state=='final' and (h is None or a is None):return None
        period=payload.get('periodDescriptor',{});clock=payload.get('clock',{})
        detail='Final' if state=='final' else ('Intermission' if clock.get('inIntermission') else str(clock.get('timeRemaining','')))+' · '+str(period.get('periodType','REG'))+' '+str(period.get('number','')) if state=='live' else state.title()
        return dict(game_id=game_id(payload['id']),sport='NHL',home_team=payload['homeTeam']['abbrev'],away_team=payload['awayTeam']['abbrev'],start_time_utc=stamp(payload['startTimeUTC']).isoformat(),state=state,home_score=h,away_score=a,detail=detail.strip(' ·'),checked_at_utc=checked,source_url=f'https://www.nhl.com/gamecenter/{payload["id"]}')
    except (KeyError,ValueError,TypeError):return None

def matches(r,sport,home,away):
    return r and r.get('sport')==sport and team(sport,r.get('home_team'))==team(sport,home) and team(sport,r.get('away_team'))==team(sport,away) and r.get('state') in STATES

def display_state(r,settled=False,start=None,now=None):
    now=stamp(now) if now is not None else pd.Timestamp.now(tz='UTC')
    if r:
        state=r['state']
        if state=='final':return 'Final' if settled else 'Final · awaiting grading'
        if state=='live':return 'Live'
        return state.title()
    if settled:return 'Final · score unavailable'
    kickoff=stamp(start)
    if pd.notna(kickoff) and kickoff>now:return 'Scheduled'
    return 'Status unavailable'
