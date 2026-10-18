"""Official NFL availability context. No injury coefficients or retrospective edits."""
from __future__ import annotations
import argparse,hashlib,io,json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import pandas as pd
import requests
from bs4 import BeautifulSoup

INJURIES='https://www.nfl.com/injuries/'
PLAYERS='https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
NAMES=dict(zip(['Cardinals','Falcons','Ravens','Bills','Panthers','Bears','Bengals','Browns','Cowboys','Broncos','Lions','Packers','Texans','Colts','Jaguars','Chiefs','Chargers','Rams','Raiders','Dolphins','Vikings','Patriots','Saints','Giants','Jets','Eagles','Steelers','49ers','Seahawks','Buccaneers','Titans','Commanders'],['ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB','HOU','IND','JAX','KC','LAC','LA','LV','MIA','MIN','NE','NO','NYG','NYJ','PHI','PIT','SF','SEA','TB','TEN','WAS']))
ALIASES={'LAR':'LA','JAC':'JAX','WSH':'WAS','AZ':'ARI'}
STATUSES={'Out','Doubtful','Questionable'}

def canonical(value):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',str(value)).lower())
def code(value):return ALIASES.get(str(value),str(value))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def get(url):
    r=requests.get(url,headers={'User-Agent':'BP-Sports-Availability/1.0'},timeout=(10,30));r.raise_for_status()
    if len(r.content)>12*1024*1024:raise ValueError('Source exceeds size limit')
    return r.content,dict(url=url,retrieved_at_utc=datetime.now(timezone.utc).isoformat(),sha256=sha(r.content),http_status=r.status_code)

def injury_tables(raw,season,week):
    soup=BeautifulSoup(raw,'html.parser')
    title=' '.join(x.get_text(' ',strip=True) for x in soup.find_all('h1'))
    if not re.search(r'Week\s*'+str(week)+r'\b',title,re.I) or str(season) not in title:raise ValueError('Official injury page has a different season/week')
    teams={}
    for unit in soup.select('section.nfl-o-injury-report__unit'):
        matchup=[code(x.get_text(strip=True)) for x in unit.select('.nfl-c-matchup-strip__team-abbreviation')]
        titles=unit.select('.d3-o-section-sub-title');tables=unit.find_all('table')
        if len(matchup)!=2 or len(titles)!=len(tables):continue
        for label,table in zip(titles,tables):
            team=NAMES.get(label.get_text(' ',strip=True))
            if team not in matchup:continue
            headers=[x.get_text(' ',strip=True) for x in table.select('thead th')]
            if headers!=['Player','Position','Injuries','Practice Status','Game Status']:continue
            players=[]
            for row in table.select('tbody tr'):
                cells=[x.get_text(' ',strip=True) for x in row.find_all('td')]
                if len(cells)!=5:raise ValueError('Malformed official injury row')
                if cells[4] in STATUSES:players.append(dict(name=cells[0],position=cells[1],injury=cells[2],status=cells[4],source_url=INJURIES))
            teams[team]=dict(matchup=matchup,players=players,submitted=True)
    if not teams:raise ValueError('Official injury tables unavailable')
    inactive_links=[];news=[]
    for a in soup.select('a[href]'):
        url=urljoin(INJURIES,a['href']);headline=a.get_text(' ',strip=True)
        if urlparse(url).hostname!='www.nfl.com':continue
        if re.search(r'nfl-week-'+str(week)+r'-inactives\b',url) and str(season) in url:inactive_links.append(url)
        if a.find('h3') and re.search(r'\b(?:will|to) start\b',headline,re.I) and not re.search(r'expected|planning|likely|could|questionable',headline,re.I):news.append(dict(url=url,headline=headline))
    return teams,list(dict.fromkeys(inactive_links)),list({n['url']:n for n in news}.values())

