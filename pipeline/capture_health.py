"""Read-only capture health gate, run after preserving any valid outputs."""
import argparse
import json
from pathlib import Path


def failure_reason(sport, dashboard):
    expected={'cbb':'research_preview','nba':'enabled'}
    if sport in expected and dashboard.get('feed_status')!=expected[sport]:
        return 'Forecast feed unavailable'
    for key in ('capture_blocked_reason','prediction_blocked_reason'):
        if dashboard.get(key):return str(dashboard[key])
    if dashboard.get('missing_upcoming_game_ids'):
        return 'Missing upcoming forecasts: '+', '.join(map(str,dashboard['missing_upcoming_game_ids']))
    return None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('sport',choices=['nba','cbb'])
    parser.add_argument('dashboard',type=Path);args=parser.parse_args()
    reason=failure_reason(args.sport,json.loads(args.dashboard.read_text()))
    if reason:raise SystemExit('::error::Forecast capture blocked: '+reason)
    print(args.sport+': forecast capture ready')


if __name__=='__main__':main()
