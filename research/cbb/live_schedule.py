"""Supplement the delayed archive with current ESPN schedule fields only.

Historical feature construction and frozen model weights are untouched.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from urllib.request import Request, urlopen

import pandas as pd

URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={day}&groups=50&limit=1000'


def normalize(payload):
    rows = []
    for event in payload.get('events', []):
        season = event.get('season', {})
        competitions = event.get('competitions', [])
        if len(competitions) != 1:
            continue
        c = competitions[0]
        sides = {x.get('homeAway'): x for x in c.get('competitors', [])}
        if set(sides) != {'home', 'away'}:
            continue
        status = c.get('status', {}).get('type', {})
        row = dict(game_id=int(event['id']), season=season.get('year'),
                   season_type=season.get('type'), date=c.get('date'),
                   time_valid=c.get('timeValid', False), neutral_site=c.get('neutralSite'),
                   status_type_name=status.get('name'),
                   status_type_completed=status.get('completed', False))
        for side, competitor in sides.items():
            team = competitor.get('team', {})
            row.update({side+'_id':int(team['id']), side+'_display_name':team['displayName'],
                        side+'_conference_id':team.get('conferenceId'),
                        side+'_score':pd.to_numeric(competitor.get('score'), errors='coerce')})
        rows.append(row)
    return pd.DataFrame(rows)


def merge_schedule(archive, live):
    """Prefer current schedule facts only when the event identity matches."""
    if live.empty:
        return archive.copy()
    if archive.game_id.duplicated().any() or live.game_id.duplicated().any():
        raise ValueError('Duplicate schedule IDs')
    original = archive.set_index('game_id')
    records = live.to_dict('records')
    for row in records:
        if row['game_id'] in original.index:
            old = original.loc[row['game_id']]
            # Providers can reverse designated sides at a neutral venue.
            # Retain the archived orientation, including any saved forecast.
            reversed_sides = (old['home_id'] == row['away_id'] and old['away_id'] == row['home_id'])
            if reversed_sides and old.get('neutral_site') == True and row.get('neutral_site') == True:
                for suffix in ['id','display_name','conference_id','score']:
                    row['home_'+suffix], row['away_'+suffix] = row['away_'+suffix], row['home_'+suffix]
            if any(str(int(old[k])) != str(int(row[k])) for k in ['home_id', 'away_id', 'season']):
                raise ValueError(f"Live/archive schedule identity mismatch: {row['game_id']} archive={old[['home_id','away_id','season']].to_dict()} live={ {k:row[k] for k in ['home_id','away_id','season']} }")
    # Merge field by field so source eligibility flags are preserved.
    combined = {row['game_id']:row for row in archive.to_dict('records')}
    for row in records:
        gid = row['game_id']
        combined.setdefault(gid, {})
        for key, value in row.items():
            if value is not None and not pd.isna(value):
                combined[gid][key] = value
    return pd.DataFrame(combined.values())


def supplement(archive, source, now, pending=(), fetcher=None):
    # Daily endpoints cover the next week plus every pending forecast's day.
    # Include the previous UTC date because ESPN groups games by US date.
    days = set(pd.date_range(now.floor('D')-pd.Timedelta(days=1),
                             now.floor('D')+pd.Timedelta(days=7), freq='D'))
    for row in pending:
        if row.get('status') != 'settled':
            day = pd.Timestamp(row['start_time_utc']).floor('D')
            days.update([day-pd.Timedelta(days=1), day])

    def read(day):
        url = URL.format(day=day.strftime('%Y%m%d'))
        if fetcher is None:
            with urlopen(Request(url, headers={'User-Agent':'BP-Sports-CBB-Schedule/1.0'}), timeout=30) as response:
                raw = response.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:
                raise ValueError('Live schedule too large')
            payload = json.loads(raw)
        else:
            payload = fetcher(url)
        if len(payload.get('events', [])) >= 1000:
            raise ValueError('Live schedule may be truncated')
        frame = normalize(payload)
        receipt = dict(url=url, sha256=hashlib.sha256(frame.to_json(orient='records').encode()).hexdigest(),
                       games=len(frame))
        return frame, receipt

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(read, sorted(days)))
    frames = [f for f, _ in results if len(f)]
    live = pd.concat(frames, ignore_index=True).drop_duplicates('game_id', keep='last') if frames else pd.DataFrame()
    conflicts = []
    if len(live):
        for gid in set(archive.game_id) & set(live.game_id):
            try:
                merge_schedule(archive[archive.game_id.eq(gid)], live[live.game_id.eq(gid)])
            except ValueError as error:
                conflicts.append(dict(game_id=int(gid), reason=str(error)))
        blocked = {r['game_id'] for r in conflicts}
        # Quarantine contradictory identities rather than guessing a team.
        archive = archive[~archive.game_id.isin(blocked)]
        live = live[~live.game_id.isin(blocked)]
    merged = merge_schedule(archive, live)
    receipt = dict(source, archive_sha256=source['sha256'], live_schedule_sources=[r for _, r in results],
                   identity_conflicts=conflicts)
    receipt['sha256'] = hashlib.sha256(merged.to_json(orient='records').encode()).hexdigest()
    return merged, receipt