def inactive_teams(raw):
    soup=BeautifulSoup(raw,'html.parser');teams={}
    for heading in soup.find_all(['h2','h3']):
        label=heading.get_text(' ',strip=True).casefold();team=next((v for k,v in NAMES.items() if k.casefold()==label),None)
        if team is None:continue
        players=[]
        for node in heading.find_all_next(['h2','h3','li']):
            if node.name in ('h2','h3'):break
            m=re.fullmatch(r'([A-Z]{1,5})\s+(.+)',node.get_text(' ',strip=True))
            if m:players.append(dict(position=m[1],name=m[2],status='Inactive'))
        # An empty or absent section means not published, never an active roster.
        if players:teams[team]=players
    return teams

def resolve_qb(headline,team,opponent,players):
    nick={v:k for k,v in NAMES.items()}
    if nick.get(team,'?').casefold() not in headline.casefold() or nick.get(opponent,'?').casefold() not in headline.casefold():return None
    if re.search(r'expected|planning|likely|could|questionable',headline,re.I):return None
    # Conservative explicit headline grammar; no inferred next-man-up decision.
    matches=re.findall(r'(?:;\s*|\bQB\s+)([A-Z][A-Za-z.\x27 -]+?)\s+(?:will|to) start\b',headline)
    if len(matches)!=1:return None
    name=matches[0].strip();candidates=players[(players.position=='QB')&players.display_name.map(canonical).eq(canonical(name))&players.gsis_id.notna()]
    ids=candidates.gsis_id.unique()
    if len(ids)!=1:return None
    return dict(team=team,qb_name=str(candidates.iloc[0].display_name),qb_id=str(ids[0]))

def kickoff(schedule):
    text=schedule.gameday.astype(str).str[:10]+' '+schedule.gametime.fillna('12:00').astype(str)
    return pd.to_datetime(text).dt.tz_localize('America/New_York').dt.tz_convert('UTC')

