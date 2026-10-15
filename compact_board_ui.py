"""Compact read-only boards using preserved primary pregame forecasts."""
import html
import pandas as pd
import streamlit as st
from overview_ui import load_overview, prepare, PRIMARY, COLUMNS, row, ts
from game_center_ui import load_scores, context, filter_favorites
from game_status import display_state, score
from matchup_details_ui import details_button, game_tile

UI_REVISION = 'compact-board-20261013'
def esc(value): return html.escape(str(value), quote=True)

def prepare_compact(sport, payload, score_feed, now, cbb=None):
    board, available, _ = prepare(payload, now)
    board = board[(board.sport == sport) & (board.group == PRIMARY.get(sport))].copy()
    if sport == 'NFL':
        ties = []
        for r in payload.get('nfl',{}).get('data',[]) or []:
            if r.get('settlement_status') != 'tie': continue
            created = ts(r.get('captured_at_utc'))
            p = pd.to_numeric(r.get('v4_adjusted_confidence'),errors='coerce')
            if pd.isna(created) or created > now or not 0<=p<=1: continue
            p = p if r.get('v4_pick') == r['home_team'] else 1-p
            ties.append(row(r['game_id'],'NFL','nfl',r['home_team'],r['away_team'],p,created,None,False,None,r))
        if ties:
            tie_frame=pd.DataFrame(ties,columns=COLUMNS).sort_values('created').drop_duplicates('game_id')
            board=pd.concat([board,tie_frame],ignore_index=True)
    if sport == 'CBB':
        records = []
        for r in (cbb or {}).get('predictions', []):
            if r.get('season') != 2027 or r.get('season_type') != 2: continue
            p = pd.to_numeric(r.get('home_win_prob'), errors='coerce')
            start, created = ts(r.get('start_time_utc')), ts(r.get('created_at_utc'))
            if pd.isna(start) or pd.isna(created) or not created < start or created > now or not 0 <= p <= 1: continue
            if r.get('bundle_sha256') != (cbb or {}).get('bundle_sha256'): continue
            settled = r.get('status') == 'settled'
            if r.get('status') not in ('pending', 'settled'): continue
            y = r.get('actual_home_win')
            if settled and (y not in (0,1) or start > now): continue
            records.append(row(r['game_id'],sport,'cbb',r['home_team'],r['away_team'],p,created,start,settled,y,r))
        board = pd.DataFrame(records,columns=COLUMNS)
    for index, r in board.iterrows():
        status = context(sport,r.game_id,r.home,r.away,score_feed)
        start = ts(status.get('start_time_utc')) if status else r.start
        if pd.isna(start):
            d = r.details
            start = ts(d.get('kickoff_utc',d.get('start_time_utc')))
        board.at[index,'start'] = start
    board['confidence'] = board.p.where(board.p.ge(.5),1-board.p)
    board['date'] = board.start.map(lambda value:value.tz_convert('America/Chicago').strftime('%Y-%m-%d') if pd.notna(value) else 'Time TBD')
    return board.sort_values(['start','game_id'],na_position='last'), available

def date_options(board, now, sport=None):
    dates = sorted(d for d in board.date.unique() if d != 'Time TBD')
    today = now.tz_convert('America/Chicago').strftime('%Y-%m-%d')
    if sport != 'NFL' and today not in dates: dates.append(today); dates.sort()
    if 'Time TBD' in set(board.date): dates.append('Time TBD')
    default = today if today in set(board.date) else next((d for d in dates if d > today and d in set(board.date) and d != 'Time TBD'),dates[-1] if dates else None)
    return dates, default

def date_label(value):
    if value == 'Time TBD': return value
    return pd.Timestamp(value).strftime('%a · %b %-d')

def team_label(sport, value):
    if sport == 'NFL':
        teams = {'ARI':'Cardinals','ATL':'Falcons','BAL':'Ravens','BUF':'Bills','CAR':'Panthers','CHI':'Bears','CIN':'Bengals','CLE':'Browns','DAL':'Cowboys','DEN':'Broncos','DET':'Lions','GB':'Packers','HOU':'Texans','IND':'Colts','JAX':'Jaguars','KC':'Chiefs','LA':'Rams','LAR':'Rams','LAC':'Chargers','LV':'Raiders','MIA':'Dolphins','MIN':'Vikings','NE':'Patriots','NO':'Saints','NYG':'Giants','NYJ':'Jets','PHI':'Eagles','PIT':'Steelers','SEA':'Seahawks','SF':'49ers','TB':'Buccaneers','TEN':'Titans','WAS':'Commanders'}
        return teams.get(value,value)
    if sport == 'NHL':
        from nhl_ui import TEAMS
        return TEAMS.get(value,value)
    if sport == 'NBA':
        from nba_ui import TEAMS
        return TEAMS.get(value,value)
    return value

