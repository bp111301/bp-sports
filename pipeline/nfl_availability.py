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
SCHEDULE='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
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
        if re.search(r'\b(?:will|to) start\b',headline,re.I) and not re.search(r'expected|planning|likely|could|questionable',headline,re.I):news.append(dict(url=url,headline=headline))
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


def confirmation_valid(item,team,checked,start):
    verified=pd.to_datetime(item.get('verified_at_utc'),utc=True,errors='coerce')
    published=pd.to_datetime(item.get('source_published_at_utc'),utc=True,errors='coerce')
    return bool(item.get('team')==team and item.get('qb_id') and item.get('qb_name')
                and urlparse(item.get('source_url','')).scheme=='https'
                and urlparse(item.get('source_url','')).hostname
                and pd.notna(verified) and checked-pd.Timedelta(days=7)<=verified<=checked<start
                and ('source_published_at_utc' not in item or (pd.notna(published) and published<=verified)))


def starter_context(team,opponent,name,pid,override,announcements,injuries,inactives,previous,checked,start):
    """Resolve explicit current evidence; never infer a starter from a roster."""
    selected=dict(override) if override.get('team',team)==team else {}
    invalid_override=False
    for field in ['verified_at_utc','source_published_at_utc']:
        if field in selected:
            value=pd.to_datetime(selected[field],utc=True,errors='coerce')
            if pd.isna(value) or value>checked or value>=start:invalid_override=True
    if invalid_override:selected={}
    confirmed=confirmation_valid(selected,team,checked,start)
    prior=dict(team=team,qb_id=previous.get('assumed_qb_id'),qb_name=previous.get('assumed_qb'),
               source_url=previous.get('starter_source_url'),verified_at_utc=previous.get('starter_verified_at_utc'),
               source_kind=previous.get('assumption_source'))
    candidates={item['qb_id']:item for item in ([prior] if previous.get('qb_evidence_state')=='confirmed' else [])+announcements
                if confirmation_valid(item,team,checked,start)}
    conflict=len(candidates)>1 or bool(confirmed and candidates and selected['qb_id'] not in candidates)
    if len(candidates)==1 and not conflict:selected=dict(next(iter(candidates.values())));confirmed=True
    assumed=selected.get('qb_name',name)
    assumed_id=selected.get('qb_id',pid)
    if pd.isna(assumed):assumed='Unknown'
    context=team_context(team,opponent,injuries,inactives,assumed)
    issues=[]
    if not context['injury_report_available']:issues.append('injury_report_unavailable')
    if not confirmed:issues.append('starter_unconfirmed')
    missing=pd.isna(assumed_id) or not str(assumed_id).strip() or assumed=='Unknown'
    if missing:issues.append('missing_qb_identity')
    if conflict:issues.append('conflicting_starter_confirmations')
    if invalid_override:issues.append('invalid_override_time')
    # A provider outage must not silently clear a known absence for this game.
    retained=(not context['injury_report_available'] and not context['inactives_published']
              and previous.get('qb_review_required') and canonical(previous.get('assumed_qb'))==canonical(assumed))
    if retained:
        context['qb_status']=previous.get('qb_status','Unknown')
        issues.append('retained_absence_evidence')
    context['qb_review_required']=bool(context['qb_review_required'] or retained or missing or conflict or invalid_override)
    schedule_disagreement=bool(confirmed and pd.notna(pid) and str(assumed_id)!=str(pid))
    if schedule_disagreement:issues.append('schedule_differs_from_confirmation')
    source='official_announcement' if selected.get('source_kind')=='official_announcement' else 'manual_confirmation' if confirmed else 'manual_override_unverified' if selected else 'nflverse_schedule'
    context.update(assumed_qb_id=None if pd.isna(assumed_id) else str(assumed_id),
                   qb_evidence_state='conflict' if conflict else 'missing_identity' if missing else 'confirmed' if confirmed else 'unconfirmed',
                   assumption_source=source,assumption_source_url=selected.get('source_url',SCHEDULE),
                   assumption_checked_at_utc=checked.isoformat(),
                   starter_verified_at_utc=selected.get('verified_at_utc') if confirmed else None,
                   schedule_qb_name=None if pd.isna(name) else name,
                   schedule_qb_id=None if pd.isna(pid) else str(pid),qb_evidence_issues=issues)
    if selected.get('source_url'):context['starter_source_url']=selected['source_url']
    if retained:context['prior_absence_evidence']=previous.get('prior_absence_evidence') or {
        key:previous.get(key) for key in ['assumed_qb','qb_status','assumption_checked_at_utc','players']}
    return context,selected

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
    manual=json.loads(Path(a.overrides).read_text()) if Path(a.overrides).exists() else {};effective=dict(manual);player_map=None;article_cache={}
    for r in future[future.week.eq(week)].to_dict('records'):
        checked=pd.Timestamp.now(tz='UTC')
        if checked>=r['kickoff_utc']:continue
        sides={};entry_over=dict(manual.get(r['game_id'],{}))
        for side,other in [('home','away'),('away','home')]:
            team,opponent=r[side+'_team'],r[other+'_team'];override=entry_over.get(side,{})
            announcements=[]
            for item in news:
                try:
                    if item['url'] not in article_cache:
                        article,receipt=get(item['url']);receipts.append(receipt)
                        soup=BeautifulSoup(article,'html.parser');title=soup.find('h1')
                        date=soup.find('meta',attrs={'property':'article:published_time'})
                        if date is None:
                            script=' '.join(s.get_text() for s in soup.find_all('script',type='application/ld+json'));match=re.search(r'"datePublished"\s*:\s*"([^"]+)"',script)
                            published=pd.to_datetime(match[1],utc=True,errors='coerce') if match else pd.NaT
                        else:published=pd.to_datetime(date.get('content'),utc=True,errors='coerce')
                        article_cache[item['url']]=(title.get_text(' ',strip=True) if title else '',published)
                    title,published=article_cache[item['url']]
                    if pd.isna(published) or not checked-pd.Timedelta(days=7)<=published<=checked:continue
                    if player_map is None:
                        raw,receipt=get(PLAYERS);receipts.append(receipt);player_map=pd.read_csv(io.BytesIO(raw),low_memory=False)
                    resolved=resolve_qb(title,team,opponent,player_map)
                    if resolved:
                        observed=pd.Timestamp.now(tz='UTC')
                        resolved.update(status_note=resolved['qb_name']+' confirmed to start by NFL report',source_url=item['url'],verified_at_utc=observed.isoformat(),source_published_at_utc=published.isoformat(),source_kind='official_announcement')
                        announcements.append(resolved)
                except (requests.RequestException,ValueError,KeyError) as error:
                    errors.append(str(error));article_cache.setdefault(item['url'],('',pd.NaT))
            previous=games.get(r['game_id'],{})
            if (previous.get('home_team'),previous.get('away_team'))!=(r['home_team'],r['away_team']):previous={}
            context,selected=starter_context(team,opponent,r.get(side+'_qb_name'),r.get(side+'_qb_id'),override,
                                             announcements,injuries,inactive,previous.get(side,{}),pd.Timestamp.now(tz='UTC'),r['kickoff_utc'])
            if selected:entry_over[side]=selected
            elif 'invalid_override_time' in context['qb_evidence_issues']:entry_over.pop(side,None)
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
