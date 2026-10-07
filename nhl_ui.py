"""Read-only presentation of the separate NHL research ledgers."""
UI_REVISION="mobile-layout-20261007"
from concurrent.futures import ThreadPoolExecutor
import csv
import html
import io
import json
import math
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st
from matchup_preview_ui import render_preview
from matchup_details_ui import details_button
from game_center_ui import filter_favorites,score_html,confidence_html,load_scores,context
from game_status import display_state

RESEARCH_URL = 'https://raw.githubusercontent.com/bp111301/bp-sports/nhl-v1-research/'
SNAPSHOT = Path(__file__).parent / 'data/nhl/dashboard_snapshot.json'
AUDIT = Path(__file__).parent / 'data/nhl/forecast_audit.json'
MODEL_NAMES = {
    'reference_control': 'Reference control',
    'decay2_logistic': 'Recency weighting',
    'linear_regulation_blend': 'Regulation blend',
}
TEAMS = dict(zip(
    ['ANA','BOS','BUF','CGY','CAR','CHI','COL','CBJ','DAL','DET','EDM','FLA','LAK','MIN','MTL','NSH','NJD','NYI','NYR','OTT','PHI','PIT','SJS','SEA','STL','TBL','TOR','UTA','VAN','VGK','WSH','WPG'],
    ['Ducks','Bruins','Sabres','Flames','Hurricanes','Blackhawks','Avalanche','Blue Jackets','Stars','Red Wings','Oilers','Panthers','Kings','Wild','Canadiens','Predators','Devils','Islanders','Rangers','Senators','Flyers','Penguins','Sharks','Kraken','Blues','Lightning','Maple Leafs','Mammoth','Canucks','Golden Knights','Capitals','Jets']))
COLORS = {'TOR':'#2656a1','DET':'#be2633','NSH':'#8e721a','BUF':'#244782','MIN':'#27533f','CAR':'#a42835','MTL':'#a52c43','NJD':'#a32732','NYR':'#28599c','NYI':'#ad5b21','SEA':'#285765','VGK':'#81734d','STL':'#264e96','CHI':'#a13235','LAK':'#404650','FLA':'#963643','WSH':'#ab3444','PIT':'#806d24','WPG':'#345477','COL':'#73334a','ANA':'#74523c','EDM':'#a15b28','UTA':'#466b7c'}

def escape(value):
    return html.escape(str(value), quote=True)

def audit_note(game_id,bundle):
    try:
        audit=json.loads(AUDIT.read_text())
        if audit['bundle_sha256']!=bundle:return None
        return audit.get('games',{}).get(str(int(game_id)))
    except (OSError,ValueError,KeyError,TypeError):return None

def ct(value):
    try:
        return pd.to_datetime(value, utc=True).tz_convert('America/Chicago').strftime('%a %b %d • %I:%M %p CT').replace(' 0', ' ')
    except (ValueError, TypeError):
        return 'Time unavailable'

def get_text(path):
    req=Request(RESEARCH_URL+path, headers={'User-Agent':'BP-Sports-Dashboard/1.0'})
    with urlopen(req, timeout=8) as response:
        data=response.read(16*1024*1024+1)
        if len(data)>16*1024*1024:raise ValueError('Research feed too large')
        return data.decode('utf-8')

@st.cache_data(ttl=120)
def load_dashboard():
    paths=['data/nhl/v2_research/prediction_ledger.csv','data/nhl/v2_research/summary.json','data/nhl/goalie_capture/observations.jsonl','data/nhl/goalie_capture/summary.json']
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            ledger,summary,goalies,goalie_summary=list(pool.map(get_text,paths))
        payload={'predictions':list(csv.DictReader(io.StringIO(ledger))), 'prediction_summary':json.loads(summary),
                 'goalies':[json.loads(line) for line in goalies.splitlines() if line.strip()], 'goalie_summary':json.loads(goalie_summary)}
        prepare_predictions(payload['predictions'])
        return payload,False
    except Exception:
        try:
            return json.loads(SNAPSHOT.read_text()),True
        except (OSError, ValueError):
            return {},True

