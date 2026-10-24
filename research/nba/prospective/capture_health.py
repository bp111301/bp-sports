"""Fail CI after saving the dashboard when NBA forecast capture is blocked."""
import json
import sys
from pathlib import Path

def failure_reason(dashboard):
    if dashboard.get('feed_status') != 'enabled': return 'NBA forecast feed is unavailable'
    if dashboard.get('prediction_blocked_reason'): return str(dashboard['prediction_blocked_reason'])
    missing = dashboard.get('missing_upcoming_game_ids', [])
    if missing: return 'Missing upcoming NBA forecasts: ' + ', '.join(map(str,missing))
    if dashboard.get('operational_status') != 'ready': return 'NBA forecast health was not verified'
    return None

def main():
    path = Path(sys.argv[1]) if len(sys.argv)>1 else Path('data/nba/prospective/dashboard.json')
    reason = failure_reason(json.loads(path.read_text()))
    if reason:
        print('::error::NBA capture blocked: '+reason)
        raise SystemExit(1)
    print('NBA forecast capture ready; all eligible upcoming games have saved forecasts.')

if __name__ == '__main__': main()
