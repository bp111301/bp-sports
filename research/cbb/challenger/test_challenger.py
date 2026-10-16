import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import ADJUSTED, ROTATION, extra_features, player_games


def game(gid, day, season=2023, home='h', away='a', offense=110.):
    start = pd.Timestamp(day)
    return dict(game_id=gid, season=season, start=start, day=start.floor('D'),
                home_id=home, away_id=away,
                values={home: dict(off_eff=offense, def_eff=90.),
                        away: dict(off_eff=90., def_eff=offense)})


def test_current_future_and_previous_day_boxes_cannot_change_forecast():
    games = [game('old', '2022-01-01T12:00Z', 2022),
             game('1', '2023-01-01T23:59Z'), game('2', '2023-01-02T00:01Z'),
             game('3', '2023-01-04T12:00Z'), game('4', '2023-01-06T12:00Z')]
    players = {('old','h'): {'returner':200.}, ('old','a'):{'other':200.},
               ('1','h'):{'returner':200.}, ('2','h'):{'new':200.},
               ('3','h'):{'new':200.}, ('4','h'):{'new':200.}}
    original = extra_features(games, players)
    changed_players = copy.deepcopy(players)
    changed_players[('3','h')] = {'returner':200.}
    changed_players[('4','h')] = {'returner':200.}
    changed_games = copy.deepcopy(games)
    changed_games[3]['values']['h']['off_eff'] = 200.
    changed = extra_features(changed_games, changed_players)
    features = ADJUSTED + ROTATION
    np.testing.assert_allclose(original.iloc[:4][features], changed.iloc[:4][features])
    assert original.iloc[4].returning_share_diff != changed.iloc[4].returning_share_diff
    assert original.iloc[4].adjusted_off_diff != changed.iloc[4].adjusted_off_diff
    midnight = copy.deepcopy(players)
    midnight[('1','h')] = {'new':200.}
    np.testing.assert_allclose(original.iloc[2][features].to_numpy(float),
                               extra_features(games, midnight).iloc[2][features].to_numpy(float))


def test_unknown_opening_roster_is_not_inferred_from_later_appearances():
    games = [game('old','2022-01-01T12:00Z',2022), game('first','2023-01-01T12:00Z')]
    base = {('old','h'):{'returner':200.}, ('old','a'):{'other':200.}}
    first = extra_features(games, {**base, ('first','h'):{'returner':200.}})
    second = extra_features(games, {**base, ('first','h'):{'new':200.}})
    np.testing.assert_allclose(first[ROTATION], second[ROTATION])
    assert first.iloc[-1].rotation_known_diff == 0


def test_transfer_only_identified_after_embargoed_appearance():
    games = [game('old','2022-01-01T12:00Z',2022), game('first','2023-01-01T12:00Z'),
             game('next','2023-01-03T12:00Z')]
    players = {('old','a'):{'transfer':200.}, ('first','h'):{'transfer':200.}}
    frame = extra_features(games, players)
    assert frame.iloc[1].transfer_share_diff == 0
    assert frame.iloc[2].transfer_share_diff == 1


def test_same_day_opponent_adjustments_do_not_leak():
    games = [game('1','2023-01-01T12:00Z'),game('2','2023-01-01T23:00Z',away='b')]
    changed = copy.deepcopy(games)
    changed[0]['values']['h']['off_eff'] = 200.
    np.testing.assert_allclose(extra_features(games,{})[ADJUSTED], extra_features(changed,{})[ADJUSTED])


def test_reviewed_2026_season_is_rejected():
    with pytest.raises(ValueError, match='development seasons'):
        extra_features([game('holdout','2026-01-01T12:00Z',2026)], {})


def test_future_season_cannot_change_past_features():
    early = game('early','2023-01-01T12:00Z')
    late = game('late','2024-01-01T12:00Z',2024,offense=200.)
    np.testing.assert_allclose(extra_features([early],{})[ADJUSTED+ROTATION],
                               extra_features([early,late],{('late','h'):{'future':200.}}).iloc[:1][ADJUSTED+ROTATION])


def test_player_identity_mismatch_rejected(tmp_path):
    g = {**game('1','2023-01-01T12:00Z',home='10',away='20'), 'home_score':80,'away_score':60}
    data = pd.DataFrame([dict(game_id=1,season=2023,season_type=2,team_id=10,
                             opponent_team_id=99,team_score=80,opponent_team_score=60,
                             athlete_id=123,minutes=200.)])
    data.to_parquet(tmp_path/'player_box_2023.parquet')
    with pytest.raises(ValueError, match='opponent identity'):
        player_games(2023,tmp_path,[g])


def test_incomplete_rotation_is_audited_not_used(tmp_path):
    g = {**game('1','2023-01-01T12:00Z',home='10',away='20'), 'home_score':80,'away_score':60}
    data = pd.DataFrame([dict(game_id=1,season=2023,season_type=2,team_id=10,
                             opponent_team_id=20,team_score=80,opponent_team_score=60,
                             athlete_id=123,minutes=30.)])
    data.to_parquet(tmp_path/'player_box_2023.parquet')
    rows,audit = player_games(2023,tmp_path,[g])
    assert not rows
    assert audit['exclusions']['invalid_minute_total'] == 1
