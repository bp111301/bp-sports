import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="B.P. Sports",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
#MainMenu, footer {visibility:hidden}
.block-container {max-width:1050px; padding-top:4.25rem; padding-bottom:4rem}
.brand {font-size:2.25rem; font-weight:950; letter-spacing:-.04em}
.sub {opacity:.62; margin-bottom:18px}
.hero {background:linear-gradient(145deg,#20252e,#12151a); border:1px solid #343b47; border-radius:20px; padding:18px 20px; margin:10px 0 20px}
.card {background:linear-gradient(145deg,#242933,#15181e); border:1px solid #353b46; border-top:6px solid #777; border-radius:20px; padding:22px; margin:15px 0}
.meta {font-size:.73rem; font-weight:850; opacity:.55; letter-spacing:.04em}
.teams {display:grid; grid-template-columns:1fr auto 1fr; gap:14px; align-items:center; margin:16px 0 18px}
.team {font-size:1.55rem; font-weight:950}
.at {font-size:.78rem; opacity:.5; font-weight:800}
.right {text-align:right}
.line {border-top:1px solid #343943; padding-top:15px}
.label {font-size:.70rem; font-weight:850; opacity:.55; letter-spacing:.05em}
.pick {font-size:1.45rem; font-weight:950; margin-top:2px}
.prow {display:flex; justify-content:space-between; font-weight:850; margin-top:12px}
.bar {height:10px; background:#333842; border-radius:20px; overflow:hidden; margin:6px 0 12px}
.fill {height:100%; background:linear-gradient(90deg,#f1f1f1,#8e98a8)}
.badge {display:inline-block; background:#303640; border:1px solid #3d4552; border-radius:20px; padding:5px 10px; font-size:.70rem; font-weight:850; margin:3px 5px 3px 0}
.warn {background:#3a3021; border-color:#665333}
.prov {background:#38272c; border-color:#68404a}
.compare {margin-top:14px; font-size:.86rem; opacity:.82}
.small {font-size:.82rem; opacity:.68}
@media(max-width:650px){
 .block-container{padding-left:14px;padding-right:14px;padding-top:3.5rem}
 .card{padding:17px}.team{font-size:1.15rem}.pick{font-size:1.25rem}
}
</style>
""",
    unsafe_allow_html=True,
)

TEAM_COLORS = {
    "ARI":"#97233F","ATL":"#A71930","BAL":"#241773","BUF":"#00338D",
    "CAR":"#0085CA","CHI":"#C83803","CIN":"#FB4F14","CLE":"#FF3C00",
    "DAL":"#003594","DEN":"#FB4F14","DET":"#0076B6","GB":"#203731",
    "HOU":"#03202F","IND":"#002C5F","JAX":"#006778","KC":"#E31837",
    "LA":"#003594","LAC":"#0080C6","LAR":"#003594","LV":"#A5ACAF",
    "MIA":"#008E97","MIN":"#4F2683","NE":"#C60C30","NO":"#D3BC8D",
    "NYG":"#0B2265","NYJ":"#125740","PHI":"#004C54","PIT":"#FFB612",
    "SEA":"#69BE28","SF":"#AA0000","TB":"#D50A0A","TEN":"#4B92DB",
    "WAS":"#5A1414",
}

TEAM_NAMES = {
    "ARI":"Cardinals","ATL":"Falcons","BAL":"Ravens","BUF":"Bills","CAR":"Panthers",
    "CHI":"Bears","CIN":"Bengals","CLE":"Browns","DAL":"Cowboys","DEN":"Broncos",
    "DET":"Lions","GB":"Packers","HOU":"Texans","IND":"Colts","JAX":"Jaguars",
    "KC":"Chiefs","LA":"Rams","LAC":"Chargers","LAR":"Rams","LV":"Raiders",
    "MIA":"Dolphins","MIN":"Vikings","NE":"Patriots","NO":"Saints","NYG":"Giants",
    "NYJ":"Jets","PHI":"Eagles","PIT":"Steelers","SEA":"Seahawks","SF":"49ers",
    "TB":"Buccaneers","TEN":"Titans","WAS":"Commanders",
}

@st.cache_data(ttl=60)
def load_csv(name):
    try:
        return pd.read_csv(name)
    except Exception:
        return pd.DataFrame()

pred = load_csv("data/current/website_feed.csv")
if pred.empty:
    pred = load_csv("bp_week5_website_feed.csv")
hist = load_csv("history.csv")

def load_json(name):
    try:
        import json
        with open(name, "r") as handle:
            return json.load(handle)
    except Exception:
        return {}

metadata = load_json("data/current/prediction_metadata.json")
tracking = load_json("data/ledger/summary.json")

st.markdown(
    '<div class="brand">🏈 B.P. SPORTS</div>'
    '<div class="sub">Independent NFL predictions • Frozen V4 forward test • Automated pipeline</div>',
    unsafe_allow_html=True,
)

t1, t2, t3 = st.tabs(["🏠 Predictions", "📊 Model Record", "🧠 About"])

with t1:
    if pred.empty:
        st.error("Week 5 model feed not found. Make sure bp_week5_website_feed.csv is in the repository root.")
    else:
        pred = pred.copy()
        pred["v4_adjusted_confidence"] = pd.to_numeric(pred["v4_adjusted_confidence"], errors="coerce")
        pred["v4_core_confidence"] = pd.to_numeric(pred["v4_core_confidence"], errors="coerce")
        pred["v3_confidence"] = pd.to_numeric(pred["v3_confidence"], errors="coerce")
        pred = pred.sort_values("v4_adjusted_confidence", ascending=False).reset_index(drop=True)

        locked = pred[~pred["prediction_status"].astype(str).str.startswith("PROVISIONAL")]
        provisional = pred[pred["prediction_status"].astype(str).str.startswith("PROVISIONAL")]
        avg_conf = pred["v4_adjusted_confidence"].mean() * 100

        st.markdown(
            f'''<div class="hero"><div class="meta">2026 • WEEK 5 • FORWARD TEST</div>
            <div style="font-size:1.25rem;font-weight:900;margin-top:4px">Frozen V4 is live</div>
            <div class="small">{len(locked)} early locks • {len(provisional)} provisional • {avg_conf:.1f}% average adjusted confidence</div></div>''',
            unsafe_allow_html=True,
        )

        week_label = metadata.get("week", 5)
        st.header(f"NFL • WEEK {week_label}")
        st.caption("V4 picks are generated independently of betting markets. Risk layers can adjust confidence, but do not flip the winner.")

        for rank, (_, r) in enumerate(pred.iterrows(), start=1):
            away = str(r["away_team"])
            home = str(r["home_team"])
            pick = str(r["v4_pick"])
            v4 = float(r["v4_adjusted_confidence"])
            core = float(r["v4_core_confidence"])
            v3 = float(r["v3_confidence"])
            status = str(r.get("prediction_status", "EARLY_LOCK"))
            provisional_flag = status.startswith("PROVISIONAL")
            accent = TEAM_COLORS.get(pick, "#777777")

            badges = []
            if provisional_flag:
                badges.append('<span class="badge prov">⏳ PROVISIONAL</span>')
            else:
                badges.append('<span class="badge">🔒 EARLY LOCK</span>')
            if bool(r.get("explosive_extreme", False)):
                badges.append('<span class="badge warn">⚡ EXPLOSIVE SIGNAL</span>')
            if bool(r.get("turnover_risk_flag", False)):
                badges.append('<span class="badge warn">↔ TURNOVER RISK</span>')
            if bool(r.get("early_down_risk_flag", False)):
                badges.append('<span class="badge warn">⚠ EARLY-DOWN RISK</span>')
            qb_note = r.get("qb_status_flag", "")
            if pd.notna(qb_note) and str(qb_note).strip():
                badges.append('<span class="badge warn">QB WATCH</span>')

            delta = (v4 - v3) * 100
            delta_text = f"{delta:+.1f} pts vs V3"
            core_delta = (v4 - core) * 100
            layer_text = "No confidence-layer adjustment" if abs(core_delta) < .05 else f"Risk layers adjusted confidence {core_delta:+.1f} pts"

            html = f'''
            <div class="card" style="border-top-color:{accent}">
              <div class="meta">#{rank} V4 CONFIDENCE • {r['game_id']}</div>
              <div class="teams">
                <div class="team">{away}<div class="small">{TEAM_NAMES.get(away, away)}</div></div>
                <div class="at">@</div>
                <div class="team right">{home}<div class="small">{TEAM_NAMES.get(home, home)}</div></div>
              </div>
              <div class="line">
                <div class="label">B.P. SPORTS V4 PICK</div>
                <div class="pick">{pick} • {v4*100:.1f}%</div>
                <div class="prow"><span>ADJUSTED WIN CONFIDENCE</span><span>{v4*100:.1f}%</span></div>
                <div class="bar"><div class="fill" style="width:{v4*100:.1f}%"></div></div>
                {''.join(badges)}
                <div class="compare"><b>V3:</b> {r['v3_pick']} {v3*100:.1f}% &nbsp;•&nbsp; <b>V4 core:</b> {core*100:.1f}% &nbsp;•&nbsp; {delta_text}<br>{layer_text}</div>
              </div>
            </div>
            '''
            st.markdown(html, unsafe_allow_html=True)

            with st.expander(f"Model breakdown • {away} @ {home}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("V3 confidence", f"{v3*100:.1f}%")
                c2.metric("V4 core", f"{core*100:.1f}%")
                c3.metric("V4 adjusted", f"{v4*100:.1f}%", f"{(v4-v3)*100:+.1f} vs V3")

                st.markdown("#### What changed")
                notes = []
                if bool(r.get("explosive_extreme", False)):
                    notes.append("Explosive-play matchup reached the model's extreme-signal threshold.")
                if bool(r.get("turnover_risk_flag", False)):
                    notes.append("Recent turnover matchup conflicts with the V4 pick, so confidence is reduced rather than flipping the winner.")
                if bool(r.get("early_down_risk_flag", False)):
                    notes.append("Early-down efficiency is acting as a risk flag against the V4 lean.")
                if not notes:
                    notes.append("No secondary risk layer materially changed the frozen V4 core probability.")
                for note in notes:
                    st.write("• " + note)

                if pd.notna(qb_note) and str(qb_note).strip():
                    st.markdown("#### QB status")
                    st.warning(str(qb_note))

                st.markdown("#### Prediction status")
                if provisional_flag:
                    st.warning("This game is provisional and must be refreshed before it becomes an official graded prediction.")
                else:
                    st.success("Early-lock snapshot preserved. The final pregame snapshot will become the official graded prediction.")

        st.info("Final pregame snapshots will incorporate legitimate QB/injury/weather updates. Once a game kicks off, its graded prediction is never rewritten.")

with t2:
    st.header("B.P. Model Record")
    st.metric("Frozen V4 historical candidate", "65.02%", "1,279–688 on reused 2018–2025 sample")
    st.caption("That historical sample was used during development, so the 2026 forward test is the evidence that matters now.")
    live = tracking.get("v4_adjusted", {})
    if live.get("games", 0):
        c1, c2, c3 = st.columns(3)
        wins = live.get("correct", 0)
        games = live.get("games", 0)
        c1.metric("2026 V4 record", f"{wins}–{games-wins}", f"{live.get('accuracy',0)*100:.1f}%")
        c2.metric("Brier score", f"{live.get('brier',0):.4f}")
        c3.metric("Log loss", f"{live.get('log_loss',0):.4f}")
        v3_live = tracking.get("v3", {})
        if v3_live.get("games", 0):
            v3_wins = v3_live.get("correct", 0)
            v3_games = v3_live.get("games", 0)
            st.caption(f"V3 comparison: {v3_wins}–{v3_games-v3_wins} • {v3_live.get('accuracy',0)*100:.1f}% • Brier {v3_live.get('brier',0):.4f}")
    elif hist.empty or "correct" not in hist.columns or hist["correct"].dropna().empty:
        st.info("2026 forward record: 0–0. Week 5 begins the frozen V4 live test.")
    else:
        st.dataframe(hist, use_container_width=True, hide_index=True)

with t3:
    st.header("How B.P. Sports Works")
    st.write("B.P. Sports predicts NFL games independently of betting lines. The frozen V4 core uses team efficiency, recent form, opponent-adjusted performance, Elo/team strength, rest, home field and a leakage-safe quarterback layer.")
    st.write("Explosive plays, turnovers and early-down efficiency are secondary confidence/risk signals. They can raise or lower confidence when their historical rules trigger, but they do not change the selected winner.")
    st.write("Market prices belong to a separate value-analysis layer. They are not allowed to choose the B.P. Sports prediction.")
    st.write("The 2026 season is the forward test. Pregame snapshots are preserved, and predictions are graded after kickoff without hindsight edits.")
