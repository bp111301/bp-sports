"""Read-only recent-result context. No weights, predictions or grading are changed."""
import math
import pandas as pd

ALIASES={'CFB':{'Southern Mississippi':'Southern Miss','UT San Antonio':'UTSA','Connecticut':'UConn','UMass':'Massachusetts','Sam Houston State':'Sam Houston'},'NFL':{'WSH':'WAS','LAR':'LA','STL':'LA'},'NBA':{'GS':'GSW','BRK':'BKN','NO':'NOP','NY':'NYK','SA':'SAS','UTAH':'UTA','WSH':'WAS'}}
def team(sport,name):return ALIASES.get(sport,{}).get(str(name),str(name))
def stamp(v):return pd.to_datetime(v,utc=True,errors='coerce')
def flag(v):return str(v).lower() in ('true','1','1.0','yes')
def game_id(v):
    try:return str(int(v))
    except (ValueError,TypeError):return str(v)

def game(sport,gid,home,away,start,h,a,completed,regular=True):
    try:h,a=float(h),float(a)
    except (ValueError,TypeError):return None
    if not completed or not regular or not all(math.isfinite(x) and x>=0 for x in (h,a)) or pd.isna(stamp(start)):return None
    return dict(game_id=game_id(gid),home=team(sport,home),away=team(sport,away),start=stamp(start).isoformat(),home_score=h,away_score=a)

def football_games(frame,sport):
    rows=[]
    for r in frame.to_dict('records'):
        if sport=='CFB':g=game(sport,r['game_id'],r['home_team'],r['away_team'],r['start_date'],r.get('home_points'),r.get('away_points'),flag(r.get('completed')),str(r.get('season_type_id')) in ('2','2.0'))
        else:
            start=stamp(str(r['gameday'])+'T'+str(r.get('gametime') or '12:00')+'-04:00')
            # NFL source times are Eastern; handle winter's UTC offset as well.
            try:start=pd.Timestamp(str(r['gameday'])+' '+str(r.get('gametime') or '12:00')).tz_localize('America/New_York').tz_convert('UTC')
            except (ValueError,TypeError):continue
            g=game(sport,r['game_id'],r['home_team'],r['away_team'],start,r.get('home_score'),r.get('away_score'),pd.notna(r.get('home_score')) and pd.notna(r.get('away_score')),r.get('game_type')=='REG')
        if g:rows.append(g)
    return rows

def nhl_games(payload):
    rows=[]
    for r in payload.get('games',[]):
        g=game('NHL',r['id'],r['homeTeam']['abbrev'],r['awayTeam']['abbrev'],r['startTimeUTC'],r['homeTeam'].get('score'),r['awayTeam'].get('score'),r.get('gameState') in ('OFF','FINAL'),r.get('gameType')==2)
        if g:rows.append(g)
    return rows

def nba_games(payload):
    rows=[]
    for event in payload.get('events',[]):
        if str(event.get('seasonType',{}).get('type'))!='2':continue
        for c in event.get('competitions',[]):
            sides={v['homeAway']:v for v in c.get('competitors',[])}
            if set(sides)!= {'home','away'}:continue
            h,a=sides['home'],sides['away'];status=c.get('status',{}).get('type',{})
            g=game('NBA',event['id'],h['team']['abbreviation'],a['team']['abbreviation'],c.get('date',event.get('date')),h.get('score',{}).get('value') if isinstance(h.get('score'),dict) else h.get('score'),a.get('score',{}).get('value') if isinstance(a.get('score'),dict) else a.get('score'),status.get('completed') is True and status.get('state')=='post')
            if g:rows.append(g)
    return rows

def profile(games,sport,name,cutoff,start):
    cutoff=stamp(cutoff);start=stamp(start)
    if pd.isna(cutoff) or pd.isna(start) or cutoff>=start:raise ValueError('Preview needs a valid pregame cutoff')
    # Earlier Eastern dates avoid treating a same-day final published later as pregame knowledge.
    day=min(cutoff,start).tz_convert('America/New_York').date();name=team(sport,name);eligible={}
    for g in games:
        if name not in (g['home'],g['away']) or g['game_id'] in eligible:continue
        t=stamp(g['start'])
        if t>=cutoff or t>=start or t.tz_convert('America/New_York').date()>=day:continue
        home=g['home']==name;points=g['home_score'] if home else g['away_score'];allowed=g['away_score'] if home else g['home_score']
        eligible[g['game_id']]={**g,'for':points,'against':allowed,'opponent':g['away'] if home else g['home'],'outcome':'W' if points>allowed else 'L' if points<allowed else 'T'}
    rows=sorted(eligible.values(),key=lambda r:r['start']);n=len(rows)
    return dict(games=n,wins=sum(r['outcome']=='W' for r in rows),losses=sum(r['outcome']=='L' for r in rows),ties=sum(r['outcome']=='T' for r in rows),recent=[r['outcome'] for r in rows[-3:]],last=rows[-1] if rows else None,scored_per_game=sum(r['for'] for r in rows)/n if n else None,allowed_per_game=sum(r['against'] for r in rows)/n if n else None)