def short_name(value,sport=None,team_id=None):
    if sport in ('CFB','CBB'):
        from college_team_ui import college_abbreviation
        return college_abbreviation(sport,value,team_id)
    if len(value) <= 4: return value
    return ''.join(w[0] for w in str(value).split()[:3]).upper()

def compact_html(r, feed, now):
    from team_theme_ui import team_color,text_color,accent_color
    status = context(r.sport,r.game_id,r.home,r.away,feed)
    state = display_state(status,r.settled,r.start,now)
    d = r.details
    h = score(status.get('home_score')) if status else None
    a = score(status.get('away_score')) if status else None
    if r.settled:
        final_h = score(d.get('actual_home_score',d.get('home_score')))
        final_a = score(d.get('actual_away_score',d.get('away_score')))
        if final_h is not None and final_a is not None: h,a = final_h,final_a
        elif not status or status.get('state') != 'final': h=a=None
        state = 'Final' if h is not None and a is not None else 'Final · score unavailable'
    pick = r.home if r.p >= .5 else r.away
    grade = ('WIN' if (r.p>=.5)==r.y else 'LOSS') if r.settled else 'PENDING'
    if d.get('settlement_status') == 'tie':
        grade = 'TIE'
        state = 'Final · tie'
        h,a = score(d.get('actual_home_score')),score(d.get('actual_away_score'))
    time = r.start.tz_convert('America/Chicago').strftime('%-I:%M %p CT') if pd.notna(r.start) else 'Time TBD'
    detail = status.get('detail','') if status and status.get('state')=='live' and not r.settled else time
    away_color=team_color(r.sport,r.away,d.get('away_team_id'))
    home_color=team_color(r.sport,r.home,d.get('home_team_id'))
    pick_color=home_color if r.p>=.5 else away_color
    return f'''<div class="bp-mini" style="--bp-away:{away_color};--bp-home:{home_color};--bp-pick:{accent_color(pick_color)};--bp-away-tint:{away_color}38;--bp-home-tint:{home_color}38">
      <div class="bp-mini-top"><span>{esc(r.sport)} · {esc(state)}</span><span>{esc(detail)}</span></div>
      <div class="bp-mini-team"><span class="bp-mini-badge" style="background:{away_color};color:{text_color(away_color)}">{esc(short_name(r.away,r.sport,d.get('away_team_id')))}</span><span class="bp-mini-name">{esc(team_label(r.sport,r.away))}</span><strong>{a if a is not None else '—'}</strong></div>
      <div class="bp-mini-team"><span class="bp-mini-badge" style="background:{home_color};color:{text_color(home_color)}">{esc(short_name(r.home,r.sport,d.get('home_team_id')))}</span><span class="bp-mini-name">{esc(team_label(r.sport,r.home))}</span><strong>{h if h is not None else '—'}</strong></div>
      <div class="bp-mini-pick"><span class="bp-mini-selected">BP PICK <b>{esc(pick)}</b><small class="{grade.lower()}">{grade}</small></span><span class="bp-mini-confidence"><b>{r.confidence:.1%}</b><small>WIN CONFIDENCE</small></span></div>
      <div class="bp-mini-bar"><div style="width:{r.confidence*100:.1f}%"></div></div>
    </div>'''

@st.dialog('Game details',width='large')
def open_cbb_details(r):
    from cbb_ui import card_html
    st.markdown(card_html({**r.details,'prob':r.p,'confidence':r.confidence,'start':r.start}),unsafe_allow_html=True)
    st.caption('Prior-season team history · no current roster, transfer or injury inputs.')

