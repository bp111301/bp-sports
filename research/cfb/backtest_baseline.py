"""Leakage-safe CFB V1 baseline walk-forward backtest.

The source matchup-line table already computes team efficiency features using
only games/plays dated before the matchup. This script adds no betting-market
features and explicitly blocks retrospective QB identity fields.

Evaluation is expanding-window by season: each test season is predicted only
from earlier seasons.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

PAIR_BASES = [
    "off_epa","def_epa","off_pass_epa","def_pass_epa","off_rush_epa","def_rush_epa",
    "off_wepa","def_wepa","off_success_rate","def_success_rate",
    "off_early_success_rate","def_early_success_rate",
    "off_pass_success_rate","def_pass_success_rate",
    "off_rush_success_rate","def_rush_success_rate",
    "off_pts_per_scoring_opp","def_pts_per_scoring_opp",
    "off_starting_fp","def_starting_fp",
]
PRIOR_BASES = [
    "off_epa","def_epa","off_pass_epa","def_pass_epa","off_rush_epa","def_rush_epa",
    "off_success_rate","def_success_rate",
]
RETROSPECTIVE_BLOCKLIST = {
    "home_qb_name","away_qb_name","home_athlete_id","away_athlete_id",
    "home_returning_qb","away_returning_qb","home_qb_starter_years","away_qb_starter_years",
    "home_qb_games","away_qb_games",
}
MARKET_BLOCKLIST = {"spread_open","spread","over_under","over_under_open"}

def load_data(data_dir: Path) -> pd.DataFrame:
    files = sorted(data_dir.glob("cfb_matchup_line_*.csv"))
    if not files:
        raise FileNotFoundError(f"No matchup files in {data_dir}")
    frames = [pd.read_csv(f, low_memory=False) for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["season"] = pd.to_numeric(df["season"], errors="coerce")
    df["home_points"] = pd.to_numeric(df["home_points"], errors="coerce")
    df["away_points"] = pd.to_numeric(df["away_points"], errors="coerce")
    df = df.dropna(subset=["season","home_points","away_points"]).copy()
    df = df[df["home_points"] != df["away_points"]].copy()
    df["season"] = df["season"].astype(int)
    df["home_win"] = (df["home_points"] > df["away_points"]).astype(int)
    return df.sort_values(["season","week","game_id"]).reset_index(drop=True)

def numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def add_diff(out: pd.DataFrame, source: pd.DataFrame, name: str, h: str, a: str) -> None:
    if h in source.columns and a in source.columns:
        out[name] = numeric(source[h]) - numeric(source[a])

def build_matrix(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    add_diff(x, df, "elo_diff", "home_pregame_elo", "away_pregame_elo")
    neutral = df["neutral_site"] if "neutral_site" in df else False
    if getattr(neutral, "dtype", None) == object:
        neutral = neutral.astype(str).str.lower().isin(["true","1","yes"])
    x["home_field"] = (~pd.Series(neutral, index=df.index).fillna(False).astype(bool)).astype(float)
    if "conference_game" in df:
        c = df["conference_game"]
        if c.dtype == object:
            c = c.astype(str).str.lower().isin(["true","1","yes"])
        x["conference_game"] = c.fillna(False).astype(float)
    for base in PAIR_BASES:
        add_diff(x, df, f"{base}_diff", f"home_{base}", f"away_{base}")
    for base in PRIOR_BASES:
        add_diff(x, df, f"prev_{base}_diff", f"prev_home_{base}", f"prev_away_{base}")
    add_diff(x, df, "opp_elo_avg_diff", "home_opp_elo_roll_avg", "away_opp_elo_roll_avg")
    add_diff(x, df, "talent_diff", "home_talent", "away_talent")
    add_diff(x, df, "weighted_talent_diff", "home_team_talent_weighted", "away_team_talent_weighted")
    add_diff(x, df, "returning_prod_diff", "home_ovr_rtprod", "away_ovr_rtprod")
    add_diff(x, df, "hc_tenure_diff", "home_hc_tenure", "away_hc_tenure")
    return x

def feature_sets(x: pd.DataFrame) -> dict[str,list[str]]:
    elo = [c for c in ["elo_diff","home_field"] if c in x]
    core_names = [
        "elo_diff","home_field","conference_game",
        "off_epa_diff","def_epa_diff","off_pass_epa_diff","def_pass_epa_diff",
        "off_rush_epa_diff","def_rush_epa_diff","off_success_rate_diff","def_success_rate_diff",
        "off_early_success_rate_diff","def_early_success_rate_diff",
        "off_pass_success_rate_diff","def_pass_success_rate_diff",
        "off_rush_success_rate_diff","def_rush_success_rate_diff",
        "off_pts_per_scoring_opp_diff","def_pts_per_scoring_opp_diff",
        "opp_elo_avg_diff",
        "prev_off_epa_diff","prev_def_epa_diff","prev_off_success_rate_diff","prev_def_success_rate_diff",
    ]
    core = [c for c in core_names if c in x]
    cfb = core + [c for c in ["talent_diff","weighted_talent_diff","returning_prod_diff","hc_tenure_diff"] if c in x]
    return {"elo_only": elo, "efficiency": core, "cfb_context": cfb}

def model(features: list[str]) -> Pipeline:
    prep = ColumnTransformer([("num", Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ]), features)], remainder="drop")
    return Pipeline([("prep", prep), ("model", LogisticRegression(C=0.5, max_iter=3000))])

def score(y: np.ndarray, p: np.ndarray) -> dict[str,float]:
    pred = (p >= 0.5).astype(int)
    return {
        "games": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0,1])),
        "mean_confidence": float(np.mean(np.maximum(p, 1-p))),
    }

def walk_forward(df: pd.DataFrame, x: pd.DataFrame, features: list[str], first_test: int) -> tuple[pd.DataFrame,dict]:
    rows, preds = [], []
    max_season = int(df["season"].max())
    for season in range(first_test, max_season + 1):
        train_idx = df.index[df["season"] < season]
        test_idx = df.index[df["season"] == season]
        if len(train_idx) == 0 or len(test_idx) == 0:
            continue
        pipe = model(features)
        pipe.fit(x.loc[train_idx, features], df.loc[train_idx, "home_win"])
        p = pipe.predict_proba(x.loc[test_idx, features])[:,1]
        y = df.loc[test_idx, "home_win"].to_numpy()
        m = score(y,p); m["season"] = season
        rows.append(m)
        block = df.loc[test_idx, ["game_id","season","week","home_team","away_team","home_points","away_points","home_win"]].copy()
        block["home_win_prob"] = p
        block["predicted_home_win"] = (p >= .5).astype(int)
        preds.append(block)
    pred_df = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame()
    overall = score(pred_df["home_win"].to_numpy(), pred_df["home_win_prob"].to_numpy()) if len(pred_df) else {}
    return pd.DataFrame(rows), overall

def calibration(pred: pd.DataFrame) -> list[dict]:
    if pred.empty: return []
    conf = np.maximum(pred.home_win_prob, 1-pred.home_win_prob)
    correct = (pred.predicted_home_win == pred.home_win).astype(int)
    bins = [(0.50,0.55),(0.55,0.60),(0.60,0.65),(0.65,0.70),(0.70,0.80),(0.80,0.90),(0.90,1.001)]
    out=[]
    for lo,hi in bins:
        mask=(conf>=lo)&(conf<hi)
        if mask.any():
            out.append({"bucket":f"{lo:.0%}-{min(hi,1):.0%}","games":int(mask.sum()),"mean_confidence":float(conf[mask].mean()),"accuracy":float(correct[mask].mean())})
    return out

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-dir",default="runtime/cfb/matchup_line")
    ap.add_argument("--out-dir",default="research/cfb/results")
    ap.add_argument("--first-test-season",type=int,default=2018)
    args=ap.parse_args()
    df=load_data(Path(args.data_dir))
    leaked=(RETROSPECTIVE_BLOCKLIST|MARKET_BLOCKLIST) & set(build_matrix(df).columns)
    if leaked:
        raise RuntimeError(f"Blocked features entered matrix: {sorted(leaked)}")
    x=build_matrix(df); sets=feature_sets(x)
    out_dir=Path(args.out_dir); out_dir.mkdir(parents=True,exist_ok=True)
    summary={"data":{"seasons":[int(df.season.min()),int(df.season.max())],"completed_games":int(len(df))},"candidates":{}}
    all_seasons=[]
    for name,features in sets.items():
        seasons,overall=walk_forward(df,x,features,args.first_test_season)
        seasons["candidate"]=name; all_seasons.append(seasons)
        # recreate predictions for calibration using same loop
        pred_parts=[]
        for season in range(args.first_test_season,int(df.season.max())+1):
            tr=df.index[df.season<season]; te=df.index[df.season==season]
            if not len(tr) or not len(te): continue
            pipe=model(features); pipe.fit(x.loc[tr,features],df.loc[tr,"home_win"])
            p=pipe.predict_proba(x.loc[te,features])[:,1]
            z=df.loc[te,["home_win"]].copy(); z["home_win_prob"]=p; z["predicted_home_win"]=(p>=.5).astype(int); pred_parts.append(z)
        pred=pd.concat(pred_parts) if pred_parts else pd.DataFrame()
        summary["candidates"][name]={"features":features,"overall":overall,"calibration":calibration(pred)}
    season_df=pd.concat(all_seasons,ignore_index=True)
    season_df.to_csv(out_dir/"baseline_by_season.csv",index=False)
    (out_dir/"baseline_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    best=min(summary["candidates"],key=lambda k:summary["candidates"][k]["overall"]["brier"])
    lines=["# CFB V1 Baseline Results","",f"Completed FBS-vs-FBS games loaded: {len(df):,}",f"Walk-forward test begins: {args.first_test_season}","",
           "| Candidate | Accuracy | Brier | Log loss | Games |","|---|---:|---:|---:|---:|"]
    for name,v in summary["candidates"].items():
        m=v["overall"]; lines.append(f"| {name} | {m['accuracy']:.2%} | {m['brier']:.4f} | {m['log_loss']:.4f} | {m['games']:,} |")
    lines += ["",f"Current baseline leader by Brier: **{best}**.","",
              "Market spreads/totals and retrospective realized-QB fields are excluded from every candidate.",
              "These are development backtests, not prospective accuracy claims."]
    (out_dir/"BASELINE_REPORT.md").write_text("\n".join(lines)+"\n")
    print("\n".join(lines))

if __name__=="__main__":
    main()
