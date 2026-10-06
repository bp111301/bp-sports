"""Frozen NBA V1 regular-season collection. Forecasts/results are separate append-only logs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'final'))
import hashlib
import io
import json
import tempfile
from datetime import datetime, timezone, timedelta
import joblib
import numpy as np
import pandas as pd
import requests
import baseline
from baseline import FEATURES, build_features, load_games, metrics, truth
from evaluate import verify_frozen

ROOT = baseline.ROOT
OUT = ROOT / 'data/nba/prospective'
SEASON = 2027
BASE = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download'
API = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def regular(r):
    note = str(r.get('notes_headline', '')).lower()
    cup_final = ('cup' in note or 'tournament' in note) and ('championship' in note or ('final' in note and 'semifinal' not in note and 'quarterfinal' not in note))
    return int(r['season']) == SEASON and int(r['season_type']) == 2 and 1 <= int(r['home_id']) <= 30 and 1 <= int(r['away_id']) <= 30 and not cup_final

def read_log(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []

def append(path, rows):
    if rows:
        with path.open('a') as f:
            for row in rows:
                f.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')

def validate(predictions, results, model_sha):
    ids = set()
    for p in predictions:
        assert p['game_id'] not in ids, 'Duplicate forecast'
        ids.add(p['game_id'])
        assert p['bundle_sha256'] == model_sha and p['season'] == SEASON and p['season_type'] == 2
        assert pd.Timestamp(p['created_at_utc']) < pd.Timestamp(p['start_time_utc'])
        assert p['history_cutoff'] < pd.Timestamp(p['start_time_utc']).tz_convert('America/New_York').date().isoformat()
        assert np.isfinite(p['home_win_prob']) and 0 <= p['home_win_prob'] <= 1
    settled = set()
    for r in results:
        assert r['game_id'] in ids and r['game_id'] not in settled
        settled.add(r['game_id'])
        p = next(p for p in predictions if p['game_id'] == r['game_id'])
        assert pd.Timestamp(r['settled_at_utc']) > pd.Timestamp(p['start_time_utc'])
        assert r['home_score'] != r['away_score'] and min(r['home_score'], r['away_score']) >= 0
        assert r['actual_home_win'] == int(r['home_score'] > r['away_score'])

def scoreboard_rows(data):
    rows = []
    for e in data.get('events', []):
        season = e.get('season', {})
        if season.get('year') != SEASON or season.get('type') != 2:
            continue
        c = e['competitions'][0]
        teams = {t['homeAway']: t for t in c['competitors']}
        h, a = teams['home'], teams['away']
        status = c['status']['type']
        r = dict(game_id=int(e['id']), season=SEASON, season_type=2, date=c['date'],
                 home_id=int(h['team']['id']), away_id=int(a['team']['id']),
                 home_abbreviation=h['team']['abbreviation'], away_abbreviation=a['team']['abbreviation'],
                 home_score=h.get('score', 0), away_score=a.get('score', 0),
                 neutral_site=c.get('neutralSite', False), notes_headline=' '.join(n.get('headline','') for n in c.get('notes', [])),
                 status_type_state=status['state'], status_type_completed=status['completed'], status_type_name=status['name'])
        if regular(r):
            rows.append(r)
    return rows

def fetch_sources(now, predictions, results):
    receipts = []
    def get(url, optional=False):
        r = requests.get(url, timeout=90)
        if optional and r.status_code == 404:
            receipts.append(dict(url=url, status=404)); return None
        r.raise_for_status()
        receipts.append(dict(url=url, status=r.status_code, sha256=digest(r.content)))
        return r.content
    schedule_bytes = get(f'{BASE}/espn_nba_schedules/nba_schedule_{SEASON}.parquet')
    schedule = pd.read_parquet(io.BytesIO(schedule_bytes))
    assert set(pd.to_numeric(schedule.season).unique()) == {SEASON}
    assert not schedule.game_id.duplicated().any()
    box_bytes = get(f'{BASE}/espn_nba_team_boxscores/team_box_{SEASON}.parquet', optional=True)
    settled = {r['game_id'] for r in results}
    day = now.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date()
    # Cross-check recent states and all pending dates; no forecast uses today's results.
    days = {day-timedelta(days=1), day, day+timedelta(days=1)}
    days.update(pd.Timestamp(p['start_time_utc']).tz_convert('America/New_York').date() for p in predictions if p['game_id'] not in settled and pd.Timestamp(p['start_time_utc']) <= now)
    indexed = {str(int(r['game_id'])): r for r in schedule.to_dict('records')}
    for d in sorted(days):
        data = json.loads(get(f'{API}?dates={d:%Y%m%d}'))
        for r in scoreboard_rows(data):
            gid = str(r['game_id'])
            old = indexed.get(gid, {})
            if old:
                assert int(old['home_id']) == r['home_id'] and int(old['away_id']) == r['away_id']
            indexed[gid] = {**old, **r}
    schedule = pd.DataFrame(indexed.values())
    return schedule, box_bytes, receipts

def current_history(schedule, box_bytes):
    completed = [r for r in schedule.to_dict('records') if regular(r) and truth(r['status_type_completed']) and r['status_type_state'] == 'post']
    if not completed:
        return pd.DataFrame()
    if box_bytes is None:
        raise ValueError('Completed regular-season box scores are not available yet')
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp); source = root/'data/nba/source'; source.mkdir(parents=True)
        schedule.to_parquet(source/f'schedule_{SEASON}.parquet', index=False)
        (source/f'box_{SEASON}.parquet').write_bytes(box_bytes)
        original = baseline.ROOT
        try:
            baseline.ROOT = root
            games, audit = load_games([SEASON])
        finally:
            baseline.ROOT = original
    if len(games) != len(completed):
        raise ValueError(f'Waiting for complete validated team boxes: {len(games)}/{len(completed)}')
    return games

def forecast_features(history, r):
    start = pd.Timestamp(r['date'])
    day = start.tz_convert('America/New_York').date().isoformat()
    prior = history[history.date < day].copy()
    # The sentinel's dummy outcome is never read for its own forecast. It is the last date.
    future = dict(game_id=str(int(r['game_id'])), season=SEASON, date=day, start_time=start.isoformat(),
                  home_id=str(int(r['home_id'])), away_id=str(int(r['away_id'])),
                  home_team=r['home_abbreviation'], away_team=r['away_abbreviation'], neutral=truth(r['neutral_site']),
                  y=0, home_score=0, away_score=0, home_stats=[0.]*8, away_stats=[0.]*8)
    f = build_features(pd.concat([prior, pd.DataFrame([future])], ignore_index=True))
    return f[f.game_id == future['game_id']].iloc[-1], prior.date.max()

def settle(predictions, results, schedule, now):
    settled = {r['game_id'] for r in results}
    indexed = {str(int(r['game_id'])): r for r in schedule.to_dict('records')}
    new = []
    for p in predictions:
        r = indexed.get(p['game_id'])
        if p['game_id'] in settled or not r or not regular(r): continue
        assert str(int(r['home_id'])) == p['home_id'] and str(int(r['away_id'])) == p['away_id']
        actual_start = pd.Timestamp(r['date'])
        if not (truth(r['status_type_completed']) and r['status_type_state'] == 'post' and actual_start < now): continue
        # A changed kickoff that invalidates original pregame timing never earns a result.
        if pd.Timestamp(p['created_at_utc']) >= actual_start: continue
        h, a = float(r['home_score']), float(r['away_score'])
        if not (np.isfinite(h) and np.isfinite(a) and min(h,a) >= 0 and h != a): continue
        new.append(dict(game_id=p['game_id'], home_score=h, away_score=a, actual_home_win=int(h>a),
                        actual_start_time_utc=actual_start.isoformat(), settled_at_utc=now.isoformat(), source_state='post_completed'))
    return new

def main():
    manifest = verify_frozen()
    evaluation = json.loads((ROOT/'research/nba/results/excluded_season_evaluation.json').read_text())
    assert evaluation['gate_passed'] and evaluation['bundle_sha256'] == manifest['bundle_sha256']
    bundle = joblib.load(ROOT/'model/nba/v1/frozen_bundle.joblib')
    assert bundle['selected'] == manifest['selected'] == 'baseline_control' and bundle['features'] == FEATURES
    OUT.mkdir(parents=True, exist_ok=True)
    predictions = read_log(OUT/'predictions.jsonl'); results = read_log(OUT/'results.jsonl')
    validate(predictions, results, manifest['bundle_sha256'])
    fetched_at = datetime.now(timezone.utc)
    schedule, box_bytes, receipts = fetch_sources(fetched_at, predictions, results)
    now = datetime.now(timezone.utc)
    new_results = settle(predictions, results, schedule, now)
    results += new_results
    blocked = None; new_predictions = []
    try:
        history, _ = load_games(range(2016, 2027))
        current = current_history(schedule, box_bytes)
        if not current.empty: history = pd.concat([history, current], ignore_index=True)
        known = {p['game_id'] for p in predictions}
        for r in sorted(schedule.to_dict('records'), key=lambda r: str(r['date'])):
            gid = str(int(r['game_id'])); start = pd.Timestamp(r['date'])
            if gid in known or not regular(r) or r['status_type_state'] != 'pre' or not (now < start <= now+timedelta(hours=36)): continue
            f, cutoff = forecast_features(history, r)
            probability = float(bundle['models']['linear'].predict_proba(pd.DataFrame([f])[FEATURES])[0,1])
            captured = datetime.now(timezone.utc)
            if captured >= start: continue
            new_predictions.append(dict(game_id=gid, season=SEASON, season_type=2, home_team=r['home_abbreviation'], away_team=r['away_abbreviation'],
                home_id=str(int(r['home_id'])), away_id=str(int(r['away_id'])), home_win_prob=probability,
                start_time_utc=start.isoformat(), created_at_utc=captured.isoformat(), history_cutoff=cutoff,
                bundle_sha256=manifest['bundle_sha256'], features={k:float(f[k]) for k in FEATURES},
                source_receipt_sha256=digest(json.dumps(receipts,sort_keys=True).encode())))
    except ValueError as e:
        blocked = str(e)
    predictions += new_predictions
    validate(predictions, results, manifest['bundle_sha256'])
    append(OUT/'predictions.jsonl', new_predictions); append(OUT/'results.jsonl', new_results)
    append(OUT/'source_receipts.jsonl', [dict(fetched_at_utc=fetched_at.isoformat(), sources=receipts)])
    by_id = {r['game_id']:r for r in results}
    dashboard_rows = [{**p, **by_id.get(p['game_id'],{}), 'status':'settled' if p['game_id'] in by_id else 'pending', 'actual_home_win':by_id.get(p['game_id'],{}).get('actual_home_win')} for p in predictions]
    record = metrics([r['actual_home_win'] for r in dashboard_rows if r['status']=='settled'], [r['home_win_prob'] for r in dashboard_rows if r['status']=='settled']) if results else dict(games=0,correct=0,accuracy=None,brier=None,log_loss=None)
    dashboard = dict(feed_status='enabled', updated_at_utc=datetime.now(timezone.utc).isoformat(), season=SEASON, regular_season_only=True,
        weights_frozen=True, bundle_sha256=manifest['bundle_sha256'], predictions=dashboard_rows, record=record,
        prediction_blocked_reason=blocked, forecast_rule='First pregame snapshot within 36 hours; earlier-date results only', grading='Hourly after source reports completed final')
    (OUT/'dashboard.json').write_text(json.dumps(dashboard, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(new_predictions=len(new_predictions), new_results=len(new_results), record=record, prediction_blocked_reason=blocked), indent=2))

if __name__ == '__main__': main()