def render_compact(sport):
    now = pd.Timestamp.now(tz='UTC')
    feed = load_scores()
    cbb = None
    if sport == 'CBB':
        from cbb_ui import load_feed
        cbb = load_feed()
        payload = {}
    else:
        payload = load_overview()
    board, available = prepare_compact(sport,payload,feed,now,cbb)
    key = {'NFL':'nfl','CFB':'cfb','NHL':'nhl','NBA':'nba'}.get(sport)
    if (sport == 'CBB' and cbb is None) or (key and not available.get(key)):
        st.warning(sport+' saved forecast feed is unavailable. Try Refresh shortly.')
        return
    st.caption('Saved picks · verified scores · Central time')
    if sport in ('NHL','CBB'): st.caption(sport+' is collecting prospective evidence as a candidate. Saved probabilities are experimental.')
    dates, default = date_options(board,now,sport)
    if not dates:
        st.info('No saved game dates are available yet. Open the detailed board for model information.')
        return
    selected_key = 'compact_date_'+sport
    if st.session_state.get(selected_key) not in dates: st.session_state[selected_key] = default
    date = st.selectbox('Game date · Central time',dates,format_func=date_label,key=selected_key)
    shown = board[board.date == date]
    with st.expander('Find a team or filter your board'):
        query = st.text_input('Search teams',key='compact_search_'+sport)
        if query: shown = shown[shown.apply(lambda r:query.casefold() in (str(r.home)+' '+str(r.away)+' '+str(team_label(sport,r.home))+' '+str(team_label(sport,r.away))).casefold(),axis=1)]
        shown = filter_favorites(shown,sport,'compact_favorites_'+sport,home='home',away='away')
    st.subheader('Games')
    st.caption(str(len(shown))+' saved matchups · '+date_label(date))
    if shown.empty:
        st.info('No saved forecasts for this date. Choose another date or open the detailed board.')
    for offset in range(0,len(shown),2):
        columns = st.columns(2,gap='small')
        for column, (_,r) in zip(columns,shown.iloc[offset:offset+2].iterrows()):
            with column:
                game_tile(sport,r.to_dict(),'compact_detail_'+sport+'_'+r.game_id,
                          compact_html(r,feed,now),now=now,
                          on_open=(lambda r=r:open_cbb_details(r)) if sport=='CBB' else None)
    if sport == 'CBB':
        with st.expander('Schedule coverage'):
            excluded = (cbb or {}).get('excluded',{})
            st.write(f"Partial schedule: {excluded.get('tipoff_time_unconfirmed',0)} source games await confirmed tipoff times; {excluded.get('division_or_conference_unknown',0)} have unknown eligibility.")
    st.caption('Scores use the existing periodic feed. A source final may appear before grading; saved probabilities stay unchanged.')

