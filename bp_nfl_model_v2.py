
"""
B.P. NFL Prediction Model — Version 2
--------------------------------------

Adds:
1. Learned weights via logistic regression.
2. Time-ordered walk-forward validation.
3. Accuracy and Brier-score evaluation.
4. A separate score-margin model.
5. No look-ahead: each game is predicted using only information available
   before that game.

Expected historical CSV columns:
    date, home_team, away_team, home_score, away_score,
    home_off_epa, away_off_epa,
    home_def_epa, away_def_epa,
    home_qb_rating, away_qb_rating,
    home_success_off, away_success_off,
    home_success_def, away_success_def,
    home_turnover_diff, away_turnover_diff,
    home_explosive, away_explosive,
    home_sos, away_sos

The feature engineering creates matchup differences:
    home offense - away defense
    away offense - home defense
    QB difference
    offensive success difference
    defensive success difference
    turnover difference
    explosive-play difference
    SOS difference
    home-field indicator

Run:
    python bp_nfl_model_v2.py games.csv

This is a research/backtesting model, not a guarantee of future results.
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, brier_score_loss, mean_absolute_error
except ImportError:
    raise SystemExit(
        "Install scikit-learn first: pip install scikit-learn"
    )


FEATURES = [
    "off_vs_def",
    "def_vs_off",
    "qb_diff",
    "off_success_diff",
    "def_success_diff",
    "turnover_diff",
    "explosive_diff",
    "sos_diff",
    "home_field",
]

REQUIRED = [
    "date", "home_team", "away_team", "home_score", "away_score",
    "home_off_epa", "away_off_epa",
    "home_def_epa", "away_def_epa",
    "home_qb_rating", "away_qb_rating",
    "home_success_off", "away_success_off",
    "home_success_def", "away_success_def",
    "home_turnover_diff", "away_turnover_diff",
    "home_explosive", "away_explosive",
    "home_sos", "away_sos",
]


def build_features(games):
    g = games.copy()

    # Defensive EPA: lower allowed EPA is better, so invert its contribution.
    g["off_vs_def"] = g["home_off_epa"] - g["away_def_epa"]
    g["def_vs_off"] = g["away_off_epa"] - g["home_def_epa"]
    g["qb_diff"] = g["home_qb_rating"] - g["away_qb_rating"]
    g["off_success_diff"] = g["home_success_off"] - g["away_success_off"]

    # Lower defensive success rate allowed is better.
    g["def_success_diff"] = (
        g["away_success_def"] - g["home_success_def"]
    )

    g["turnover_diff"] = (
        g["home_turnover_diff"] - g["away_turnover_diff"]
    )
    g["explosive_diff"] = (
        g["home_explosive"] - g["away_explosive"]
    )
    g["sos_diff"] = g["home_sos"] - g["away_sos"]
    g["home_field"] = 1.0

    return g


def train_models(train):
    X = train[FEATURES]
    y = (train["home_score"] > train["away_score"]).astype(int)

    # Logistic regression learns the win-probability relationship.
    win_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=0.5, max_iter=5000)
    )
    win_model.fit(X, y)

    # Ridge regression predicts expected scoring margin.
    margin = train["home_score"] - train["away_score"]
    margin_model = make_pipeline(
        StandardScaler(),
        Ridge(alpha=10.0)
    )
    margin_model.fit(X, margin)

    return win_model, margin_model


def walk_forward_backtest(games, min_train_games=150):
    """
    Strict chronological evaluation.
    Every prediction is made before seeing that game's result.
    """
    games = games.sort_values("date").reset_index(drop=True)
    games = build_features(games)

    predictions = []
    actuals = []

    for i in range(min_train_games, len(games)):
        train = games.iloc[:i]
        test = games.iloc[[i]]

        win_model, margin_model = train_models(train)

        X_test = test[FEATURES]
        p_home = win_model.predict_proba(X_test)[0, 1]
        pred_margin = margin_model.predict(X_test)[0]

        actual_home_win = int(
            test["home_score"].iloc[0] > test["away_score"].iloc[0]
        )

        predictions.append({
            "date": test["date"].iloc[0],
            "home_team": test["home_team"].iloc[0],
            "away_team": test["away_team"].iloc[0],
            "p_home": p_home,
            "pred_margin": pred_margin,
            "actual_home_win": actual_home_win,
        })
        actuals.append(actual_home_win)

    out = pd.DataFrame(predictions)

    if out.empty:
        raise ValueError("Not enough games for the requested backtest.")

    pred_winner = (out["p_home"] >= 0.5).astype(int)

    accuracy = accuracy_score(out["actual_home_win"], pred_winner)
    brier = brier_score_loss(out["actual_home_win"], out["p_home"])

    print("\nB.P. NFL WALK-FORWARD BACKTEST")
    print("--------------------------------")
    print(f"Games tested: {len(out)}")
    print(f"Straight-up accuracy: {accuracy:.3%}")
    print(f"Brier score: {brier:.4f}")
    print(
        "Interpretation: lower Brier score is better; "
        "50% accuracy is roughly coin-flip territory."
    )

    return out


def train_current_model(games):
    games = build_features(games)
    win_model, margin_model = train_models(games)
    return win_model, margin_model


def predict_game(win_model, margin_model, row):
    g = pd.DataFrame([row])
    g = build_features(g)

    X = g[FEATURES]
    p_home = float(win_model.predict_proba(X)[0, 1])
    margin = float(margin_model.predict(X)[0])

    if p_home >= 0.5:
        winner = row["home_team"]
        winner_probability = p_home
    else:
        winner = row["away_team"]
        winner_probability = 1 - p_home

    # Simple scoring projection around a 44.5-point league environment.
    total = 44.5
    home_score = round((total + margin) / 2)
    away_score = round((total - margin) / 2)

    return {
        "winner": winner,
        "winner_probability": winner_probability,
        "projected_margin": margin,
        "projected_score": (
            f"{row['home_team']} {home_score} - "
            f"{row['away_team']} {away_score}"
        ),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python bp_nfl_model_v2.py games.csv")
        raise SystemExit(1)

    path = Path(sys.argv[1])
    games = pd.read_csv(path)
    games["date"] = pd.to_datetime(games["date"])

    missing = [c for c in REQUIRED if c not in games.columns]
    if missing:
        raise SystemExit(
            "CSV is missing required columns:\n" + "\n".join(missing)
        )

    # Historical evaluation first.
    backtest = walk_forward_backtest(games)

    # Train final model on all available historical games.
    win_model, margin_model = train_current_model(games)

    print("\nFinal model trained on all available games.")
    print("Use the returned models with predict_game() for future matchups.")
