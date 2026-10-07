"""Read-only NBA presentation; historical scores never enter the live record."""
from concurrent.futures import ThreadPoolExecutor
import html
import json
import math
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import pandas as pd
import streamlit as st
from matchup_preview_ui import render_preview

RESEARCH_URL='https://raw.githubusercontent.com/bp111301/bp-sports/nba-v1-research/'
SNAPSHOT=Path(__file__).parent/'data/nba/dashboard_snapshot.json'
TEAMS={'ATL':'Hawks','BOS':'Celtics','BKN':'Nets','BRK':'Nets','CHA':'Hornets','CHI':'Bulls','CLE':'Cavaliers','DAL':'Mavericks','DEN':'Nuggets','DET':'Pistons','GS':'Warriors','GSW':'Warriors','HOU':'Rockets','IND':'Pacers','LAC':'Clippers','LAL':'Lakers','MEM':'Grizzlies','MIA':'Heat','MIL':'Bucks','MIN':'Timberwolves','NO':'Pelicans','NOP':'Pelicans','NY':'Knicks','NYK':'Knicks','OKC':'Thunder','ORL':'Magic','PHI':'76ers','PHX':'Suns','POR':'Trail Blazers','SAC':'Kings','SA':'Spurs','SAS':'Spurs','TOR':'Raptors','UTA':'Jazz','UTAH':'Jazz','WSH':'Wizards','WAS':'Wizards'}

def escape(value):return html.escape(str(value),quote=True)

def get_json(path):
    with urlopen(Request(RESEARCH_URL+path,headers={'User-Agent':'BP-Sports-Dashboard/1.0'}),timeout=8) as response:
        data=response.read(2*1024*1024+1)
        if len(data)>2*1024*1024:raise ValueError('NBA feed too large')
        return json.loads(data)

def get_prospective():
    try:return get_json('data/nba/prospective/dashboard.json')
    except HTTPError as e:
        if e.code==404:return {'feed_status':'not_enabled','predictions':[]}
        return {'feed_status':'unavailable','predictions':[]}
    except Exception:return {'feed_status':'unavailable','predictions':[]}

def validate_history(data):
    manifest=data['manifest'];evaluation=data['evaluation'];development=data['development']
    if manifest['bundle_sha256']!=evaluation['bundle_sha256'] or evaluation['selected']!=manifest['selected']:
        raise ValueError('NBA model identity mismatch')
    if evaluation['season']!=2026 or evaluation.get('weights_retrained') is not False:
        raise ValueError('Invalid excluded-season record')
    if evaluation.get('gate_passed') is not True:
        raise ValueError('NBA historical release gate is not passed')
    for result in (evaluation['metrics']['selected'],development['pooled']['team_logistic']):
        games=int(result['games']);correct=int(result['correct']);accuracy=float(result['accuracy'])
        if games<=0 or not 0<=correct<=games or not math.isfinite(accuracy) or abs(accuracy-correct/games)>1e-8:
            raise ValueError('Invalid historical metrics')
    return data

@st.cache_data(ttl=300)
def load_dashboard():
    paths=['model/nba/v1/manifest.json','research/nba/results/excluded_season_evaluation.json','research/nba/results/baseline_summary.json']
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending=pool.submit(get_prospective)
            manifest,evaluation,development=list(pool.map(get_json,paths))
            prospective=pending.result()
        return validate_history(dict(manifest=manifest,evaluation=evaluation,development=development,prospective=prospective)),False
    except Exception:
        try:
            data=validate_history(json.loads(SNAPSHOT.read_text()))
            data['prospective']={'feed_status':'unavailable','predictions':[]}
            return data,True
        except (OSError,ValueError,KeyError,TypeError):return {},True

def prepare_predictions(records,now):
    cols=['game_id','season','season_type','home_team','away_team','home_win_prob','start_time_utc','created_at_utc','status','actual_home_win']
    board=pd.DataFrame(records)
    if board.empty:return pd.DataFrame(columns=cols)
    if not set(cols).issubset(board):raise ValueError('Incomplete NBA prospective feed')
    for col in ('season','season_type','home_win_prob','actual_home_win'):
        board[col]=pd.to_numeric(board[col],errors='coerce')
    for col in ('start_time_utc','created_at_utc'):
        board[col]=pd.to_datetime(board[col],utc=True,errors='coerce')
    board=board.dropna(subset=['game_id','home_team','away_team','home_win_prob','start_time_utc','created_at_utc'])
    board=board[(board.season==2027)&(board.season_type==2)&board.home_win_prob.between(0,1)&board.status.isin(['pending','settled'])&board.created_at_utc.lt(board.start_time_utc)&board.created_at_utc.le(now)]
    board=board[(board.status!='settled')|board.actual_home_win.isin([0,1])]
    board=board[(board.status!='settled')|board.start_time_utc.le(now)]
    if board.game_id.duplicated().any():raise ValueError('Duplicate NBA forecasts')
    return board.sort_values(['start_time_utc','game_id'])

