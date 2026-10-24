"""Validate live ESPN final team boxes in the frozen loader's input schema."""
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

FIELDS = ['field_goals_made','field_goals_attempted','three_point_field_goals_made',
          'free_throws_made','free_throws_attempted','offensive_rebounds',
          'defensive_rebounds','turnovers','team_score']
COLUMNS = ['game_id','team_id','opponent_team_id','team_home_away'] + FIELDS
SUMMARY = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='

def number(value):
    if isinstance(value, bool): raise ValueError('Boolean box statistic')
    n = float(value)
    if not math.isfinite(n) or n < 0 or not n.is_integer():
        raise ValueError('Invalid box statistic')
    return int(n)

def validate_pair(rows, game):
    if len(rows) != 2: raise ValueError('Missing team box pair')
    sides = {r['team_home_away']: r for r in rows}
    if set(sides) != {'home','away'}: raise ValueError('Invalid box sides')
    for side, other in [('home','away'),('away','home')]:
        r = sides[side]
        if (number(r['game_id']) != number(game['game_id']) or
            number(r['team_id']) != number(game[side+'_id']) or
            number(r['opponent_team_id']) != number(game[other+'_id'])):
            raise ValueError('Team box identity mismatch')
        values = {k:number(r[k]) for k in FIELDS}
        if values['team_score'] != number(game[side+'_score']):
            raise ValueError('Team box score mismatch')
        if (values['field_goals_attempted'] <= 0 or
            values['field_goals_made'] > values['field_goals_attempted'] or
            values['three_point_field_goals_made'] > values['field_goals_made'] or
            values['free_throws_made'] > values['free_throws_attempted'] or
            2*values['field_goals_made'] + values['three_point_field_goals_made'] + values['free_throws_made'] != values['team_score']):
            raise ValueError('Team box points do not reconcile')
    if number(game['home_score']) == number(game['away_score']):
        raise ValueError('Tied completed game')
    possessions = sum(number(r['field_goals_attempted']) + .44*number(r['free_throws_attempted']) - number(r['offensive_rebounds']) + number(r['turnovers']) for r in rows)/2
    if possessions <= 0: raise ValueError('Invalid possessions')
    return [{k:(r[k] if k=='team_home_away' else number(r[k])) for k in COLUMNS} for r in rows]

def summary_pair(payload, game):
    header = payload['header']; competition = header['competitions'][0]
    if (number(header['id']) != number(game['game_id']) or
        number(competition['id']) != number(game['game_id']) or
        number(header['season']['year']) != 2027 or number(header['season']['type']) != 2):
        raise ValueError('Wrong summary game or season')
    status = competition['status']['type']
    if status.get('completed') is not True or status.get('state') != 'post':
        raise ValueError('Team boxes require a confirmed final')
    if pd.Timestamp(competition['date']) != pd.Timestamp(game['date']):
        raise ValueError('Summary start time mismatch')
    if pd.Timestamp(competition['date']) >= pd.Timestamp.now(tz='UTC'):
        raise ValueError('Future final')
    competitors = {t['homeAway']:t for t in competition['competitors']}
    if len(competition['competitors']) != 2 or set(competitors) != {'home','away'}:
        raise ValueError('Invalid summary sides')
    for side in ('home','away'):
        t = competitors[side]
        if number(t['team']['id']) != number(game[side+'_id']) or number(t['score']) != number(game[side+'_score']):
            raise ValueError('Summary competitor mismatch')
    rows = []
    for team in payload['boxscore']['teams']:
        side = team['homeAway']
        if side not in competitors: raise ValueError('Invalid box side')
        other = 'away' if side=='home' else 'home'
        stats = {s['name']:s['displayValue'] for s in team['statistics']}
        def pair(name):
            values = stats[name].split('-')
            if len(values) != 2: raise ValueError('Invalid shooting pair')
            made, attempted = map(number, values)
            if made > attempted: raise ValueError('Invalid shooting attempts')
            return made, attempted
        fg, fga = pair('fieldGoalsMade-fieldGoalsAttempted')
        three, three_attempts = pair('threePointFieldGoalsMade-threePointFieldGoalsAttempted')
        ft, fta = pair('freeThrowsMade-freeThrowsAttempted')
        if three_attempts > fga: raise ValueError('Invalid three-point attempts')
        rows.append(dict(game_id=number(header['id']),team_id=number(team['team']['id']),
            opponent_team_id=number(game[other+'_id']),team_home_away=side,
            field_goals_made=fg,field_goals_attempted=fga,three_point_field_goals_made=three,
            free_throws_made=ft,free_throws_attempted=fta,
            offensive_rebounds=number(stats['offensiveRebounds']),
            defensive_rebounds=number(stats['defensiveRebounds']),
            turnovers=number(stats['turnovers']),team_score=number(competitors[side]['score'])))
    return validate_pair(rows, game)

def complete_boxes(schedule, archive_bytes, fetch, cache_path=None):
    """Keep validated archive rows; fill missing/invalid finals from source summaries."""
    completed = schedule[schedule.status_type_state.eq('post') & schedule.status_type_completed.map(lambda x:str(x).lower() in ('true','1','1.0'))]
    if completed.empty: return archive_bytes
    archive = pd.read_parquet(io.BytesIO(archive_bytes)) if archive_bytes is not None else pd.DataFrame(columns=COLUMNS)
    groups = {str(number(gid)):group.to_dict('records') for gid,group in archive.groupby('game_id')}
    cached = {}
    path = Path(cache_path) if cache_path is not None else None
    if path is not None and path.exists():
        for line in path.read_text().splitlines():
            if line:
                receipt = json.loads(line); cached[str(receipt['game_id'])] = receipt
    rows = []
    for game in completed.to_dict('records'):
        gid = str(number(game['game_id'])); pair = None
        for candidate in (groups.get(gid,[]),cached.get(gid,{}).get('rows',[])):
            try: pair = validate_pair(candidate,game); break
            except (ValueError,KeyError,TypeError): pass
        if pair is None:
            url = SUMMARY+gid; raw = fetch(url)
            try: pair = summary_pair(json.loads(raw),game)
            except (ValueError,KeyError,TypeError,IndexError) as error:
                raise ValueError(f'Unverified final team boxes for {gid}: {error}') from error
            if path is not None:
                import hashlib
                path.parent.mkdir(parents=True,exist_ok=True)
                receipt = dict(game_id=gid,fetched_at_utc=datetime.now(timezone.utc).isoformat(),
                    source_url=url,source_sha256=hashlib.sha256(raw).hexdigest(),rows=pair)
                with path.open('a') as f: f.write(json.dumps(receipt,sort_keys=True,allow_nan=False)+'\n')
        rows.extend(pair)
    output = io.BytesIO()
    pd.DataFrame(rows,columns=COLUMNS).to_parquet(output,index=False)
    return output.getvalue()
