"""Select the official NBA forecast without changing either frozen ledger."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

BASE_BRANCH = 'nba-v1-research'
BASE_PATH = 'data/nba/prospective/dashboard.json'
INJURY_BRANCH = 'nba-v2-challenger'
INJURY_PATH = 'data/nba/availability-shadow/primary.json'
BASE_HASH = 'c57d804ab9062542e9e456a9585327bbb677732e5ad55b0186f91ddbdf5e079f'
INJURY_HASH = 'b161f4327eb6524d99311169c1d150e08724c82901d9a7713b75511b76824451'
CUTOVER = datetime(2026, 11, 6, 18, tzinfo=timezone.utc)
SAVED_BEFORE = datetime(2026, 11, 4, 21, tzinfo=timezone.utc)


def stamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('NBA timestamps must include a time zone')
    return parsed.astimezone(timezone.utc)


def publish(directory, now):
    """Append compact, verified injury picks while there is time to publish them."""
    path = directory / 'primary.json'
    existing = json.loads(path.read_text()) if path.exists() else {}
    if path.exists() and existing.get('bundle_sha256') != INJURY_HASH:
        raise ValueError('NBA injury feed identity mismatch')
    picks = existing.get('picks', {})
    with (directory / 'predictions.jsonl').open() as ledger:
        for line in ledger:
            row = json.loads(line)
            game = row['game_id']
            if game in picks or row['fallback'] is not False:
                continue
            start = stamp(row['start_time_utc'])
            created = stamp(row['created_at_utc'])
            if start < CUTOVER or not SAVED_BEFORE <= created <= now < start:
                continue
            if (row['shadow_sha256'] != INJURY_HASH or row['v1_bundle_sha256'] != BASE_HASH
                    or row['season'] != 2027 or row['season_type'] != 2
                    or row['injury_report']['both_known'] is not True
                    or row['injury_report']['parse_issues']
                    or not 0 <= row['candidate_probability'] <= 1):
                raise ValueError('Invalid NBA injury forecast')
            picks[game] = {key: row[key] for key in (
                'home_id', 'away_id', 'created_at_utc', 'start_time_utc', 'candidate_probability',
            )}
    path.write_text(json.dumps(dict(bundle_sha256=INJURY_HASH, picks=picks), allow_nan=False) + '\n')


def merge(base, injury):
    """Use the original fast-finals feed for settlement of the selected pick."""
    if base.get('feed_status') != 'enabled':
        return base
    if base.get('bundle_sha256') != BASE_HASH:
        raise ValueError('NBA team model identity mismatch')
    picks = injury['picks'] if injury.get('bundle_sha256') == INJURY_HASH else None
    selected = []
    for row in base['predictions']:
        if stamp(row['start_time_utc']) < CUTOVER or stamp(row['created_at_utc']) < SAVED_BEFORE:
            selected.append({**row, 'nba_pick_source': 'legacy'})
            continue
        if picks is None:
            raise ValueError('NBA injury feed unavailable or invalid')
        pick = picks.get(row['game_id'])
        if pick and (
            pick['home_id'] == row['home_id'] and pick['away_id'] == row['away_id']
            and stamp(pick['start_time_utc']) == stamp(row['start_time_utc'])
            and stamp(row['created_at_utc']) <= stamp(pick['created_at_utc']) < stamp(row['start_time_utc'])
            and stamp(pick['created_at_utc']) < stamp(row.get('actual_start_time_utc') or row['start_time_utc'])
            and 0 <= pick['candidate_probability'] <= 1
        ):
            selected.append(dict(row, nba_pick_source='injury', home_win_prob=pick['candidate_probability'],
                                 created_at_utc=pick['created_at_utc']))
        else:
            selected.append({**row, 'nba_pick_source': 'team'})
    return dict(base, predictions=selected)


if __name__ == '__main__':
    publish(Path(sys.argv[1]), datetime.now(timezone.utc))
