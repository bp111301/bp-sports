import json
import html
import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="B.P. Sports • NFL",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
:root{
  --bp-bg:#080b10;
  --bp-panel:#11161f;
  --bp-panel-2:#171d27;
  --bp-border:#27303d;
  --bp-text:#f5f7fb;
  --bp-muted:#8d98a8;
  --bp-blue:#6ea8fe;
  --bp-green:#44d17a;
  --bp-gold:#f5c451;
  --bp-red:#ff6b7a;
}
html,body,[class*="css"]{font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.stApp{background:
  radial-gradient(circle at 50% -10%,rgba(55,95,150,.16),transparent 28rem),
  linear-gradient(180deg,#0a0d13 0%,#080b10 100%);
  color:var(--bp-text)}
#MainMenu,footer{visibility:hidden}
header[data-testid="stHeader"]{background:rgba(8,11,16,.86);backdrop-filter:blur(14px)}
.block-container{max-width:1160px;padding-top:2.4rem;padding-bottom:5rem}
.bp-nav{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:7px 0 18px;border-bottom:1px solid var(--bp-border);margin-bottom:22px}
.bp-logo{display:flex;align-items:center;gap:11px}
.bp-mark{width:40px;height:40px;border-radius:11px;background:linear-gradient(145deg,#8cb9ff,#386fc6);display:flex;align-items:center;justify-content:center;color:#07101f;font-weight:1000;font-size:1rem;box-shadow:0 8px 24px rgba(71,126,211,.25)}
.bp-wordmark{font-size:1.42rem;font-weight:950;letter-spacing:-.045em;line-height:1}
.bp-wordmark span{color:var(--bp-blue)}
.bp-kicker{font-size:.67rem;color:var(--bp-muted);font-weight:800;letter-spacing:.12em;margin-top:5px}
.live-pill{display:inline-flex;align-items:center;gap:7px;padding:7px 11px;border:1px solid #294a37;background:#12241a;border-radius:999px;font-size:.67rem;font-weight:900;letter-spacing:.08em;color:#9ae6b4;white-space:nowrap}
.live-dot{width:7px;height:7px;background:var(--bp-green);border-radius:50%;box-shadow:0 0 0 4px rgba(68,209,122,.11)}
.hero{position:relative;overflow:hidden;background:linear-gradient(135deg,#172131 0%,#10151e 52%,#121923 100%);border:1px solid #2c3747;border-radius:24px;padding:28px;margin:8px 0 18px;box-shadow:0 18px 55px rgba(0,0,0,.22)}
.hero:after{content:"BP";position:absolute;right:-15px;top:-55px;font-size:11rem;font-weight:1000;letter-spacing:-.12em;color:rgba(255,255,255,.025);transform:rotate(-8deg);pointer-events:none}
.eyebrow{font-size:.68rem;font-weight:900;letter-spacing:.12em;color:var(--bp-blue);text-transform:uppercase}
.hero-title{font-size:2.15rem;line-height:1.02;font-weight:1000;letter-spacing:-.055em;margin:7px 0 9px;max-width:680px}
.hero-copy{max-width:720px;color:#aeb8c7;font-size:.91rem;line-height:1.55}
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0 7px}
.stat{background:rgba(6,9,14,.42);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:12px 14px}
.stat-v{font-size:1.18rem;font-weight:950;letter-spacing:-.025em}
.stat-l{font-size:.62rem;color:var(--bp-muted);font-weight:850;letter-spacing:.08em;text-transform:uppercase;margin-top:2px}
.section-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin:25px 0 8px}
.section-title{font-size:1.3rem;font-weight:950;letter-spacing:-.035em}
.section-sub{font-size:.76rem;color:var(--bp-muted)}
.spotlight{display:grid;grid-template-columns:1fr auto;gap:20px;align-items:center;background:linear-gradient(135deg,#182234,#101720);border:1px solid #334159;border-radius:19px;padding:19px 21px;margin:10px 0 18px}
.spot-title{font-size:.68rem;color:var(--bp-gold);font-weight:900;letter-spacing:.12em}
.spot-match{font-size:1.2rem;font-weight:950;margin-top:5px}
.spot-note{font-size:.78rem;color:var(--bp-muted);margin-top:3px}
.spot-prob{text-align:right;font-size:2rem;font-weight:1000;letter-spacing:-.055em}
.spot-prob small{display:block;font-size:.61rem;color:var(--bp-muted);letter-spacing:.08em}
.card{position:relative;background:linear-gradient(145deg,#151b24,#10151c);border:1px solid #27313e;border-left:5px solid #777;border-radius:18px;padding:18px 20px;margin:11px 0;box-shadow:0 8px 28px rgba(0,0,0,.12);transition:transform .15s ease,border-color .15s ease}
.card:hover{transform:translateY(-1px);border-color:#3a4657}
.card-top{display:flex;align-items:center;justify-content:space-between;gap:12px}
.game-meta{font-size:.64rem;color:var(--bp-muted);font-weight:850;letter-spacing:.08em;text-transform:uppercase}
.tier{padding:5px 9px;border-radius:999px;font-size:.62rem;font-weight:950;letter-spacing:.07em;white-space:nowrap}
.tier-strong{background:#153222;color:#8ee2ac;border:1px solid #285c3c}
.tier-solid{background:#172b46;color:#9dc4ff;border:1px solid #294b77}
.tier-lean{background:#30291a;color:#f3d17d;border:1px solid #5b4a25}
.tier-toss{background:#302126;color:#ffadb7;border:1px solid #59333c}
.match-row{display:grid;grid-template-columns:minmax(0,1fr) 48px minmax(0,1fr);align-items:center;gap:10px;margin:15px 0}
.team-box{display:flex;align-items:center;gap:10px;min-width:0}
.team-box.home{justify-content:flex-end;text-align:right}
.team-dot{width:39px;height:39px;min-width:39px;border-radius:12px;display:flex;align-items:center;justify-content:center;color:white;font-size:.68rem;font-weight:950;box-shadow:inset 0 0 0 1px rgba(255,255,255,.13)}
.team-abbr{font-size:1.15rem;font-weight:1000;line-height:1}
.team-name{font-size:.7rem;color:var(--bp-muted);margin-top:4px}
.at{text-align:center;color:#657082;font-size:.68rem;font-weight:900}
.pick-panel{display:grid;grid-template-columns:1fr 190px;gap:18px;align-items:end;border-top:1px solid #252d38;padding-top:14px}
.pick-label{font-size:.61rem;color:var(--bp-muted);font-weight:900;letter-spacing:.1em}
.pick-name{font-size:1.35rem;font-weight:1000;letter-spacing:-.03em;margin-top:2px}
.prob{text-align:right;font-size:1.65rem;font-weight:1000;letter-spacing:-.045em}
.prob span{display:block;font-size:.58rem;color:var(--bp-muted);font-weight:850;letter-spacing:.08em}
.bar{height:7px;background:#252c36;border-radius:99px;overflow:hidden;margin-top:11px}
.fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#78aaff,#c1d7ff)}
.badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.badge{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.59rem;font-weight:900;letter-spacing:.055em;background:#202833;border:1px solid #303b49;color:#b8c3d2}
.badge-lock{background:#14291d;border-color:#285038;color:#91dbaa}
.badge-warn{background:#30281a;border-color:#584824;color:#efd17f}
.badge-prov{background:#302027;border-color:#58333e;color:#ffacb6}
.model-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:12px}
.model-cell{background:#0c1117;border:1px solid #222b36;border-radius:10px;padding:8px 10px}
.model-cell .m{font-size:.58rem;color:var(--bp-muted);font-weight:850;letter-spacing:.06em}
.model-cell .v{font-size:.82rem;font-weight:900;margin-top:2px}
.layer-note{font-size:.68rem;color:#8894a4;margin-top:9px}
.record-hero{background:linear-gradient(135deg,#151d29,#0e141c);border:1px solid #293544;border-radius:20px;padding:22px;margin:8px 0 18px}
.record-big{font-size:2.6rem;font-weight:1000;letter-spacing:-.06em}
.record-label{font-size:.68rem;color:var(--bp-muted);font-weight:850;letter-spacing:.09em}
.about-card{background:#10161e;border:1px solid #27313d;border-radius:16px;padding:18px 20px;margin:10px 0}
.about-num{font-size:.67rem;color:var(--bp-blue);font-weight:950;letter-spacing:.1em}
.about-title{font-size:1rem;font-weight:950;margin:3px 0}
.about-copy{font-size:.82rem;color:#a3adbb;line-height:1.55}
div[data-baseweb="tab-list"]{gap:5px;background:#0d1219;border:1px solid #242d39;border-radius:13px;padding:4px;margin-bottom:10px}
button[data-baseweb="tab"]{border-radius:9px;padding:8px 14px!important;font-weight:800!important}
div[data-testid="stExpander"]{border:1px solid #252f3b!important;border-radius:13px!important;background:#0e131a!important;margin-top:-5px!important;margin-bottom:11px!important}
@media(max-width:760px){
 .block-container{padding:1.6rem 12px 4rem}
 .bp-nav{margin-bottom:15px}.bp-kicker{display:none}.bp-wordmark{font-size:1.2rem}.bp-mark{width:36px;height:36px}
 .live-pill{font-size:.58rem;padding:6px 8px}
 .hero{padding:20px 17px;border-radius:18px}.hero-title{font-size:1.62rem}.hero-copy{font-size:.8rem}
 .stat-grid{grid-template-columns:repeat(2,1fr)}
 .spotlight{padding:16px;grid-template-columns:1fr auto}.spot-prob{font-size:1.55rem}
 .card{padding:15px 14px;border-radius:15px}
 .match-row{grid-template-columns:minmax(0,1fr) 28px minmax(0,1fr)}
 .team-dot{width:34px;height:34px;min-width:34px;border-radius:10px}.team-abbr{font-size:1rem}.team-name{font-size:.62rem}
 .pick-panel{grid-template-columns:1fr auto;gap:8px}.pick-name{font-size:1.18rem}.prob{font-size:1.35rem}
 .model-strip{grid-template-columns:1fr 1fr 1fr}.model-cell{padding:7px}.model-cell .v{font-size:.72rem}
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
    "SEA":"#69BE28","SF":"#AA0000","TB":"#D50A0A","TEN":"#4B92DB","WAS":"#5A1414",
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

@st.cache_data(ttl=60)
def load_json(name):
    try:
        with open(name, "r") as handle:
            return json.load(handle)
    except Exception:
        return {}

def is_true(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}

def confidence_tier(p):
    pct = p * 100
    if pct >= 70:
        return "STRONG", "tier-strong"
    if pct >= 60:
        return "SOLID", "tier-solid"
    if pct >= 55:
        return "LEAN", "tier-lean"
    return "TOSS-UP", "tier-toss"

def team_block(team, home=False):
    safe = html.escape(team)
    name = html.escape(TEAM_NAMES.get(team, team))
    color = TEAM_COLORS.get(team, "#526071")
    dot = f'<div class="team-dot" style="background:{color}">{safe}</div>'
    txt = f'<div><div class="team-abbr">{safe}</div><div class="team-name">{name}</div></div>'
    return f'<div class="team-box{" home" if home else ""}">{txt + dot if home else dot + txt}</div>'

pred = load_csv("data/current/website_feed.csv")
if pred.empty:
    pred = load_csv("bp_week5_website_feed.csv")
hist = load_csv("history.csv")
metadata = load_json("data/current/prediction_metadata.json")
tracking = load_json("data/ledger/summary.json")

week_label = metadata.get("week", 5)
captured = str(metadata.get("captured_at_utc", ""))
fresh_text = "AUTOMATED V4"
if captured:
    try:
        fresh_text = f"UPDATED {pd.to_datetime(captured).strftime('%b %d • %I:%M %p UTC').upper()}"
    except Exception:
        pass

st.markdown(
    f'''<div class="bp-nav">
      <div class="bp-logo">
        <div class="bp-mark">BP</div>
        <div><div class="bp-wordmark">B.P. <span>SPORTS</span></div><div class="bp-kicker">INDEPENDENT NFL INTELLIGENCE</div></div>
      </div>
      <div class="live-pill"><span class="live-dot"></span>{html.escape(fresh_text)}</div>
    </div>''',
    unsafe_allow_html=True,
)

t1, t2, t3 = st.tabs(["PREDICTIONS", "MODEL RECORD", "THE MODEL"])

with t1:
    if pred.empty:
        st.error("The current prediction feed is unavailable.")
    else:
        pred = pred.copy()
        for col in ["v4_adjusted_confidence", "v4_core_confidence", "v3_confidence"]:
            pred[col] = pd.to_numeric(pred[col], errors="coerce")
        pred = pred.dropna(subset=["v4_adjusted_confidence"]).sort_values("v4_adjusted_confidence", ascending=False).reset_index(drop=True)

        provisional_mask = pred["prediction_status"].astype(str).str.startswith("PROVISIONAL")
        locked = pred[~provisional_mask]
        provisional = pred[provisional_mask]
        avg_conf = pred["v4_adjusted_confidence"].mean() * 100
        strong_count = int((pred["v4_adjusted_confidence"] >= .60).sum())
        risk_count = sum(
            is_true(r.get("turnover_risk_flag", False)) or
            is_true(r.get("early_down_risk_flag", False))
            for _, r in pred.iterrows()
        )

        st.markdown(
            f'''<div class="hero">
              <div class="eyebrow">2026 • NFL WEEK {week_label} • FORWARD TEST</div>
              <div class="hero-title">The B.P. Sports Week {week_label} Board</div>
              <div class="hero-copy">Frozen V4 ranks every matchup independently of betting markets. Quarterback context lives in the core model; explosive plays, turnovers and early-down efficiency can adjust confidence without changing the selected winner.</div>
              <div class="stat-grid">
                <div class="stat"><div class="stat-v">{len(pred)}</div><div class="stat-l">Games tracked</div></div>
                <div class="stat"><div class="stat-v">{len(locked)}</div><div class="stat-l">Early locks</div></div>
                <div class="stat"><div class="stat-v">{strong_count}</div><div class="stat-l">60%+ picks</div></div>
                <div class="stat"><div class="stat-v">{avg_conf:.1f}%</div><div class="stat-l">Avg confidence</div></div>
              </div>
            </div>''',
            unsafe_allow_html=True,
        )

        top = pred.iloc[0]
        top_pick = str(top["v4_pick"])
        top_away, top_home = str(top["away_team"]), str(top["home_team"])
        top_prob = float(top["v4_adjusted_confidence"]) * 100
        st.markdown(
            f'''<div class="spotlight">
              <div><div class="spot-title">B.P. TOP CONFIDENCE</div>
              <div class="spot-match">{html.escape(top_away)} @ {html.escape(top_home)} → {html.escape(top_pick)}</div>
              <div class="spot-note">{html.escape(TEAM_NAMES.get(top_pick, top_pick))} lead the current frozen V4 board.</div></div>
              <div class="spot-prob">{top_prob:.1f}%<small>WIN CONFIDENCE</small></div>
            </div>''',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'''<div class="section-head"><div><div class="section-title">Full slate</div>
            <div class="section-sub">Ordered by V4 adjusted confidence • {len(provisional)} provisional • {risk_count} active risk flags</div></div></div>''',
            unsafe_allow_html=True,
        )

        filter_choice = st.radio(
            "Board filter",
            ["All games", "60%+ confidence", "Risk flags", "Provisional"],
            horizontal=True,
            label_visibility="collapsed",
        )
        board = pred
        if filter_choice == "60%+ confidence":
            board = pred[pred["v4_adjusted_confidence"] >= .60]
        elif filter_choice == "Risk flags":
            mask = pred.apply(
                lambda r: is_true(r.get("turnover_risk_flag", False))
                or is_true(r.get("early_down_risk_flag", False))
                or is_true(r.get("explosive_extreme", False)),
                axis=1,
            )
            board = pred[mask]
        elif filter_choice == "Provisional":
            board = pred[provisional_mask]

        if board.empty:
            st.info("No games match this filter.")
        else:
            for rank, (_, r) in enumerate(board.iterrows(), start=1):
                away, home, pick = str(r["away_team"]), str(r["home_team"]), str(r["v4_pick"])
                v4, core, v3 = float(r["v4_adjusted_confidence"]), float(r["v4_core_confidence"]), float(r["v3_confidence"])
                status = str(r.get("prediction_status", "EARLY_LOCK"))
                provisional_flag = status.startswith("PROVISIONAL")
                accent = TEAM_COLORS.get(pick, "#64748b")
                tier, tier_class = confidence_tier(v4)
                qb_note = r.get("qb_status_flag", "")

                badges = []
                badges.append('<span class="badge badge-prov">PROVISIONAL</span>' if provisional_flag else '<span class="badge badge-lock">LOCKED SNAPSHOT</span>')
                if is_true(r.get("explosive_extreme", False)):
                    badges.append('<span class="badge badge-warn">⚡ EXPLOSIVE SIGNAL</span>')
                if is_true(r.get("turnover_risk_flag", False)):
                    badges.append('<span class="badge badge-warn">↔ TURNOVER RISK</span>')
                if is_true(r.get("early_down_risk_flag", False)):
                    badges.append('<span class="badge badge-warn">⚠ EARLY-DOWN RISK</span>')
                if pd.notna(qb_note) and str(qb_note).strip():
                    badges.append('<span class="badge badge-warn">QB WATCH</span>')

                core_delta = (v4 - core) * 100
                layer_text = "Confidence layers: no adjustment" if abs(core_delta) < .05 else f"Confidence layers: {core_delta:+.1f} pts"
                pick_name = TEAM_NAMES.get(pick, pick)

                st.markdown(
                    f'''<div class="card" style="border-left-color:{accent}">
                      <div class="card-top"><div class="game-meta">#{rank} ON BOARD • {html.escape(str(r["game_id"]))}</div><div class="tier {tier_class}">{tier}</div></div>
                      <div class="match-row">{team_block(away)}<div class="at">@</div>{team_block(home, True)}</div>
                      <div class="pick-panel">
                        <div><div class="pick-label">B.P. SPORTS V4 PICK</div><div class="pick-name">{html.escape(pick)} • {html.escape(pick_name)}</div></div>
                        <div class="prob">{v4*100:.1f}%<span>ADJUSTED CONFIDENCE</span></div>
                      </div>
                      <div class="bar"><div class="fill" style="width:{v4*100:.1f}%"></div></div>
                      <div class="badges">{''.join(badges)}</div>
                      <div class="model-strip">
                        <div class="model-cell"><div class="m">V3 BASE</div><div class="v">{html.escape(str(r["v3_pick"]))} {v3*100:.1f}%</div></div>
                        <div class="model-cell"><div class="m">V4 CORE</div><div class="v">{core*100:.1f}%</div></div>
                        <div class="model-cell"><div class="m">V4 FINAL</div><div class="v">{v4*100:.1f}%</div></div>
                      </div>
                      <div class="layer-note">{html.escape(layer_text)}</div>
                    </div>''',
                    unsafe_allow_html=True,
                )

                with st.expander(f"WHY V4 LIKES {pick} • {away} @ {home}"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("V3", f"{v3*100:.1f}%")
                    c2.metric("V4 core", f"{core*100:.1f}%")
                    c3.metric("V4 final", f"{v4*100:.1f}%", f"{(v4-v3)*100:+.1f} vs V3")

                    notes = []
                    if is_true(r.get("explosive_extreme", False)):
                        notes.append("Explosive-play matchup reached the frozen model's extreme-signal threshold.")
                    if is_true(r.get("turnover_risk_flag", False)):
                        notes.append("Recent turnover matchup conflicts with the V4 side, so confidence is reduced instead of flipping the pick.")
                    if is_true(r.get("early_down_risk_flag", False)):
                        notes.append("Recent early-down efficiency is acting as a risk flag against the V4 side.")
                    if not notes:
                        notes.append("No secondary confidence layer materially changed the V4 core probability.")
                    for note in notes:
                        st.write("• " + note)

                    if pd.notna(qb_note) and str(qb_note).strip():
                        st.warning(str(qb_note))
                    if provisional_flag:
                        st.warning("Provisional: legitimate pregame information still needs to be refreshed before the official graded snapshot.")
                    else:
                        st.success("Pregame snapshot preserved. Once kickoff occurs, this prediction cannot be rewritten.")

        st.caption("B.P. Sports is a prediction model, not a guarantee. Market odds do not choose the model's winner.")

with t2:
    st.markdown('<div class="section-title">Model record</div><div class="section-sub">The forward ledger is the scoreboard that matters.</div>', unsafe_allow_html=True)
    live = tracking.get("v4_adjusted", {})
    games = int(live.get("games", 0) or 0)
    if games:
        wins = int(live.get("correct", 0) or 0)
        losses = games - wins
        st.markdown(
            f'''<div class="record-hero"><div class="record-label">2026 FROZEN V4 FORWARD RECORD</div>
            <div class="record-big">{wins}–{losses}</div><div class="section-sub">{live.get("accuracy",0)*100:.1f}% accuracy across {games} graded games</div></div>''',
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Accuracy", f"{live.get('accuracy',0)*100:.1f}%")
        c2.metric("Brier score", f"{live.get('brier',0):.4f}")
        c3.metric("Log loss", f"{live.get('log_loss',0):.4f}")
        v3_live = tracking.get("v3", {})
        if v3_live.get("games", 0):
            v3_wins = int(v3_live.get("correct", 0) or 0)
            v3_games = int(v3_live.get("games", 0) or 0)
            st.markdown(f'<div class="about-card"><div class="about-num">CHAMPION / CHALLENGER</div><div class="about-title">V4 vs V3</div><div class="about-copy">V4: {wins}–{losses} • {live.get("accuracy",0)*100:.1f}% • Brier {live.get("brier",0):.4f}<br>V3: {v3_wins}–{v3_games-v3_wins} • {v3_live.get("accuracy",0)*100:.1f}% • Brier {v3_live.get("brier",0):.4f}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '''<div class="record-hero"><div class="record-label">2026 FROZEN V4 FORWARD RECORD</div>
            <div class="record-big">0–0</div><div class="section-sub">Week 5 begins the prospective test. No games have been graded yet.</div></div>''',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-title" style="margin-top:24px">Historical development</div>', unsafe_allow_html=True)
    st.metric("Frozen V4 candidate", "65.02%", "1,279–688 • 2018–2025 reused sample")
    st.caption("This is a development result, not a promised future hit rate. The 2026 forward ledger is intentionally kept separate.")

with t3:
    st.markdown('<div class="section-title">Inside V4</div><div class="section-sub">What the model uses — and what it deliberately ignores.</div>', unsafe_allow_html=True)
    cards = [
        ("01", "Efficiency foundation", "Opponent-adjusted EPA, success rate, recent form, Elo/team strength, rest and home-field context form the base of the prediction engine."),
        ("02", "Quarterback layer", "V4 adds leakage-safe quarterback continuity, QB-change impact and prior quarterback quality without using post-kickoff information."),
        ("03", "Confidence intelligence", "Explosive plays can raise or lower confidence. Turnovers and early-down efficiency act conservatively as risk flags. These layers cannot flip the core winner."),
        ("04", "Market firewall", "Sportsbook and prediction-market prices do not choose the B.P. Sports winner. Market information belongs to a separate value-analysis layer."),
        ("05", "Immutable grading", "Pregame snapshots are timestamped and preserved. Once a game starts, the graded prediction is never rewritten with hindsight."),
    ]
    for num, title, copy in cards:
        st.markdown(f'<div class="about-card"><div class="about-num">{num}</div><div class="about-title">{html.escape(title)}</div><div class="about-copy">{html.escape(copy)}</div></div>', unsafe_allow_html=True)

    st.info("Pressure/sack proxies, third-down conversion rate, red-zone TD rate and special-teams proxies were tested but did not earn core V4 weight because they failed broader historical stability checks.")
