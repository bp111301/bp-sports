import importlib
import json
import html
import io
from urllib.request import Request, urlopen
import streamlit as st
import pandas as pd
from navigation_ui import request_top, render_top_anchor, render_scroll_reset
from matchup_preview_ui import render_preview
from matchup_details_ui import details_button
from cfb_board_ui import dated_board, date_choices, games_on_date, date_label
import game_center_ui
if getattr(game_center_ui,"UI_REVISION",None)!="mobile-layout-20261007":importlib.reload(game_center_ui)
from game_center_ui import render_preferences, filter_favorites, score_html, confidence_html, render_score_refresh, render_header, render_host_chrome

st.set_page_config(
    page_title="B.P. Sports",
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
header[data-testid="stHeader"]{display:none}
.block-container{max-width:1160px;padding-top:1rem;padding-bottom:5rem}
.st-key-bp_sport{position:sticky;top:0;z-index:20;background:#0b1019;padding:8px 0;border-bottom:1px solid #27364c}
.st-key-bp_sport [role="radiogroup"]{gap:6px;flex-wrap:wrap}
.st-key-bp_sport label{border:1px solid #30425c;border-radius:10px;padding:8px 12px;background:#101c2d}
.st-key-bp_sport label:has(input:checked){background:#234673;border-color:#75a9f3}
.st-key-bp_sport label p{font-weight:800!important;color:#d9e2ef!important}
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
 .block-container{padding:1rem 12px 4rem}
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

def current_feed_text(name):
    # Data-only bot commits can leave Community Cloud's checkout behind.
    # Read changing CFB feeds from the same source as the live Overview.
    with urlopen(Request(
        "https://raw.githubusercontent.com/bp111301/bp-sports/main/" + name,
        headers={"User-Agent": "BP-Sports-CFB-Board/1.0"},
    ), timeout=8) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Feed too large")
    return raw.decode("utf-8")


@st.cache_data(ttl=60)
def load_csv(name):
    if name.startswith("data/cfb/"):
        try:
            return pd.read_csv(io.StringIO(current_feed_text(name)))
        except Exception:
            pass
    try:
        return pd.read_csv(name)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_json(name):
    if name.startswith("data/cfb/"):
        try:
            return json.loads(current_feed_text(name))
        except Exception:
            pass
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

render_top_anchor()
render_host_chrome()
render_header()
st.markdown('<div style="font-size:.64rem;color:#8d98a8;font-weight:900;letter-spacing:.11em;margin-bottom:4px">SPORT</div>', unsafe_allow_html=True)
sport = st.radio("Sport", ["Overview", "NFL", "CFB", "NHL", "NBA"], horizontal=True, label_visibility="collapsed", key="bp_sport", on_change=request_top)

def current_ui(module):
    # Streamlit can retain imported modules during a deployment rerun. Reload once per UI revision.
    if getattr(module,"UI_REVISION",None)!="mobile-layout-20261007":module=importlib.reload(module)
    return module

with st.container(key='bp_toolbar'):
    refresh,options=st.columns([1,1],gap='small')
    with refresh:render_score_refresh()
    with options:render_preferences(TEAM_NAMES)

if sport == "Overview":
    import overview_ui
    current_ui(overview_ui).render_overview()

elif sport == "NFL":
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
    
            nfl_ledger = load_csv("data/ledger/prediction_ledger.csv")
            nfl_settled = set(nfl_ledger.loc[nfl_ledger.settlement_status.isin(["final","tie"]),"game_id"]) if "settlement_status" in nfl_ledger else set()
            board = filter_favorites(board, "NFL", "nfl_my_teams")
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
                          {score_html("NFL",r["game_id"],home,away,r["game_id"] in nfl_settled)}
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
                          {confidence_html(v4,"NFL")}
                          <div class="layer-note">{html.escape(layer_text)}</div>
                        </div>''',
                        unsafe_allow_html=True,
                    )
    
                    detail_row=r.to_dict()
                    if r['game_id'] in nfl_settled:
                        result_row=nfl_ledger[nfl_ledger.game_id.eq(r['game_id'])].iloc[0]
                        detail_row.update(actual_home_score=result_row.actual_home_score,actual_away_score=result_row.actual_away_score)
                    details_button('NFL',detail_row,'details_nfl_'+str(r['game_id']),settled=r['game_id'] in nfl_settled)

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
    

elif sport == "CFB":
    cfb_pred = load_csv("data/cfb/current/predictions.csv")
    cfb_meta = load_json("data/cfb/current/metadata.json")
    cfb_holdout = load_json("research/cfb/results/holdout_2026.json")
    cfb_live_record = load_json("data/cfb/ledger/summary.json")

    def cfb_initials(name):
        words = [w for w in str(name).replace("(", " ").replace(")", " ").split() if w]
        if len(words) == 1:
            return words[0][:3].upper()
        return "".join(w[0] for w in words[:3]).upper()

    def cfb_team_block(team, home=False):
        safe = html.escape(str(team))
        abbr = html.escape(cfb_initials(team))
        dot = f'<div class="team-dot" style="background:#315f9f">{abbr}</div>'
        txt = f'<div><div class="team-abbr">{abbr}</div><div class="team-name">{safe}</div></div>'
        return f'<div class="team-box{" home" if home else ""}">{txt + dot if home else dot + txt}</div>'

    def kickoff_ct(value):
        try:
            dt = pd.to_datetime(value, utc=True).tz_convert("America/Chicago")
            return dt.strftime("%a %b %d • %I:%M %p CT").replace(" 0", " ")
        except Exception:
            return "Kickoff TBD"

    generated = str(cfb_meta.get("generated_at_utc", ""))
    cfb_fresh = "AUTOMATED CFB V1"
    if generated:
        try:
            cfb_fresh = f"UPDATED {pd.to_datetime(generated).strftime('%b %d • %I:%M %p UTC').upper()}"
        except Exception:
            pass


    c1, c2, c3 = st.tabs(["PREDICTIONS", "MODEL RECORD", "THE MODEL"])

    with c1:
        if cfb_pred.empty:
            st.error("The current CFB prediction feed is unavailable.")
        else:
            ledger = load_csv("data/cfb/ledger/prediction_ledger.csv")
            board = pd.concat([cfb_pred,ledger],ignore_index=True).drop_duplicates("game_id")
            if "correct" in ledger:
                results=ledger.drop_duplicates("game_id").set_index("game_id")["correct"]
                board["correct"]=board["game_id"].map(results)
            board["_settled"] = board.get("correct",pd.Series(index=board.index,dtype=float)).notna()
            board["confidence"] = pd.to_numeric(board["confidence"], errors="coerce")
            board["home_win_prob"] = pd.to_numeric(board["home_win_prob"], errors="coerce")
            board["week"] = pd.to_numeric(board["week"], errors="coerce")
            board = board.dropna(subset=["confidence"]).sort_values(
                ["confidence", "kickoff_utc"], ascending=[False, True]
            ).reset_index(drop=True)

            weeks = sorted(board["week"].dropna().astype(int).unique().tolist())
            if not weeks:
                week_text = "CURRENT"
            elif len(weeks) == 1:
                week_text = str(weeks[0])
            else:
                week_text = f"{weeks[0]}–{weeks[-1]}"

            avg_conf = board["confidence"].mean() * 100
            strong_count = int((board["confidence"] >= .70).sum())
            solid_count = int((board["confidence"] >= .60).sum())

            st.markdown(
                f'''<div class="hero">
                  <div class="eyebrow">2026 • CFB WEEKS {week_text} • FROZEN V1</div>
                  <div class="hero-title">The B.P. Sports College Football Board</div>
                  <div class="hero-copy">CFB V1 ranks the upcoming slate with a market-free ensemble built from team efficiency, Elo, talent, returning production and a dynamic early-season prior. Every displayed pick is a timestamped pregame snapshot.</div>
                  <div class="stat-grid">
                    <div class="stat"><div class="stat-v">{len(board)}</div><div class="stat-l">Games tracked</div></div>
                    <div class="stat"><div class="stat-v">{strong_count}</div><div class="stat-l">70%+ picks</div></div>
                    <div class="stat"><div class="stat-v">{solid_count}</div><div class="stat-l">60%+ picks</div></div>
                    <div class="stat"><div class="stat-v">{avg_conf:.1f}%</div><div class="stat-l">Avg confidence</div></div>
                  </div>
                </div>''',
                unsafe_allow_html=True,
            )

            top = board.iloc[0]
            top_pick = str(top["predicted_winner"])
            top_prob = float(top["confidence"]) * 100
            st.markdown(
                f'''<div class="spotlight">
                  <div><div class="spot-title">B.P. TOP CFB CONFIDENCE</div>
                  <div class="spot-match">{html.escape(str(top["away_team"]))} @ {html.escape(str(top["home_team"]))} → {html.escape(top_pick)}</div>
                  <div class="spot-note">Frozen CFB V1's highest-confidence game on the current board.</div></div>
                  <div class="spot-prob">{top_prob:.1f}%<small>WIN CONFIDENCE</small></div>
                </div>''',
                unsafe_allow_html=True,
            )

            st.markdown(
                '<div class="section-head"><div><div class="section-title">CFB games by date</div>'
                '<div class="section-sub">Choose a date. Games are ordered by kickoff time in Central time.</div></div></div>',
                unsafe_allow_html=True,
            )
            left, right = st.columns([2, 1])
            query = left.text_input(
                "Find a CFB team",
                placeholder="Search Texas Tech, Alabama, Oregon…",
                label_visibility="collapsed",
            )
            confidence_filter = right.selectbox(
                "CFB confidence filter",
                ["All games", "70%+", "60%+", "Close calls <55%"],
                label_visibility="collapsed",
            )

            dated = dated_board(board, game_center_ui.load_scores())
            dates, default_date = date_choices(dated)
            if st.session_state.get('cfb_games_view', default_date) not in dates:
                st.session_state['cfb_games_view'] = default_date
            game_date = st.selectbox("CFB game date (Central time)", dates, index=dates.index(default_date), format_func=date_label, key="cfb_games_view")
            shown = games_on_date(dated, game_date)
            shown = filter_favorites(shown,"CFB","cfb_my_teams")
            if query.strip():
                q = query.strip().lower()
                shown = shown[
                    shown.apply(
                        lambda r: q in str(r["away_team"]).lower()
                        or q in str(r["home_team"]).lower(),
                        axis=1,
                    )
                ]
            if confidence_filter == "70%+":
                shown = shown[shown["confidence"] >= .70]
            elif confidence_filter == "60%+":
                shown = shown[shown["confidence"] >= .60]
            elif confidence_filter == "Close calls <55%":
                shown = shown[shown["confidence"] < .55]

            if shown.empty:
                st.info("No games match this filter.")
            else:
                last_date = None
                for rank, (_, r) in enumerate(shown.iterrows(), start=1):
                    day = r['_game_date'] if pd.notna(r['_game_date']) else 'Kickoff TBD'
                    if day != last_date:
                        st.markdown('### '+date_label(day))
                        last_date = day
                    away = str(r["away_team"])
                    home = str(r["home_team"])
                    pick = str(r["predicted_winner"])
                    conf = float(r["confidence"])
                    home_prob = float(r["home_win_prob"])
                    away_prob = 1 - home_prob
                    tier, tier_class = confidence_tier(conf)
                    accent = "#44d17a" if conf >= .70 else "#6ea8fe" if conf >= .60 else "#f5c451" if conf >= .55 else "#ff6b7a"
                    kickoff = kickoff_ct(r['_display_kickoff']) if pd.notna(r['_display_kickoff']) else 'Kickoff TBD'
                    week = int(r["week"]) if pd.notna(r["week"]) else "—"

                    st.markdown(
                        f'''<div class="card" style="border-left-color:{accent}">
                          <div class="card-top"><div class="game-meta">WEEK {week} • {html.escape(kickoff)}</div><div class="tier {tier_class}">{tier}</div></div>
                          {score_html("CFB",r["game_id"],home,away,bool(r["_settled"]),r['_display_kickoff'])}
                          <div class="match-row">{cfb_team_block(away)}<div class="at">@</div>{cfb_team_block(home, True)}</div>
                          <div class="pick-panel">
                            <div><div class="pick-label">B.P. SPORTS CFB V1 PICK</div><div class="pick-name">{html.escape(pick)}</div></div>
                            <div class="prob">{conf*100:.1f}%<span>WIN CONFIDENCE</span></div>
                          </div>
                          <div class="bar"><div class="fill" style="width:{conf*100:.1f}%"></div></div>
                          <div class="badges"><span class="badge badge-lock">PREGAME SNAPSHOT</span><span class="badge">MARKET-FREE PICK</span></div>
                          <div class="model-strip">
                            <div class="model-cell"><div class="m">AWAY WIN</div><div class="v">{away_prob*100:.1f}%</div></div>
                            <div class="model-cell"><div class="m">HOME WIN</div><div class="v">{home_prob*100:.1f}%</div></div>
                            <div class="model-cell"><div class="m">MODEL</div><div class="v">CFB V1</div></div>
                          </div>
                          {confidence_html(conf,"CFB")}
                          <div class="layer-note">Snapshot ID: {html.escape(str(r.get("prediction_id", "")))}</div>
                        </div>''',
                        unsafe_allow_html=True,
                    )

                    details_button('CFB',r,'details_cfb_'+str(r['game_id']),settled=bool(r['_settled']))

            st.caption(
                "B.P. Sports CFB V1 is a probability model, not a guarantee. "
                "Betting-market prices do not choose the winner."
            )

    with c2:
        st.markdown(
            '<div class="section-title">CFB model record</div>'
            '<div class="section-sub">Historical development, untouched 2026 diagnostic, and prospective tracking are kept separate.</div>',
            unsafe_allow_html=True,
        )
        if cfb_live_record:
            graded = int(cfb_live_record.get("settled_games", 0))
            wins = int(cfb_live_record.get("wins", 0))
            st.markdown(f'<div class="record-hero"><div class="record-label">CFB V1 • OFFICIAL PROSPECTIVE RECORD</div><div class="record-big">{wins}–{graded-wins}</div><div class="section-sub">{graded} graded games • {int(cfb_live_record.get("pending_games", 0))} pending snapshots</div></div>', unsafe_allow_html=True)
            st.caption("Confirmed finals are checked every 15 minutes. Pending games never count as wins or losses; original pregame picks stay fixed.")
        else:
            st.info("The CFB prospective record is unavailable. Historical results below are separate.")
        hold = cfb_holdout.get("overall", {})
        if hold:
            st.markdown(
                f'''<div class="record-hero">
                  <div class="record-label">2026 UNTOUCHED DIAGNOSTIC • PRE-FREEZE GAMES</div>
                  <div class="record-big">{hold.get("accuracy",0)*100:.2f}%</div>
                  <div class="section-sub">{int(hold.get("games",0))} completed games • frozen before these results were opened</div>
                </div>''',
                unsafe_allow_html=True,
            )
            r1, r2, r3 = st.columns(3)
            r1.metric("Accuracy", f'{hold.get("accuracy",0)*100:.2f}%')
            r2.metric("Brier score", f'{hold.get("brier",0):.4f}')
            r3.metric("Log loss", f'{hold.get("log_loss",0):.4f}')
            st.caption(
                "This is an untouched diagnostic, not a prospective record. "
                "These completed games cannot be used to change CFB V1."
            )

        st.markdown(
            '<div class="section-title" style="margin-top:24px">Historical development</div>',
            unsafe_allow_html=True,
        )
        d1, d2, d3 = st.columns(3)
        d1.metric("Walk-forward accuracy", "72.74%", "5,733 games")
        d2.metric("Brier score", "0.1773")
        d3.metric("Log loss", "0.5280")
        st.markdown(
            '''<div class="about-card"><div class="about-num">PROSPECTIVE LEDGER</div>
            <div class="about-title">Started October 6, 2026</div>
            <div class="about-copy">The live CFB board now writes immutable pregame snapshots. Those games become the clean forward record used to judge whether CFB V1 holds up in the real world.</div></div>''',
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            '<div class="section-title">Inside CFB V1</div>'
            '<div class="section-sub">A separate college-football model — not an NFL model stretched onto college games.</div>',
            unsafe_allow_html=True,
        )
        cfb_cards = [
            ("01", "25% context model", "Elo, home field, conference-game status, efficiency, opponent strength, talent, returning production and coaching continuity."),
            ("02", "75% dynamic-prior model", "A seven-week transition blends prior-season strength into current-season EPA and success-rate information, reducing early-season noise."),
            ("03", "Walk-forward training", "Every historical test season is predicted using only earlier seasons. The 2018–2025 tournament covered 5,733 held-out games."),
            ("04", "Market firewall", "Spreads, totals and prediction-market prices are excluded from winner selection. They can be compared later without contaminating the pick."),
            ("05", "Frozen + immutable", "CFB V1 was frozen before the 2026 diagnostic was opened. Live pregame snapshots are preserved and model changes require CFB V2."),
        ]
        for num, title, copy in cfb_cards:
            st.markdown(
                f'<div class="about-card"><div class="about-num">{num}</div>'
                f'<div class="about-title">{html.escape(title)}</div>'
                f'<div class="about-copy">{html.escape(copy)}</div></div>',
                unsafe_allow_html=True,
            )
        st.info(
            "A tested QB layer was deferred from CFB V1 because it did not add meaningful historical "
            "probability quality. It can be revisited in CFB V2 with better player-availability data."
        )

elif sport == "NHL":
    import nhl_ui
    current_ui(nhl_ui).render_nhl()

elif sport == "NBA":
    import nba_ui
    current_ui(nba_ui).render_nba()

render_scroll_reset()