def live_record(board):
    settled=board[board.status=='settled']
    games=len(settled);wins=int(((settled.home_win_prob>=.5)==settled.actual_home_win).sum()) if games else 0
    return games,wins,games-wins

def render_nba(now=None):
    now=pd.Timestamp.now(tz='UTC') if now is None else pd.to_datetime(now,utc=True)
    if st.button('Refresh NBA data',key='nba_refresh'):load_dashboard.clear()
    data,saved=load_dashboard()
    st.markdown('''<style>
.nba-pill{background:#302117;border-color:#805330;color:#ffc68e}.nba-hero{background:radial-gradient(ellipse at 100% 0,rgba(212,124,44,.19),transparent 60%),linear-gradient(135deg,#1d202a,#10151e)}.nba-hero .eyebrow{color:#f7ad68}.nba-ready{border-left-color:#edaa65}.nba-ready .about-num{color:#f7ad68}.nba-statuses{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 2px}.nba-statuses span{padding:7px 11px;background:#17202c;border:1px solid #354252;border-radius:8px;color:#c5d3e4;font-size:.72rem}.nba-statuses span:last-child{background:#30241a;border-color:#6b4b2e;color:#efbd8c}.nba-record-tag{font-size:.68rem;color:#f7ad68;font-weight:900;letter-spacing:.12em}.st-key-nba_refresh button{background:#30241a;color:#ffd2aa;border:1px solid #765030}[data-testid="stWidgetLabel"] p,[data-testid="stRadio"] label p{color:#d9e2ef!important}[data-testid="stAlert"] p{color:#e0e8f5!important}
[data-testid="stTabs"] [role="tab"] p{color:#b8c5d8!important}[data-testid="stTabs"] [role="tab"][aria-selected="true"] p{color:#ffc68e!important}.nba-table-wrap{overflow-x:auto;border:1px solid #2c3747;border-radius:14px;margin:12px 0}.nba-table{width:100%;border-collapse:collapse;font-size:.78rem;background:#111823;color:#dce5f2}.nba-table th{text-align:left;padding:13px 15px;color:#a3b1c6;background:#172131;font-size:.66rem;letter-spacing:.06em}.nba-table td{padding:13px 15px;border-top:1px solid #27303d;white-space:nowrap}.nba-table tbody tr:first-child{color:#ffd2aa;background:#201e1d}
</style>
<div class="bp-nav"><div class="bp-logo"><div class="bp-mark">BP</div><div><div class="bp-wordmark">B.P. <span>SPORTS</span></div><div class="bp-kicker">INDEPENDENT BASKETBALL INTELLIGENCE</div></div></div><div class="live-pill nba-pill">NBA V1 • FROZEN</div></div>''',unsafe_allow_html=True)
    if not data:st.error('The NBA model record is unavailable. Please try again later.');return
    if saved:st.warning('Live NBA data is unavailable. Showing a saved historical snapshot; the live record is unavailable.')
    manifest=data['manifest'];evaluation=data['evaluation'];history=evaluation['metrics']['selected'];development=data['development']['pooled']['team_logistic']
    feed=data.get('prospective',{});available=feed.get('feed_status')=='enabled' and not saved
    try:board=prepare_predictions(feed.get('predictions',[]) if available else [],now)
    except ValueError:
        st.warning('The NBA forecast feed could not be verified. Live predictions and grading are unavailable.')
        board=prepare_predictions([],now);available=False
    games,wins,losses=live_record(board)
    tabs=st.tabs(['PREDICTIONS','MODEL RECORD','THE MODEL'])
    with tabs[0]:
        live_text=f'{wins}–{losses}' if available or feed.get('feed_status')=='not_enabled' else '—'
        st.markdown(f'''<div class="hero nba-hero"><div class="eyebrow">2026–27 • REGULAR SEASON • NBA V1</div><div class="hero-title">The B.P. Sports NBA Board</div><div class="hero-copy">A frozen team model built on efficiency, recent form, rest and home-court context. Pregame forecasts and their live results belong here; preseason games stay outside the official record.</div><div class="stat-grid"><div class="stat"><div class="stat-v">{live_text}</div><div class="stat-l">Official live record</div></div><div class="stat"><div class="stat-v">{games if available else '0' if feed.get('feed_status')=='not_enabled' else '—'}</div><div class="stat-l">Live games graded</div></div><div class="stat"><div class="stat-v">{history['accuracy']*100:.2f}%</div><div class="stat-l">2025–26 historical test</div></div><div class="stat"><div class="stat-v">Frozen V1</div><div class="stat-l">Model status</div></div></div></div>''',unsafe_allow_html=True)
        if not available:
            unavailable=feed.get('feed_status')=='unavailable'
            title='Live forecast feed unavailable' if unavailable else 'Waiting for the first pregame slate'
            copy='Current forecasts and the live record could not be verified. The historical evaluation is shown separately below.' if unavailable else 'The model has passed its reserved-season evaluation. The regular-season forecast feed has not been enabled yet. Once enabled, this board will display timestamped picks, confidence and completed results.'
            status='Live feed: unavailable' if unavailable else 'Live feed: awaiting activation'
            st.markdown(f'<div class="card nba-ready"><div class="nba-record-tag">READY FOR THE REGULAR SEASON</div><div class="about-title">{title}</div><div class="about-copy">{copy}</div><div class="nba-statuses"><span>✓ Model frozen</span><span>✓ Historical gate passed</span><span>{status}</span></div></div>',unsafe_allow_html=True)
            if feed.get('feed_status')=='unavailable':st.warning('The prospective feed is unavailable. Its live record cannot be confirmed.')
        else:
            st.caption('Live feed active • Regular-season forecasts lock within 36 hours of tipoff • Final results checked about every 15 minutes')
            if feed.get('prediction_blocked_reason'):
                st.warning('New forecasts are waiting for complete, verified results from previous games. Saved forecasts remain locked.')
            view=st.selectbox('Games',['Upcoming','Awaiting results','Completed','All tracked'],key='nba_view')
            search=st.text_input('Search NBA teams',placeholder='Team or abbreviation',key='nba_search').strip().lower()
            selected=board
            if view=='Upcoming':selected=selected[(selected.status=='pending')&selected.start_time_utc.gt(now)]
            elif view=='Awaiting results':selected=selected[(selected.status=='pending')&selected.start_time_utc.le(now)]
            elif view=='Completed':selected=selected[selected.status=='settled']
            if search:selected=selected[selected.apply(lambda r:search in ' '.join([str(r.home_team),str(r.away_team),TEAMS.get(r.home_team,''),TEAMS.get(r.away_team,'')]).lower(),axis=1)]
            if selected.empty:st.info('Collection is active. Picks will appear within 36 hours of the first regular-season games; preseason games are excluded.' if board.empty else 'No NBA forecasts match this view.')
            for r in selected.itertuples():
                home=float(r.home_win_prob);pick=r.home_team if home>=.5 else r.away_team;prob=max(home,1-home)
                time=r.start_time_utc.tz_convert('America/Chicago').strftime('%a %b %d • %I:%M %p CT')
                status='Awaiting final result' if r.status=='pending' and r.start_time_utc<=now else 'Pregame snapshot' if r.status=='pending' else 'Correct' if (home>=.5)==r.actual_home_win else 'Incorrect'
                st.markdown(f'<div class="card nba-ready"><div class="game-meta">{escape(time)} • {escape(status)}</div><div class="spot-match">{escape(r.away_team)} @ {escape(r.home_team)}</div><div class="pick-panel"><div><div class="pick-label">NBA V1 PICK</div><div class="pick-name">{escape(pick)} • {escape(TEAMS.get(pick,pick))}</div></div><div class="prob">{prob*100:.1f}%<span>WIN PROBABILITY</span></div></div></div>',unsafe_allow_html=True)
                with st.expander(f'Forecast details • {r.away_team} @ {r.home_team}'):
                    render_preview('NBA',r._asdict())
                    st.write(f'Home win probability: {home*100:.2f}%')
                    st.caption(f'Saved before tipoff: {r.created_at_utc.tz_convert("America/Chicago").strftime("%b %d, %Y %I:%M %p CT")}')
        st.caption('Historical accuracy is evidence from past games, not a promised future hit rate.')
    with tabs[1]:
        st.markdown('<div class="section-title">Official live record</div><div class="section-sub">2026–27 regular season • forecasts saved before tipoff only</div>',unsafe_allow_html=True)
        if available or feed.get('feed_status')=='not_enabled':
            st.markdown(f'<div class="record-hero"><div class="record-label">NBA V1 PROSPECTIVE RECORD</div><div class="record-big">{wins}–{losses}</div><div class="section-sub">{games} graded live games • historical test games are excluded</div></div>',unsafe_allow_html=True)
        else:st.info('The official live record is unavailable until the prospective feed can be verified.')
        if games:st.metric('Live accuracy',f'{wins/games*100:.2f}%')
        st.markdown('<div class="section-title" style="margin-top:24px">Reserved-season evaluation</div><div class="section-sub">2025–26 regular season • model frozen before this season was opened</div>',unsafe_allow_html=True)
        st.markdown(f'<div class="spotlight"><div><div class="spot-title">HISTORICAL TEST • {history["games"]:,} GAMES</div><div class="spot-match">{history["correct"]} correct · {history["games"]-history["correct"]} incorrect</div><div class="spot-note">All preregistered historical gate checks passed.</div></div><div class="spot-prob">{history["accuracy"]*100:.2f}%<small>HISTORICAL ACCURACY</small></div></div>',unsafe_allow_html=True)
        comparison=[]
        for key,name in [('selected','Frozen NBA V1'),('elo','Fixed Elo'),('home_frequency','Home-frequency control')]:
            m=evaluation['metrics'][key];comparison.append({'Model':name,'Games':m['games'],'Accuracy':f'{m["accuracy"]*100:.2f}%','Brier':f'{m["brier"]:.4f}','Log loss':f'{m["log_loss"]:.4f}'})
        columns=['Model','Games','Accuracy','Brier','Log loss']
        headers=''.join(f'<th>{escape(c)}</th>' for c in columns)
        rows=''.join('<tr>'+''.join(f'<td>{escape(r[c])}</td>' for c in columns)+'</tr>' for r in comparison)
        st.markdown(f'<div class="nba-table-wrap"><table class="nba-table"><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table></div>',unsafe_allow_html=True)
        st.caption('Lower Brier and log loss indicate better probability forecasts. This evaluation did not retrain weights on 2025–26.')
        with st.expander('Performance by month • 2025–26'):
            st.dataframe(pd.DataFrame([{'Month':r['month'],'Games':r['games'],'Correct':r['correct'],'Accuracy':f'{r["accuracy"]*100:.2f}%','Brier':f'{r["brier"]:.4f}'} for r in evaluation['monthly']]),hide_index=True,use_container_width=True)
            st.caption('December and January were weaker. The full-season result includes every month.')
        with st.expander('Earlier chronological development'):
            st.metric('Development accuracy',f'{development["accuracy"]*100:.2f}%')
            st.caption(f'{development["games"]:,} games • 2018–19 through 2024–25. These games helped choose the model; they are separate from the reserved season and live record.')
    with tabs[2]:
        st.markdown('<div class="section-title">Inside NBA V1</div><div class="section-sub">14 prior-game features • one frozen team model</div>',unsafe_allow_html=True)
        cards=[('01','Efficiency and form','Offensive and defensive efficiency, shooting, turnovers, rebounding, free throws and recent form use games completed before the prediction date.'),('02','Team strength and schedule','Elo, home or neutral context, rest and back-to-backs provide matchup context. Neutral games receive no home advantage.'),('03','Frozen selection','Advanced-stat, tree, blend and calibration challengers did not meet the replacement rules. The original logistic baseline remained selected.'),('04','Separate scoreboards','The reserved-season evaluation is historical. Only valid pregame forecasts for the 2026–27 regular season can enter the official live record.'),('05','Player availability','NBA V1 does not yet adjust for confirmed starters or injuries. A future player layer needs verified pregame inputs and its own validation.')]
        for num,title,copy in cards:st.markdown(f'<div class="about-card"><div class="about-num">{num}</div><div class="about-title">{escape(title)}</div><div class="about-copy">{escape(copy)}</div></div>',unsafe_allow_html=True)
        st.caption(f'Training: {manifest["training_games"]:,} games, 2015–16 through 2024–25. No preseason testing is enabled.')
        st.link_button('View the NBA research report','https://github.com/bp111301/bp-sports/blob/nba-v1-research/research/nba/HANDOFF.md')