def render_compact_styles():
    st.markdown('''<style>
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{max-width:100%;overflow-x:hidden}
.block-container{box-sizing:border-box;min-width:0;width:100%}
[data-testid="stElementContainer"],[data-testid="stVerticalBlock"],[data-testid="stHorizontalBlock"],[data-testid="stColumn"]{min-width:0}
.st-key-bp_sport [role="radiogroup"]{flex-wrap:wrap!important;overflow-x:visible!important;max-width:100%}
.st-key-bp_sport [data-testid="stRadioOption"],.st-key-bp_sport label{border:0!important;border-radius:0!important;background:transparent!important;padding:10px 12px!important}
.st-key-bp_sport label:has(input:checked){border-bottom:3px solid #6ea8fe!important;background:transparent!important}
.st-key-bp_sport label:has(input:checked) p{color:#83b6ff!important}
[class*="st-key-compact_date_"]{min-width:0;max-width:100%}
[class*="st-key-compact_date_"] [role="radiogroup"]{flex-wrap:wrap!important;overflow-x:visible;gap:6px;padding:5px 0 10px;min-width:0;max-width:100%}
[class*="st-key-compact_date_"] label{flex:0 0 auto;white-space:nowrap;border:1px solid #29384e;border-radius:10px;padding:9px 12px;background:#111b29}
[class*="st-key-compact_date_"] label:has(input:checked){background:#1e3d64;border-color:#6ea8fe}
[class*="st-key-compact_date_"] [data-testid="stRadioOption"]>div>div:first-child:not([data-testid="stMarkdownContainer"]){display:none}
.bp-mini{container-type:inline-size;background:linear-gradient(135deg,#131e2e,#0e1723);border:1px solid #2a3c54;border-radius:15px;padding:13px 15px;margin-top:6px;min-width:0}
.bp-mini-top{display:flex;justify-content:space-between;gap:8px;font-size:.67rem;color:#a0b3ce;margin-bottom:10px}
.bp-mini-team{display:flex;gap:9px;align-items:center;margin:7px 0}.bp-mini-badge{width:31px;height:31px;flex:0 0 31px;display:flex;align-items:center;justify-content:center;background:#254970;border-radius:9px;font-size:.6rem;font-weight:850;color:#d8e9ff}
.bp-mini-name{flex:1;min-width:0;font-size:.9rem;font-weight:750;overflow-wrap:normal;word-break:normal}.bp-mini-team strong{font-size:1.2rem}
.bp-mini-pick{display:flex;flex-wrap:wrap;justify-content:space-between;gap:10px;border-top:1px solid #29394e;padding-top:10px;margin-top:11px;font-size:.7rem;color:#91a9c8}.bp-mini-pick b{color:#deebff}.bp-mini-pick small{font-size:.55rem;margin-left:5px}.bp-mini-pick .win{color:#82e9ad}.bp-mini-pick .loss{color:#ff9aa6}
.bp-mini-selected{flex:1 1 150px;min-width:0;overflow-wrap:normal;word-break:normal}.bp-mini-selected b,.bp-mini-selected small{display:block;margin:3px 0 0}
.bp-mini-confidence{flex:0 0 100px;text-align:right}.bp-mini-confidence b{font-size:1.3rem;font-weight:900}.bp-mini-confidence small{display:block;white-space:nowrap;margin:3px 0 0;letter-spacing:.05em}
.bp-mini-bar{height:7px;background:#26364c;border-radius:99px;overflow:hidden;margin-top:11px}.bp-mini-bar>div{height:100%;border-radius:99px;background:linear-gradient(90deg,#6ea8fe,#c1d7ff)}
.bp-mini{background:radial-gradient(ellipse at 0 0,var(--bp-away-tint),transparent 65%),radial-gradient(ellipse at 100% 100%,var(--bp-home-tint),transparent 65%),#101925;border-left:4px solid var(--bp-pick)}
.bp-mini-badge{box-shadow:inset 0 0 0 1px #ffffff30}.bp-mini-confidence b{color:var(--bp-pick)}.bp-mini-bar>div{background:linear-gradient(90deg,var(--bp-pick),#d4e6ff)}
[data-testid="stButton"] button p{white-space:normal;overflow-wrap:normal;word-break:normal}
@container(max-width:280px){
.bp-mini-pick{display:grid;grid-template-columns:minmax(0,1fr);gap:9px}
.bp-mini-selected{width:100%;min-width:0}
.bp-mini-confidence{display:flex;align-items:baseline;justify-content:space-between;gap:8px;width:100%;text-align:right}
.bp-mini-confidence small{order:-1;white-space:normal;letter-spacing:.02em;text-align:left}
.bp-mini-confidence b{white-space:nowrap}
}
@media(max-width:640px){.bp-mini{padding:11px 12px}.bp-mini-name{font-size:.86rem}.st-key-bp_sport label{padding:10px 9px!important}}

/* A native, keyboard-accessible button covers the full card. */
[class*="st-key-bp_game_tile_"]{position:relative;gap:0!important;isolation:isolate}
[class*="st-key-bp_game_tile_"] > [data-testid="stElementContainer"]:has([data-testid="stButton"]){position:absolute!important;inset:0!important;width:100%!important;height:100%!important;z-index:2;margin:0!important}
[class*="st-key-bp_game_tile_"] [data-testid="stButton"]{height:100%!important}
[class*="st-key-bp_game_tile_"] [data-testid="stButton"] button{height:100%!important;width:100%!important;min-height:100%!important;background:transparent!important;border:0!important;border-radius:15px!important;box-shadow:none!important;cursor:pointer}
[class*="st-key-bp_game_tile_"] [data-testid="stButton"] button p{opacity:0}
[class*="st-key-bp_game_tile_"] [data-testid="stButton"] button:hover{background:#ffffff06!important}
[class*="st-key-bp_game_tile_"] [data-testid="stButton"] button:focus-visible{outline:3px solid #8bbdff!important;outline-offset:2px}
</style>''',unsafe_allow_html=True)
