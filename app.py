import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="B.P. Sports", page_icon="🏈", layout="wide")

# ---------- Styling ----------
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; max-width: 1250px;}
[data-testid="stMetricValue"] {font-size: 1.8rem;}
.bp-card {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 10px;
}
.small-muted {opacity:.68; font-size:.9rem;}
</style>
""", unsafe_allow_html=True)

st.title("🏈 B.P. SPORTS")
st.caption("NFL Prediction Dashboard • Model-first predictions, market analysis kept separate")

# ---------- Data helpers ----------
@st.cache_data
def load_predictions():
    try:
        return pd.read_csv("predictions.csv")
    except FileNotFoundError:
        return pd.DataFrame(columns=[
            "rank","week","away","home","pick","win_probability",
            "away_score","home_score","confidence","status",
            "offense_edge","defense_edge","qb_edge","recent_edge",
            "injury_edge","home_field_edge","notes"
        ])

@st.cache_data
def load_history():
    try:
        return pd.read_csv("history.csv")
    except FileNotFoundError:
        return pd.DataFrame(columns=[
            "week","away","home","pick","win_probability",
            "actual_winner","correct","projected_away_score",
            "projected_home_score","actual_away_score","actual_home_score"
        ])

pred = load_predictions()
hist = load_history()

# ---------- Sidebar ----------
st.sidebar.header("B.P. Model")
page = st.sidebar.radio(
    "Navigate",
    ["Weekly Predictions", "Game Breakdown", "Model Record", "About the Model"]
)

st.sidebar.divider()
st.sidebar.caption("Current version")
st.sidebar.write("**B.P. NFL Model v2.1**")
st.sidebar.caption("Predictions are probabilistic. No game is guaranteed.")

# ---------- Weekly Predictions ----------
if page == "Weekly Predictions":
    st.subheader("Weekly Predictions")

    if pred.empty:
        st.info("No slate has been loaded yet. Add this week's games to predictions.csv.")
    else:
        weeks = sorted(pred["week"].dropna().unique(), reverse=True)
        week = st.selectbox("Week", weeks)
        slate = pred[pred["week"] == week].copy()
        slate = slate.sort_values(["rank","win_probability"], ascending=[True,False])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Games", len(slate))
        c2.metric("Highest confidence", f"{slate['win_probability'].max():.1f}%")
        c3.metric("80%+ picks", int((slate["win_probability"] >= 80).sum()))
        c4.metric("Model", "v2.1")

        st.caption("Ranked from the model's strongest predicted winner to weakest.")

        display = slate[[
            "rank","away","home","pick","win_probability",
            "away_score","home_score","confidence"
        ]].copy()
        display["matchup"] = display["away"] + " @ " + display["home"]
        display["projected_score"] = (
            display["away"] + " " + display["away_score"].astype(str)
            + " – " + display["home"] + " " + display["home_score"].astype(str)
        )
        display["win_probability"] = display["win_probability"].map(lambda x: f"{x:.1f}%")
        display = display[[
            "rank","matchup","pick","win_probability","projected_score","confidence"
        ]]
        display.columns = ["Rank","Matchup","Pick","Win %","Projected Score","Confidence"]
        st.dataframe(display, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Sunday Update")
        st.write(
            "When the slate is refreshed, injury, QB, weather, and availability changes "
            "can be reflected here. The model prediction remains separate from market odds."
        )

# ---------- Game Breakdown ----------
elif page == "Game Breakdown":
    st.subheader("Game Breakdown")

    if pred.empty:
        st.info("Load a slate first.")
    else:
        pred = pred.copy()
        pred["game"] = pred["away"] + " @ " + pred["home"]
        game = st.selectbox("Choose a matchup", pred["game"].tolist())
        row = pred[pred["game"] == game].iloc[0]

        left, right = st.columns([1.2, 1])
        with left:
            st.markdown(f"## {row['away']} @ {row['home']}")
            st.metric("B.P. Model Pick", row["pick"])
            st.metric("Win Probability", f"{row['win_probability']:.1f}%")
            st.write(
                f"**Projected score:** {row['away']} {int(row['away_score'])} – "
                f"{row['home']} {int(row['home_score'])}"
            )
            st.write(f"**Confidence:** {row['confidence']}")

        with right:
            st.markdown("### Why the model leans this way")
            edges = pd.DataFrame({
                "Factor": ["Offense","Defense","QB","Recent form","Injuries","Home field"],
                "Edge": [
                    row["offense_edge"], row["defense_edge"], row["qb_edge"],
                    row["recent_edge"], row["injury_edge"], row["home_field_edge"]
                ]
            })
            st.bar_chart(edges.set_index("Factor"))
            if isinstance(row.get("notes"), str) and row["notes"].strip():
                st.caption(row["notes"])

        st.divider()
        st.caption(
            "Positive factor values favor the model's pick; negative values work against it. "
            "These are model contribution scores, not percentage points of win probability."
        )

# ---------- Model Record ----------
elif page == "Model Record":
    st.subheader("Model Record")

    if hist.empty:
        st.info("No completed predictions have been recorded yet.")
    else:
        completed = hist[hist["correct"].notna()].copy()
        wins = int(completed["correct"].astype(bool).sum())
        total = len(completed)
        accuracy = wins / total if total else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Straight-up record", f"{wins}–{total-wins}")
        c2.metric("Accuracy", f"{accuracy:.1%}")
        c3.metric("Predictions graded", total)

        if total:
            completed["bucket"] = pd.cut(
                completed["win_probability"],
                bins=[0,70,80,90,101],
                labels=["<70%","70–79%","80–89%","90%+"],
                right=False
            )
            calibration = (
                completed.groupby("bucket", observed=False)
                .agg(Picks=("correct","size"), Actual_Win_Rate=("correct","mean"))
                .reset_index()
            )
            calibration["Actual_Win_Rate"] = calibration["Actual_Win_Rate"].map(
                lambda x: f"{x:.1%}" if pd.notna(x) else "—"
            )
            st.markdown("### Confidence performance")
            st.dataframe(calibration, use_container_width=True, hide_index=True)

        st.markdown("### Prediction history")
        st.dataframe(completed, use_container_width=True, hide_index=True)

# ---------- About ----------
else:
    st.subheader("About the B.P. NFL Model")
    st.write(
        "The model predicts NFL games independently of sportsbook odds. "
        "Its inputs are designed around team efficiency, quarterback play, recent form, "
        "strength of schedule, turnovers, explosive plays, home field, and relevant personnel."
    )
    st.markdown("""
**Workflow**

1. Build a probability and projected score for every game.
2. Rank the slate by predicted winner probability.
3. Refresh material injury, QB, weather, and availability information.
4. Lock the prediction before kickoff.
5. Grade the result and add it to the permanent model record.
6. Evaluate calibration and improve the model using historical performance.

**Important:** A 90% prediction means the model expects comparable games to win about
nine times out of ten. It does not mean the game is a lock.
""")

    st.markdown("### Product roadmap")
    st.write(
        "Next: automatic data ingestion → historical backtesting → model calibration → "
        "market-value layer → college football model."
    )
