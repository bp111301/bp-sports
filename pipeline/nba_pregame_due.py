"""Find NBA games whose pregame injury capture window is open."""
from datetime import datetime, timedelta, timezone
import json
import os
from urllib.error import URLError
from urllib.request import urlopen
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo('America/New_York')
SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'


def open_windows(events, now):
    due = set()
    for event in events:
        if event['season']['type'] != 2 or event['status']['type']['state'] != 'pre':
            continue
        start = datetime.fromisoformat(event['date']).astimezone(EASTERN)
        evening = start.replace(hour=18, minute=0, second=0, microsecond=0)
        # Match the injury collector's regular-season report cutoff.
        opens = min(start - timedelta(hours=1), evening)
        if opens <= now < start:
            due.add(str(event['id']))
    return due


def read_json(url):
    with urlopen(url, timeout=12) as response:
        return json.load(response)


def main():
    now = datetime.now(timezone.utc)
    day = now.astimezone(EASTERN).strftime('%Y%m%d')
    events = read_json(f'{SCOREBOARD}?dates={day}&limit=1000')['events']
    due = open_windows(events, now)
    if due:
        repo = os.environ['GITHUB_REPOSITORY']
        path = 'nba-v2-challenger/data/nba/availability-shadow/dashboard.json'
        try:
            dashboard = read_json(f'https://raw.githubusercontent.com/{repo}/{path}')
        except (URLError, ValueError):
            dashboard = {}
        saved = {str(game['game_id']) for game in dashboard.get('upcoming', [])
                 if game['status'] == 'already_saved'}
        due -= saved
    if due:
        print(','.join(sorted(due)))


if __name__ == '__main__':
    main()
