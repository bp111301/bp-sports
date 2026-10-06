import importlib.util
from pathlib import Path
import pandas as pd

SPEC=importlib.util.spec_from_file_location("cfb_baseline",Path("research/cfb/backtest_baseline.py"))
m=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)

def test_feature_matrix_excludes_market_and_retrospective_qb():
    df=pd.DataFrame({
        "home_pregame_elo":[1600],"away_pregame_elo":[1500],"neutral_site":[False],
        "spread":[-7.5],"over_under":[55.0],
        "home_qb_games":[20],"away_qb_games":[2],
        "home_off_epa":[.2],"away_off_epa":[.1],
    })
    x=m.build_matrix(df)
    assert "elo_diff" in x and x.loc[0,"elo_diff"]==100
    assert not (set(x.columns) & m.MARKET_BLOCKLIST)
    assert not (set(x.columns) & m.RETROSPECTIVE_BLOCKLIST)

def test_home_field_zero_on_neutral():
    df=pd.DataFrame({"home_pregame_elo":[1,1],"away_pregame_elo":[1,1],"neutral_site":[True,False]})
    x=m.build_matrix(df)
    assert list(x.home_field)==[0.0,1.0]
