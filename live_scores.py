"""Read-only live score overlay. No forecast, ledger, model or grading writes."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from urllib.request import Request, urlopen

import pandas as pd

from game_status import espn_game, matches
from preview_data import stamp

LEAGUES = {'NFL':'football/nfl', 'CFB':'football/college-football',
           'NHL':'hockey/nhl', 'NBA':'basketball/nba',
           'CBB':'basketball/mens-college-basketball'}


def read_json(url):
    with urlopen(Request(url, headers={'User-Agent':'BP-Sports-Live-Scores/1.0',
                                      'Cache-Control':'no-cache'}), timeout=8) as response:
        raw = response.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:
        raise ValueError('Score response too large')
    return json.loads(raw)


def merge_games(saved, fresh):
    """Map provider IDs to existing NFL/NHL keys using teams and game date."""
    result = copy.deepcopy(saved)
    for g in fresh:
        keys = [g['sport']+':'+g['game_id']]
        if g['sport'] in ('NFL', 'NHL'):
            for key, old in saved.items():
                if old.get('sport')!=g['sport']:
                    continue
                if not matches(g, g['sport'], old.get('home_team'), old.get('away_team')):
                    continue
                old_start, new_start = stamp(old.get('start_time_utc')), stamp(g['start_time_utc'])
                if pd.notna(old_start) and old_start.tz_convert('America/New_York').date()==new_start.tz_convert('America/New_York').date():
                    keys.append(key)
        for key in keys:
            old = result.get(key)
            if old and old.get('state')=='final' and g['state']!='final':
                continue
            result[key] = {**g, 'provider_game_id':g['game_id'], 'game_id':key.split(':',1)[1]}
    return result


def collect_scores(archive, now=None, fetcher=None):
    fetcher = read_json if fetcher is None else fetcher
    now = stamp(now) if now is not None else pd.Timestamp.now(tz='UTC')
    checked = now.isoformat()
    day = now.tz_convert('America/New_York').normalize()
    # The previous US date retains late games after midnight. Future cards use
    # their saved scheduled tipoff until they enter this live score window.
    days = [(day-pd.Timedelta(days=1)).strftime('%Y%m%d'), day.strftime('%Y%m%d')]
    queries = [(sport, date) for sport in LEAGUES for date in days]

    def fetch(item):
        sport, date = item
        url = f'https://site.api.espn.com/apis/site/v2/sports/{LEAGUES[sport]}/scoreboard?dates={date}&limit=1000'
        url += '&groups=80' if sport=='CFB' else '&groups=50' if sport=='CBB' else ''
        try:
            payload = fetcher(url)
            if not isinstance(payload.get('events'), list):
                raise ValueError('Invalid scoreboard response')
            if len(payload['events'])>=1000:
                raise ValueError('Scoreboard may be truncated')
            rows = [g for e in payload['events'] if (g:=espn_game(sport,e,checked))]
            return rows, dict(sport=sport,date=date,checked_at_utc=checked,status='success',games=len(rows)), None
        except Exception as error:
            return [], dict(sport=sport,date=date,status='unavailable'), f'{sport} {date}: {type(error).__name__}'

    with ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(fetch,queries))
    fresh = [g for rows,_,_ in batches for g in rows]
    errors = [error for _,_,error in batches if error]
    merged = merge_games(archive.get('games',{}),fresh)
    healthy_sports = {check['sport'] for _,check,_ in batches if check['status']=='success'}
    # College scoreboards sometimes omit unranked games even with limit=1000.
    # Resolve active saved IDs directly; never turn missing data into a score.
    missing = []
    for key, old in archive.get('games',{}).items():
        sport = old.get('sport'); start = stamp(old.get('start_time_utc'))
        if sport not in ('CFB','NBA','CBB') or sport not in healthy_sports or old.get('state')=='final':
            continue
        if pd.notna(start) and now-pd.Timedelta(hours=12)<=start<=now+pd.Timedelta(minutes=15) and merged[key].get('checked_at_utc')!=checked:
            missing.append((key,old))
    def detail(item):
        key, old = item; sport = old['sport']; gid = old['game_id']
        url = f'https://site.api.espn.com/apis/site/v2/sports/{LEAGUES[sport]}/summary?event={gid}'
        try:
            header = fetcher(url).get('header',{})
            if str(header.get('id'))!=str(gid):raise ValueError('Score event identity mismatch')
            row = espn_game(sport,header,checked)
            if not matches(row,sport,old['home_team'],old['away_team']):raise ValueError('Score team identity mismatch')
            return row,None
        except Exception as error:return None,f'{key} direct score: {type(error).__name__}'
    with ThreadPoolExecutor(max_workers=6) as pool:
        for row,error in pool.map(detail,missing):
            if row:fresh.append(row)
            if error:errors.append(error)
    any_success = any(check['status']=='success' for _,check,_ in batches)
    return {**archive, 'games':merge_games(archive.get('games',{}),fresh),
            'updated_at_utc':checked if any_success else archive.get('updated_at_utc'),
            'archive_updated_at_utc':archive.get('updated_at_utc'),
            'mode':'direct_live' if not errors else 'partial_live' if any_success else 'saved_fallback',
            'source_checks':[check for _,check,_ in batches], 'errors':errors,
            'purpose':'Read-only live scores; saved probabilities and grading unchanged'}
