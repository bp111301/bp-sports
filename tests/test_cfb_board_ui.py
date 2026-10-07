import pandas as pd
from cfb_board_ui import dated_board, date_choices, games_on_date


def fixture():
    return pd.DataFrame([
        dict(game_id='late', home_team='Troy', away_team='Southern Mississippi', kickoff_utc='2026-10-08T01:00:00Z', confidence=.99),
        dict(game_id='early', home_team='Texas Tech', away_team='Houston', kickoff_utc='2026-10-07T23:00:00Z', confidence=.55),
        dict(game_id='next', home_team='Notre Dame', away_team='Stanford', kickoff_utc='2026-10-08T05:01:00Z', confidence=.8),
        dict(game_id='unknown', home_team='Alabama', away_team='Auburn', kickoff_utc=None, confidence=.9),
    ])


def test_central_dates_and_time_order_do_not_rank_by_confidence_or_mutate_forecasts():
    raw = fixture(); before = raw.copy(deep=True)
    board = dated_board(raw, {})
    assert list(games_on_date(board, '2026-10-07').game_id) == ['early', 'late']
    assert list(games_on_date(board, '2026-10-08').game_id) == ['next']
    assert list(games_on_date(board, 'All dates').game_id) == ['early', 'late', 'next', 'unknown']
    assert list(games_on_date(board, 'Kickoff TBD').game_id) == ['unknown']
    pd.testing.assert_frame_equal(raw, before)


def test_default_selects_today_then_next_available_date_and_keeps_results_accessible():
    board = dated_board(fixture(), {})
    options, chosen = date_choices(board, '2026-10-07T21:00:00Z')
    assert chosen == '2026-10-07' and options == ['All dates', '2026-10-07', '2026-10-08', 'Kickoff TBD']
    assert date_choices(board, '2026-10-06T21:00:00Z')[1] == '2026-10-07'
    assert date_choices(board, '2026-10-10T21:00:00Z')[1] == '2026-10-08'


def test_verified_schedule_updates_display_date_only_and_rejects_wrong_teams():
    raw = fixture(); before = raw.copy(deep=True)
    raw['schedule_kickoff_utc'] = ['2026-10-09T01:00:00Z', None, None, None]
    feed = {'games': {'CFB:late': {'sport':'CFB', 'state':'scheduled', 'home_team':'Troy', 'away_team':'Southern Mississippi', 'start_time_utc':'2026-10-10T01:00:00Z'}}}
    board = dated_board(raw, feed)
    assert board.loc[0, '_game_date'] == '2026-10-09'
    assert board.loc[0, 'kickoff_utc'] == before.loc[0, 'kickoff_utc']
    assert board.loc[0, 'confidence'] == before.loc[0, 'confidence']
    feed['games']['CFB:late']['home_team'] = 'Other Team'
    assert dated_board(raw, feed).loc[0, '_game_date'] == '2026-10-08'
