from datetime import datetime
from unittest.mock import patch

from pipeline import nba_pregame_due


def game(game_id, start, state='pre', season_type=2):
    return {
        'id': game_id,
        'date': start,
        'status': {'type': {'state': state}},
        'season': {'type': season_type},
    }


def test_early_and_late_tipoffs_open_at_the_existing_report_cutoff():
    games = [
        game('early', '2026-11-12T00:00:00Z'),
        game('late', '2026-11-12T03:00:00Z'),
        game('live', '2026-11-12T00:30:00Z', state='in'),
        game('preseason', '2026-11-12T01:00:00Z', season_type=1),
    ]
    assert nba_pregame_due.open_windows(games, datetime.fromisoformat('2026-11-11T22:59:00Z')) == set()
    assert nba_pregame_due.open_windows(games, datetime.fromisoformat('2026-11-11T23:00:00Z')) == {'early', 'late'}
    assert nba_pregame_due.open_windows(games, datetime.fromisoformat('2026-11-12T00:00:00Z')) == {'late'}


def test_watchdog_skips_saved_pairs_and_requests_unsaved_games(capsys, monkeypatch):
    monkeypatch.setenv('GITHUB_REPOSITORY', 'bp111301/bp-sports')
    games = {'events': [game('saved', '2026-11-12T03:00:00Z'), game('due', '2026-11-12T03:00:00Z')]}
    dashboard = {'upcoming': [{'game_id': 'saved', 'status': 'already_saved'}]}
    with patch.object(nba_pregame_due, 'datetime', wraps=datetime) as clock, patch.object(
        nba_pregame_due, 'read_json', side_effect=[games, dashboard]
    ):
        clock.now.return_value = datetime.fromisoformat('2026-11-11T23:05:00Z')
        nba_pregame_due.main()
    assert capsys.readouterr().out == 'due\n'