def prepare_predictions(records):
    columns=['game_id','candidate','home_team','away_team','home_win_prob','start_time_utc','created_at_utc','status','actual_home_win']
    board=pd.DataFrame(records)
    if board.empty:return pd.DataFrame(columns=columns)
    if not set(columns).issubset(board.columns):raise ValueError('Incomplete NHL feed')
    board=board[board.candidate.isin(MODEL_NAMES) & board.status.isin(['pending','settled'])].copy()
    for col in ['start_time_utc','created_at_utc']:
        board[col]=pd.to_datetime(board[col], utc=True, errors='coerce')
    for col in ['home_win_prob','actual_home_win','game_id']:
        board[col]=pd.to_numeric(board[col], errors='coerce')
    board=board.dropna(subset=['game_id','home_team','away_team','home_win_prob','start_time_utc','created_at_utc'])
    board=board[board.home_win_prob.between(0,1) & board.created_at_utc.lt(board.start_time_utc)]
    board=board[(board.status!='settled') | board.actual_home_win.isin([0,1])]
    if board.duplicated(['game_id','candidate']).any():raise ValueError('Duplicate NHL prediction')
    board['favored_team']=board.home_team.where(board.home_win_prob.ge(.5),board.away_team)
    board['favored_prob']=board.home_win_prob.where(board.home_win_prob.ge(.5),1-board.home_win_prob)
    return board.sort_values(['start_time_utc','game_id'])

def latest_goalies(records, now):
    latest={}
    for r in records:
        try:
            captured=pd.to_datetime(r['captured_at_utc'],utc=True);start=pd.to_datetime(r['start_time_utc'],utc=True)
            if pd.isna(captured) or pd.isna(start) or captured>now or captured>=start:continue
            key=(int(r['game_id']),r['side'])
            if key not in latest or captured>pd.to_datetime(latest[key]['captured_at_utc'],utc=True):latest[key]=r
        except (ValueError, TypeError, KeyError):continue
    return latest

def team_block(team, home=False):
    dot=f'<div class="team-dot" style="background:{COLORS.get(team,"#315f9f")}">{escape(team)}</div>'
    text=f'<div><div class="team-abbr">{escape(team)}</div><div class="team-name">{escape(TEAMS.get(team,team))}</div></div>'
    return f'<div class="team-box{" home" if home else ""}">{text+dot if home else dot+text}</div>'

def goalie_text(report):
    if not report:return 'No pregame report captured'
    name=report.get('goalie_name') or 'Goalie unknown'
    status=report.get('status') or 'Unknown'
    if status=='Confirmed' and report.get('confirmed_eligible') is not True:status='Confirmation unverified'
    if status=='Unknown':status='Unconfirmed'
    return f'{name} • {status}'

def record_metrics(board):
    rows=[]
    for candidate,name in MODEL_NAMES.items():
        settled=board[(board.candidate==candidate) & (board.status=='settled')]
        if settled.empty:
            rows.append({'Model':name,'Games':0,'Accuracy':'—','Brier':'—','Log loss':'—'});continue
        p=settled.home_win_prob;y=settled.actual_home_win
        loss=-sum(float(a)*math.log(min(max(float(b),1e-15),1-1e-15))+(1-float(a))*math.log(min(max(1-float(b),1e-15),1-1e-15)) for a,b in zip(y,p))/len(y)
        rows.append({'Model':name,'Games':len(y),'Accuracy':f'{((p>=.5)==y).mean()*100:.2f}%','Brier':f'{((p-y)**2).mean():.4f}','Log loss':f'{loss:.4f}'})
    return pd.DataFrame(rows)