def team_context(team,opponent,injuries,inactives,assumed):
    source=injuries.get(team,{});valid=source.get('matchup') in ([team,opponent],[opponent,team])
    players=source.get('players',[]) if valid else []
    merged={canonical(p['name']):dict(p) for p in players}
    for p in inactives.get(team,[]):merged[canonical(p['name'])]={**merged.get(canonical(p['name']),{}),**p}
    rows=list(merged.values());qb=next((p for p in rows if canonical(p['name'])==canonical(assumed)),None)
    blocked=bool(qb and qb['status'] in ('Out','Inactive'))
    uncertain=bool(qb and qb['status'] in ('Questionable','Doubtful'))
    return dict(team=team,injury_report_available=bool(valid),inactives_published=team in inactives,
                assumed_qb=assumed,qb_status=qb['status'] if qb else 'No game designation found' if valid else 'Unknown',
                qb_review_required=blocked,qb_uncertain=uncertain,players=rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--season',type=int,required=True);p.add_argument('--data-dir',default='runtime');p.add_argument('--overrides',default='config/qb_overrides.json');p.add_argument('--output',default='data/current/nfl_availability.json');a=p.parse_args()
    root=Path(a.data_dir);schedule=pd.read_csv(root/'schedules.csv');schedule=schedule[(schedule.season==a.season)&schedule.game_type.eq('REG')].copy();schedule['kickoff_utc']=kickoff(schedule)
    for c in ['home_team','away_team']:schedule[c]=schedule[c].map(code)
    now=pd.Timestamp.now(tz='UTC');future=schedule[(schedule.kickoff_utc>now)&schedule.home_score.isna()&schedule.away_score.isna()];week=int(future.week.min()) if len(future) else None
    path=Path(a.output);old=json.loads(path.read_text()) if path.exists() else {};games=dict(old.get('games',{}));receipts=[];errors=[];injuries={};inactive={};news=[];inactive_url=None
    if week is not None:
        try:
            raw,receipt=get(INJURIES);receipts.append(receipt);injuries,links,news=injury_tables(raw,a.season,week)
            if links:
                inactive_url=links[0];raw,receipt=get(inactive_url);receipts.append(receipt);inactive=inactive_teams(raw)
                for players in inactive.values():
                    for player in players:player['source_url']=inactive_url
        except (requests.RequestException,ValueError) as error:errors.append(str(error))
    manual=json.loads(Path(a.overrides).read_text()) if Path(a.overrides).exists() else {};effective=dict(manual);player_map=None
    for r in future[future.week.eq(week)].to_dict('records'):
        checked=pd.Timestamp.now(tz='UTC')
        if checked>=r['kickoff_utc']:continue
        sides={};entry_over=dict(manual.get(r['game_id'],{}))
        for side,other in [('home','away'),('away','home')]:
            team,opponent=r[side+'_team'],r[other+'_team'];override=entry_over.get(side,{})
            assumed=override.get('qb_name',r.get(side+'_qb_name')) if override.get('team',team)==team else r.get(side+'_qb_name')
            if pd.isna(assumed):assumed='Unknown'
            context=team_context(team,opponent,injuries,inactive,assumed)
            if context['qb_review_required']:
                for item in news:
                    try:
                        article,receipt=get(item['url']);receipts.append(receipt);soup=BeautifulSoup(article,'html.parser');title=soup.find('h1')
                        date=soup.find('meta',attrs={'property':'article:published_time'})
                        if date is None:
                            script=' '.join(s.get_text() for s in soup.find_all('script',type='application/ld+json'));m=re.search(r'"datePublished"\s*:\s*"([^"]+)"',script);published=pd.to_datetime(m[1],utc=True) if m else pd.NaT
                        else:published=pd.to_datetime(date.get('content'),utc=True,errors='coerce')
                        if pd.isna(published) or not checked-pd.Timedelta(days=7)<=published<=checked:continue
                        if player_map is None:
                            raw,receipt=get(PLAYERS);receipts.append(receipt);player_map=pd.read_csv(io.BytesIO(raw),low_memory=False)
                        resolved=resolve_qb(title.get_text(' ',strip=True) if title else '',team,opponent,player_map)
                        if resolved:
                            resolved.update(status_note=resolved['qb_name']+' confirmed to start by NFL report',source_url=item['url'],verified_at_utc=checked.isoformat(),source_published_at_utc=published.isoformat())
                            entry_over[side]=resolved;context=team_context(team,opponent,injuries,inactive,resolved['qb_name']);context['starter_source_url']=item['url'];break
                    except (requests.RequestException,ValueError,KeyError) as error:errors.append(str(error))
            if entry_over.get(side,{}).get('source_url'):context['starter_source_url']=entry_over[side]['source_url']
            sides[side]=context
        effective[r['game_id']]=entry_over
        completed=pd.Timestamp.now(tz='UTC')
        if completed>=r['kickoff_utc']:continue
        games[r['game_id']]=dict(game_id=r['game_id'],season=a.season,week=week,home_team=r['home_team'],away_team=r['away_team'],
            kickoff_utc=r['kickoff_utc'].isoformat(),checked_at_utc=completed.isoformat(),home=sides['home'],away=sides['away'],
            qb_review_required=any(v['qb_review_required'] for v in sides.values()),qb_uncertain=any(v['qb_uncertain'] for v in sides.values()),
            source_errors=errors.copy(),injuries_url=INJURIES,inactives_url=inactive_url,
            source_receipts=list(receipts),
            near_kickoff_check=bool(r['kickoff_utc']-checked<=pd.Timedelta(minutes=90)))
    report=dict(season=a.season,week=week,updated_at_utc=datetime.now(timezone.utc).isoformat(),games=games,source_receipts=receipts,source_errors=errors,
                scope='Official injury reports/inactives and explicit QB starter announcements; no non-QB probability coefficients')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (root/'qb_overrides_effective.json').write_text(json.dumps(effective,indent=2)+'\n')
    print(json.dumps(dict(week=week,checked_games=sum(g.get('week')==week for g in games.values()),qb_review_games=[k for k,g in games.items() if g.get('week')==week and g.get('qb_review_required')],source_errors=errors),indent=2))

if __name__=='__main__':main()
