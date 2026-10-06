"""Download only preregistered development seasons; never fetch the holdout."""
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/nba/source'
BASE = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download'
SEASONS = list(range(2016, 2026))  # ending year; 2025-26 remains excluded

def fetch(item):
    season, kind = item
    tag, stem = ('espn_nba_team_boxscores', 'team_box') if kind == 'box' else ('espn_nba_schedules', 'nba_schedule')
    url = f'{BASE}/{tag}/{stem}_{season}.parquet'
    path = SOURCE / f'{kind}_{season}.parquet'
    if not path.exists():
        response = requests.get(url, timeout=90)
        response.raise_for_status()
        pd.read_parquet(io.BytesIO(response.content))  # reject non-data responses
        path.write_bytes(response.content)
    frame = pd.read_parquet(path)
    assert set(pd.to_numeric(frame.season).unique()) == {season}
    return dict(season=season, kind=kind, url=url, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), rows=len(frame))

def main():
    SOURCE.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(fetch, [(s,k) for s in SEASONS for k in ('box','schedule')]))
    manifest = dict(source='SportsDataverse hoopR ESPN NBA archive', retrieved_at=datetime.now(timezone.utc).isoformat(), excluded_season=2026, files=entries)
    (SOURCE/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Validated', len(entries), 'development source files; holdout not downloaded')

if __name__ == '__main__':
    main()