def render_nhl(now=None):
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.to_datetime(now,utc=True)
    data,saved=load_dashboard()
    st.markdown('''<style>.nhl-pill{background:#30281a;border-color:#584824;color:#efd17f}.nhl-goalies{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px;font-size:.72rem;color:#aeb8c7}.nhl-goalies div:last-child{text-align:right}.nhl-goalies small{display:block;color:#8d98a8;font-size:.59rem;margin-bottom:3px}[data-testid="stWidgetLabel"] p,[data-testid="stRadio"] label p{color:#d9e2ef!important}[data-testid="stAlert"] p{color:#e0e8f5!important}.st-key-nhl_refresh button{background:#172b46;color:#dbe9ff;border:1px solid #294b77}</style>
''' ,unsafe_allow_html=True)
    st.info('NHL is in prospective research. All three models are experimental; none has passed the release gate. Goalie reports are collected separately and do not change these predictions.')
    if not data:
        st.error('The NHL research feed is unavailable. Please try again later.');return
    if saved:st.warning('Live NHL data is unavailable. Showing a saved snapshot; check the capture times before using it.')
    try:board=prepare_predictions(data.get('predictions',[]))
    except ValueError:
        st.error('The NHL research feed could not be verified. No predictions are displayed.');return
    board=board[board.created_at_utc.le(now)]
    if board.empty:
        st.info('No valid pregame NHL predictions have been recorded yet.');return
    summary=data.get('prediction_summary',{});goalie_summary=data.get('goalie_summary',{})
    st.caption(f'Prediction ledger updated: {ct(summary.get("as_of_utc"))} • Goalie capture: {ct(goalie_summary.get("as_of_utc"))}')
    if goalie_summary.get('errors'):st.warning('Some goalie reports could not be collected or matched. Check the individual report statuses.')
    reports=latest_goalies(data.get('goalies',[]),now)
    n1,n2,n3=st.tabs(['RESEARCH BOARD','MODEL RECORD','THE MODEL'])
    with n1:
        left,right=st.columns([2,1])
        candidate=left.selectbox('Research model',list(MODEL_NAMES),format_func=MODEL_NAMES.get,key='nhl_candidate')
        view=right.selectbox('Games',['Today + upcoming','Upcoming','Awaiting results','Completed','All tracked'],key='nhl_view')
        selected=board[board.candidate==candidate].copy()
        upcoming=selected[(selected.status=='pending') & selected.start_time_utc.gt(now)]
        confirmed=sum(bool(reports.get((int(g),'home'),{}).get('confirmed_eligible')) and bool(reports.get((int(g),'away'),{}).get('confirmed_eligible')) for g in upcoming.game_id)
        st.markdown(f'''<div class="hero"><div class="eyebrow">2026–27 • PROSPECTIVE RESEARCH</div><div class="hero-title">The B.P. Sports NHL Board</div><div class="hero-copy">Follow the three fixed models on games predicted before puck drop. Compare their probabilities and track new results as they arrive.</div><div class="stat-grid"><div class="stat"><div class="stat-v">{len(upcoming)}</div><div class="stat-l">Upcoming games</div></div><div class="stat"><div class="stat-v">3</div><div class="stat-l">Models tracked</div></div><div class="stat"><div class="stat-v">{confirmed}</div><div class="stat-l">Both goalies confirmed</div></div><div class="stat"><div class="stat-v">{int((selected.status=='settled').sum())}</div><div class="stat-l">Graded games</div></div></div></div>''',unsafe_allow_html=True)
        query=st.text_input('Find an NHL team',placeholder='Search Red Wings, Maple Leafs, TOR…',key='nhl_search')
        if view=='Today + upcoming':
            today=now.tz_convert('America/Chicago').date()
            shown=selected[selected.start_time_utc.dt.tz_convert('America/Chicago').dt.date.eq(today) | ((selected.status=='pending') & selected.start_time_utc.gt(now))]
            st.caption('Today’s games stay visible after puck drop and after grading. Future games appear once a pregame prediction is saved. Times are Central.')
        elif view=='Upcoming':shown=upcoming
        elif view=='Awaiting results':shown=selected[(selected.status=='pending') & selected.start_time_utc.le(now)]
        elif view=='Completed':shown=selected[selected.status=='settled']
        else:shown=selected
        if query.strip():
            q=query.strip().lower()
            shown=shown[shown.apply(lambda r:any(q in str(t).lower() or q in TEAMS.get(str(t),'').lower() for t in [r.home_team,r.away_team]),axis=1)]
        shown=filter_favorites(shown,"NHL","nhl_my_teams")
        if shown.empty:st.info('No games match this view. New pregame predictions are collected daily.')
        for _,r in shown.iterrows():
            game_id=int(r.game_id);home=str(r.home_team);away=str(r.away_team);p=float(r.home_win_prob)
            status='Pregame' if r.start_time_utc>now and r.status=='pending' else 'Awaiting final' if r.status=='pending' else 'Win' if (p>=.5)==r.actual_home_win else 'Loss'
            if r.status=='pending':status=display_state(context('NHL',game_id,home,away),False,r.start_time_utc,now)
            result_class='tier-strong' if status=='Win' else 'tier-toss' if status=='Loss' else 'tier-solid' if status=='Pregame' else 'tier-lean'
            note=audit_note(game_id,r.get('bundle_sha256'))
            if note:st.warning(note['message'])
            comparisons=board[board.game_id==game_id].set_index('candidate')
            cells=''.join(f'<div class="model-cell"><div class="m">{escape(name)}</div><div class="v">{float(comparisons.loc[key,"home_win_prob"])*100:.1f}% {escape(home)}</div></div>' if key in comparisons.index else f'<div class="model-cell"><div class="m">{escape(name)}</div><div class="v">Not captured</div></div>' for key,name in MODEL_NAMES.items())
            st.markdown(f'''<div class="card" style="border-left-color:#6ea8fe"><div class="card-top"><div class="game-meta">{escape(ct(r.start_time_utc))}</div><div class="tier {result_class}">{escape(status.upper())}</div></div>{score_html("NHL",game_id,home,away,r.status=="settled",r.start_time_utc,now)}<div class="match-row">{team_block(away)}<div class="at">@</div>{team_block(home,True)}</div><div class="pick-panel"><div><div class="pick-label">{escape(MODEL_NAMES[candidate].upper())} • EXPERIMENTAL</div><div class="pick-name">{escape(r.favored_team)} favored</div></div><div class="prob">{r.favored_prob*100:.1f}%<span>MODEL WIN PROBABILITY</span></div></div>{confidence_html(r.favored_prob,"NHL",bool(note))}<div class="bar"><div class="fill" style="width:{r.favored_prob*100:.1f}%"></div></div><div class="model-strip">{cells}</div><div class="nhl-goalies"><div><small>{escape(away)} GOALIE REPORT</small>{escape(goalie_text(reports.get((game_id,'away'))))}</div><div><small>{escape(home)} GOALIE REPORT</small>{escape(goalie_text(reports.get((game_id,'home'))))}</div></div><div class="layer-note">Prediction recorded {escape(ct(r.created_at_utc))}. Goalie reports are separate from these model probabilities.</div></div>''',unsafe_allow_html=True)
            extras={'goalies':{side:reports.get((game_id,side)) for side in ['home','away']}}
            details_button('NHL',r,'details_nhl_'+candidate+'_'+str(game_id),MODEL_NAMES[candidate],extras=extras,now=now)
        st.caption('Win / Loss grades the saved pick. Results are checked about every 15 minutes after games begin. NHL probabilities remain experimental; the first pregame prediction stays saved.')
    with n2:
        st.markdown('<div class="section-title">Prospective NHL record</div><div class="section-sub">Only valid predictions captured before puck drop are graded here.</div>',unsafe_allow_html=True)
        metrics=record_metrics(board);st.dataframe(metrics,hide_index=True,use_container_width=True)
        if metrics.Games.sum()==0:st.info('No tracked games have been settled yet. Accuracy will appear after recorded games finish and the ledger refreshes.')
        st.caption('The models share a fixed training boundary through 2025–26. Early results are descriptive; there is no automatic promotion.')
        st.markdown('<div class="section-title" style="margin-top:24px">Historical research</div>',unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{'Model':'Original team-stat reference','Development accuracy':'61.34%','Decision':'Comparator'}, {'Model':'Recency weighting','Development accuracy':'61.70%','Decision':'Failed season-consistency requirement'}, {'Model':'Regulation blend','Development accuracy':'61.32%','Decision':'One fewer correct pick than reference'}]),hide_index=True,use_container_width=True)
        st.caption('Reused development seasons: 2021–22 through 2024–25, 5,248 games. These figures are not live performance.')
        st.warning('Original frozen NHL V1 reached 53.43% on the excluded 2025–26 season (1,312 games) and failed its release gate. That season is now training data for the new watchlist; it is not another independent test.')
    with n3:
        st.markdown('<div class="section-title">Inside NHL research</div>',unsafe_allow_html=True)
        cards=[('01','Reference control','Elo, recent results, scoring, rest and shifted 20-game team statistics provide the common reference.'),('02','Recency weighting','The same logistic model gives newer training seasons more weight, with a fixed two-season half-life.'),('03','Regulation blend','A fixed 50/50 blend combines the reference with regulation win/tie/loss probabilities. Extra-time ties use a fixed 50% home-win chance.'),('04','Pregame record','Model weights stay fixed. Each game’s first prediction is preserved; final results only grade recorded predictions.'),('05','Starting-goalie experiment','Confirmed starter reports are archived before games. A separate paired experiment compares team-only, inferred-starter and confirmed-starter probabilities on the same games. Its results are on the Overview research tab; these board probabilities remain unchanged.')]
        for num,title,copy in cards:
            st.markdown(f'<div class="about-card"><div class="about-num">{num}</div><div class="about-title">{escape(title)}</div><div class="about-copy">{escape(copy)}</div></div>',unsafe_allow_html=True)
