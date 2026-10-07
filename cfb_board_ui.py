"""Presentation-only CFB dates and chronological game ordering."""
import pandas as pd
from game_center_ui import context


def dated_board(frame, feed):
    board = frame.copy(deep=True)
    saved = pd.to_datetime(board['kickoff_utc'], utc=True, errors='coerce')
    scheduled = pd.to_datetime(board.get('schedule_kickoff_utc', board['kickoff_utc']), utc=True, errors='coerce')
    board['_display_kickoff'] = scheduled.fillna(saved)
    for i, row in board.iterrows():
        verified = context('CFB', row['game_id'], row['home_team'], row['away_team'], feed=feed)
        if verified:
            kickoff = pd.to_datetime(verified.get('start_time_utc'), utc=True, errors='coerce')
            if pd.notna(kickoff):
                board.loc[i, '_display_kickoff'] = kickoff
    board['_game_date'] = board['_display_kickoff'].dt.tz_convert('America/Chicago').dt.strftime('%Y-%m-%d')
    return board


def date_choices(board, now=None):
    dates = sorted(board['_game_date'].dropna().unique().tolist())
    options = ['All dates', *dates]
    if board['_display_kickoff'].isna().any():
        options.append('Kickoff TBD')
    today = (pd.Timestamp.now(tz='UTC') if now is None else pd.to_datetime(now, utc=True)).tz_convert('America/Chicago').strftime('%Y-%m-%d')
    default = next((day for day in dates if day >= today), dates[-1] if dates else 'All dates')
    return options, default


def games_on_date(board, selected):
    shown = board if selected == 'All dates' else board[board['_display_kickoff'].isna()] if selected == 'Kickoff TBD' else board[board['_game_date'] == selected]
    return shown.sort_values(['_display_kickoff', 'away_team', 'home_team', 'game_id'], kind='stable', na_position='last').copy()


def date_label(value):
    return value if value in ('All dates', 'Kickoff TBD') else pd.Timestamp(value).strftime('%a, %b %-d, %Y') + ' · CT'
