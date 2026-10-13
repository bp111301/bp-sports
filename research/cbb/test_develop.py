import pandas as pd
import numpy as np
from develop import build_features, FEATURES, PRIOR


def game(gid, start, home='h', away='a', score=80, neutral=False, season=2023):
    start=pd.Timestamp(start)
    return dict(game_id=gid,season=season,start=start,day=start.floor('D'),home_id=home,away_id=away,
                home=home,away=away,neutral=neutral,home_score=score,away_score=60,y=int(score>60),
                values={home:{**PRIOR,'off_eff':float(score)},away:dict(PRIOR)})


def test_current_and_future_outcomes_do_not_enter_features():
    games=[game('1','2023-01-01T12:00Z'),game('2','2023-01-03T12:00Z'),game('3','2023-01-05T12:00Z')]
    original=build_features(games)
    changed=build_features([games[0],game('2','2023-01-03T12:00Z',score=20),game('3','2023-01-05T12:00Z',score=150)])
    np.testing.assert_allclose(original.iloc[:2][FEATURES].to_numpy(dtype=float),changed.iloc[:2][FEATURES].to_numpy(dtype=float))
    assert original.iloc[2].elo_diff!=changed.iloc[2].elo_diff


def test_same_day_games_do_not_leak_and_neutral_removes_home_advantage():
    games=[game('1','2023-01-01T12:00Z'),game('2','2023-01-01T23:00Z',away='b',neutral=True)]
    original=build_features(games)
    changed=build_features([game('1','2023-01-01T12:00Z',score=20),games[1]])
    np.testing.assert_allclose(original.iloc[1][FEATURES].to_numpy(dtype=float),changed.iloc[1][FEATURES].to_numpy(dtype=float))
    assert original.iloc[1].home_advantage==0 and original.iloc[1].elo_probability==.5


def test_future_season_cannot_change_earlier_season_features():
    first=game('1','2023-01-01T12:00Z')
    alone=build_features([first])
    later=build_features([first,game('2','2024-01-01T12:00Z',score=150,season=2024)])
    np.testing.assert_allclose(alone[FEATURES].to_numpy(dtype=float),later.iloc[:1][FEATURES].to_numpy(dtype=float))


def test_midnight_boundary_does_not_assume_previous_game_has_finished():
    first=game('1','2023-01-01T23:59Z')
    next_day=game('2','2023-01-02T00:01Z',away='b')
    original=build_features([first,next_day])
    changed=build_features([game('1','2023-01-01T23:59Z',score=20),next_day])
    np.testing.assert_allclose(original.iloc[1][FEATURES].to_numpy(dtype=float),changed.iloc[1][FEATURES].to_numpy(dtype=float))
