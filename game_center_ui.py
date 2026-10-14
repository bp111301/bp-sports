"""Shared scores, preferences and probability guidance for the web UI."""
UI_REVISION="clean-nav-20261013"
import html,json
from pathlib import Path
from urllib.request import Request,urlopen
import pandas as pd
import streamlit as st
from game_status import matches,display_state,score
from preview_data import game_id,team,stamp
ROOT=Path(__file__).parent
STATUS_URL='https://raw.githubusercontent.com/bp111301/bp-sports/main/data/game_status.json'

def esc(x):return html.escape(str(x),quote=True)

@st.cache_data(ttl=60)
def load_scores():
    try:
        with urlopen(Request(STATUS_URL,headers={'User-Agent':'BP-Sports-Scores/1.0'}),timeout=6) as response:return json.loads(response.read(4*1024*1024))
    except Exception:
        try:return json.loads((ROOT/'data/game_status.json').read_text())
        except (OSError,ValueError):return {}

def context(sport,gid,home,away,feed=None):
    r=(load_scores() if feed is None else feed).get('games',{}).get(sport+':'+game_id(gid))
    return r if matches(r,sport,home,away) else None

def score_html(sport,gid,home,away,settled=False,start=None,now=None,feed=None):
    r=context(sport,gid,home,away,feed);state=display_state(r,settled,start,now)
    cls='final' if r and r['state']=='final' or settled else 'live' if r and r['state']=='live' else 'scheduled'
    h,a=(score(r.get('home_score')),score(r.get('away_score'))) if r else (None,None)
    value=f'{esc(away)} <b>{a}</b> <span>–</span> <b>{h}</b> {esc(home)}' if h is not None and a is not None else 'Score unavailable' if settled else 'Scores appear when verified'
    detail=r.get('detail','') if r and r['state']=='live' else ''
    if r and r['state']=='scheduled' and pd.notna(stamp(r.get('start_time_utc'))):detail=stamp(r['start_time_utc']).tz_convert('America/Chicago').strftime('%a %b %d · %-I:%M %p CT')
    checked=stamp(r.get('checked_at_utc')) if r else pd.NaT
    stale=pd.notna(checked) and (stamp(now) if now is not None else pd.Timestamp.now(tz='UTC'))-checked>pd.Timedelta(minutes=30) and r['state']!='final'
    age=' · update delayed' if stale else ''
    source=f'<a href="{esc(r["source_url"])}" target="_blank" rel="noopener noreferrer">Source</a>' if r else ''
    at=checked.tz_convert('America/Chicago').strftime('%b %d, %-I:%M %p CT') if pd.notna(checked) else 'not available'
    return f'<div class="bp-score"><div class="bp-score-top"><span class="bp-game-state {cls}">{esc(state+age)}</span><span>{esc(detail)}</span></div><div class="bp-score-value">{value}</div><div class="bp-score-source">Score check: {esc(at)} {source}</div></div>'

def confidence_html(prob,sport,audit=False):
    p=float(prob);opponent=(1-p)*100
    if audit:note='Input concern: missing power-play feature. Treat this estimate cautiously; see the audit.'
    elif p>=.9:note='Unusually high estimate · limited prospective evidence at this confidence level.'
    elif sport=='NHL':note='Experimental estimate · NHL models have not passed the release gate.'
    else:note='Saved model estimate · performance is tracked against actual results.'
    return f'<div class="bp-confidence {"concern" if audit or p>=.9 else ""}"><b>Opponent chance: {opponent:.1f}%</b><span>{esc(note)}</span></div>'

def favorite_key(sport,name):return sport+':'+team(sport,name)

def favorites_mask(frame,sport,home='home_team',away='away_team',selected=None):
    chosen=set(st.session_state.get('bp_favorites',[]) if selected is None else selected)
    return frame.apply(lambda r:favorite_key(sport or r['sport'],r[home]) in chosen or favorite_key(sport or r['sport'],r[away]) in chosen,axis=1).astype(bool)

def filter_favorites(frame,sport,key,home='home_team',away='away_team'):
    only=st.toggle('My teams only',key=key)
    if not only:return frame
    if not st.session_state.get('bp_favorites'):st.info('Choose favorites in ☰ Menu → My teams to use this filter.')
    return frame[favorites_mask(frame,sport,home,away)]

def save_favorites():
    picks=st.session_state.get('bp_favorites',[])
    if picks:st.query_params['teams']='|'.join(picks)
    elif 'teams' in st.query_params:del st.query_params['teams']


def menu_route(page, sport=None):
    from navigation_ui import request_top
    st.session_state['bp_page']=page
    if sport is not None:st.session_state['bp_sport']=sport
    request_top()


def board_route():
    from navigation_ui import request_top
    st.session_state['bp_page']='Board'
    request_top()


def render_information(page):
    st.button('← Back to games',key='bp_back_to_board',on_click=board_route)
    if page=='Weekly results':
        import importlib, overview_ui
        if getattr(overview_ui,'UI_REVISION',None)!='weekly-results-20261013':importlib.reload(overview_ui)
        overview_ui.render_weekly_results()
        return
    if page=='About B.P. Sports':
        st.title('Sports, with a clearer picture.')
        st.write('B.P. Sports brings NFL, college football, NHL and NBA matchups, saved predictions and results into one sports desk. Follow your teams, understand each forecast and see how the models perform when the games are played.')
        st.subheader('Built on evidence')
        st.write('We publish probabilities before games and preserve those snapshots. Confirmed results build the live record. A model’s historical testing is shown separately so you can see the difference between development results and real prospective performance.')
        st.subheader('Still growing')
        st.write('B.P. Sports is an independent project in active development. The models are gathering prospective evidence, the NHL board remains research, and a mobile app is our longer-term goal.')
        st.info('A probability is an estimate, never a guarantee. Even a strong favorite can lose.')
        return
    st.title('Our models & data')
    st.write('Each sport has its own model. Inputs use information available before the game; future scores do not belong in a pregame forecast.')
    models=[
        ('NFL · Frozen V4','NFL play-by-play and schedules from nflverse.','Team efficiency, opponent strength, Elo, recent form, rest and quarterback quality or changes. EPA measures how much a play improves a team’s expected scoring position. Explosive plays, turnovers and early-down efficiency can adjust confidence without flipping the core winner.','Starter inputs can be refreshed before kickoff. This is a new timestamped forecast, not a change to the frozen model weights.','main/model/v4/BP_V4_FROZEN_SPEC.md'),
        ('CFB · Frozen V1','College football matchup data built from cfbfastR, plus team context such as talent and returning production.','A 25% context and 75% dynamic-prior ensemble combines efficiency, Elo, home field, conference context, talent and coaching continuity. A seven-week transition gradually shifts emphasis from last season to this season.','CFB V1 excludes quarterback features. Frozen Candidate B is a separate challenger collecting results; it has not replaced V1.','main/model/cfb/v1/CFB_V1_FROZEN_SPEC.md'),
        ('NHL · Prospective research','Prior NHL results and team statistics; separately archived pregame goalie reports.','The watchlist compares a reference control, recency weighting and a regulation-probability blend. Team inputs include Elo, scoring, recent results, rest and statistics shifted to exclude the current game.','The original NHL V1 failed its release gate. Watchlist models and the confirmed-goalie paired experiment remain research; goalie experiments do not automatically change the board’s team-only picks.','nhl-v1-research/research/nhl/v2/HANDOFF.md'),
        ('NBA · Frozen V1','Historical NBA box-score and schedule data.','Fourteen prior-game features cover Elo, home context, offense and defense, pace, effective shooting, turnovers, offensive rebounding, free throws, recent form, rest and back-to-backs.','Regular-season prospective forecasts only. NBA V1 does not adjust for injuries or confirmed starters, and preseason games are excluded.','nba-v1-research/research/nba/HANDOFF.md')]
    for title,source,inputs,limits,path in models:
        with st.expander(title):
            st.markdown('**Data**')
            st.write(source)
            st.markdown('**What goes into the prediction**')
            st.write(inputs)
            st.markdown('**Current status & limits**')
            st.write(limits)
            st.link_button('Read the model report','https://github.com/bp111301/bp-sports/blob/'+path)
    with st.expander('CBB · Research candidate'):
        st.write('Men’s Division I regular-season schedules and team box scores from the SportsDataverse ESPN data archive. Inputs include Elo, venue, prior-game offense and defense, shooting, turnovers, rebounding, free throws, pace, rest and experience.')
        st.write('The candidate passed its locked historical gate and is gathering prospective evidence. Early forecasts use prior-season team history with no current roster, transfer or injury inputs. Schedule coverage is incomplete; unconfirmed times and unknown eligibility are excluded. Historical testing stays separate from the prospective record.')
        st.link_button('Read the CBB research report','https://github.com/bp111301/bp-sports/blob/cbb-v1-research/research/cbb/HANDOFF.md')
    st.subheader('How we keep score')
    st.write('Frozen means the algorithm and weights stay fixed while we collect new results. Pregame information can update, but saved forecasts stay preserved. Any future model change receives its own version and evaluation.')
    st.write('Accuracy measures correct winners. Brier score and log loss measure probability quality: lower is better. Pending games do not count as wins or losses. Betting-market prices do not choose our winners.')

def render_preferences(nfl):
    from nhl_ui import TEAMS as hockey
    from nba_ui import TEAMS as basketball
    options={favorite_key('NFL',k):'NFL · '+v+' ('+k+')' for k,v in nfl.items()}
    options.update({favorite_key('NHL',k):'NHL · '+v+' ('+k+')' for k,v in hockey.items()})
    options.update({favorite_key('NBA',k):'NBA · '+v+' ('+team('NBA',k)+')' for k,v in basketball.items()})
    try:
        for name in json.loads((ROOT/'data/team_catalog.json').read_text()).get('CFB',[]):options[favorite_key('CFB',name)]='CFB · '+name
        records=json.loads((ROOT/'data/matchup_previews.json').read_text()).get('games',{}).values()
        for r in records:
            if r['sport']=='CFB':
                for side in ('home_team','away_team'):options[favorite_key('CFB',r[side])]='CFB · '+r[side]
    except (OSError,ValueError,KeyError):pass
    from cbb_ui import load_feed
    for r in (load_feed() or {}).get('predictions',[]):
        for side in ('home_team','away_team'):options[favorite_key('CBB',r[side])]='CBB · '+r[side]
    if 'bp_favorites' not in st.session_state:st.session_state['bp_favorites']=[k for k in st.query_params.get('teams','').split('|') if k in options]
    with st.popover('☰ Menu',use_container_width=True):
        st.markdown('### Your sports desk')
        st.caption('Jump to a board or explore B.P. Sports.')
        left,right=st.columns(2)
        for index,name in enumerate(['Overview','NFL','CFB','NHL','NBA','CBB']):
            (left if index%2==0 else right).button(name,key='bp_menu_'+name,use_container_width=True,on_click=menu_route,args=('Board',name))
        st.divider()
        st.button('Weekly results',key='bp_menu_weekly',use_container_width=True,on_click=menu_route,args=('Weekly results',None))
        st.button('About B.P. Sports',key='bp_menu_about',use_container_width=True,on_click=menu_route,args=('About B.P. Sports',None))
        st.button('Our models & data',key='bp_menu_models',use_container_width=True,on_click=menu_route,args=('Our models & data',None))
        st.divider()
        st.markdown('**My teams**')
        st.multiselect('Choose favorite teams',sorted(options,key=options.get),format_func=options.get,key='bp_favorites',on_change=save_favorites)
        st.caption('Your teams are saved in this page’s link. Bookmark it to keep your selection. Use My teams only on any board; records still include all tracked picks.')
        with st.expander('Understanding predictions'):
            st.write('70% is the model’s estimated chance of winning: it still gives the opponent 30%. Across many well-calibrated 70% predictions, about 7 in 10 should win. A single game can go either way.')
            st.write('These models are collecting prospective evidence. High estimates are not locks; the confidence table on Overview compares saved probabilities with actual win rates. NHL remains experimental.')
        with st.expander('Score updates'):
            st.caption('This page checks every minute. The source feed refreshes about every 15 minutes; source or workflow delays can take longer. Confirmed finals may await grading. Refresh reloads saved feeds for all four sports.')
    st.markdown('''<style>
[data-testid="stPopoverBody"]{max-height:75vh;max-height:75dvh;overflow-y:auto;max-width:calc(100vw - 24px)}
.bp-score{background:#0b1420;border:1px solid #2a394c;border-radius:12px;padding:12px 14px;margin:12px 0}.bp-score-top{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:.7rem;color:#abbdd1}.bp-game-state{display:inline-block;font-weight:850;border-radius:30px;padding:4px 9px;background:#1d2c40;color:#bed6fa}.bp-game-state.live{background:#123e2d;color:#88f0bc}.bp-game-state.final{background:#25354d;color:#d4e3fb}.bp-score-value{font-size:1rem;color:#eef5ff;margin-top:8px;overflow-wrap:anywhere}.bp-score-value b{font-size:1.3rem}.bp-score-value span{color:#91a6c3}.bp-score-source{font-size:.65rem;color:#9bb0ca;margin-top:5px}.bp-score-source a{margin-left:8px;color:#93c1ff}.bp-confidence{display:flex;flex-direction:column;gap:4px;font-size:.72rem;color:#aabbd0;margin:10px 0 0;line-height:1.45}.bp-confidence b{font-weight:650;color:#c7d9ef}.bp-confidence.concern{border-left:3px solid #e4bc62;padding-left:10px;color:#ecd29c}
@media(max-width:640px){.st-key-bp_sport [role="radiogroup"]{display:flex!important;flex-wrap:nowrap!important;overflow-x:auto;gap:4px;padding-bottom:4px}.st-key-bp_sport label{flex:0 0 auto!important;width:max-content!important;min-width:max-content!important;min-height:44px;padding:8px!important}.card-top{align-items:flex-start;gap:6px}.game-meta{letter-spacing:.03em;line-height:1.5}.team-box{gap:6px}.team-name{overflow-wrap:anywhere}.prob{white-space:nowrap}.model-strip{grid-template-columns:1fr!important}.model-cell{display:flex;justify-content:space-between;align-items:center;gap:10px}.model-cell .m,.model-cell .v{margin:0}.nhl-goalies{grid-template-columns:1fr!important}.nhl-goalies div:last-child{text-align:left!important}.bp-score{padding:10px}.bp-score-top{flex-wrap:wrap}.bp-score-value{font-size:.88rem}.bp-confidence{font-size:.73rem}.spotlight{grid-template-columns:1fr!important;gap:12px}.spot-prob{text-align:left}.hero-copy{line-height:1.6}.st-key-open_NFL button,.st-key-open_CFB button,.st-key-open_NHL button,.st-key-open_NBA button{min-height:44px} [data-testid="stTabs"] [role="tab"]{min-height:44px} [data-testid="stExpander"] summary{min-height:44px}}
.st-key-bp_sport [role="radiogroup"]{flex-wrap:nowrap!important;overflow-x:auto;max-width:100%;padding-bottom:4px}
.st-key-bp_sport [data-testid="stRadioOption"]{flex:0 0 auto!important;width:max-content!important;min-width:max-content!important;white-space:nowrap!important;min-height:44px}
.st-key-bp_sport [data-testid="stRadioOption"]>div{flex:0 0 auto!important;width:auto!important;min-width:max-content!important}
.st-key-bp_sport [data-testid="stRadioOption"]>div>div:first-child:not([data-testid="stMarkdownContainer"]){display:none}
.st-key-bp_sport [data-testid="stMarkdownContainer"],.st-key-bp_sport label p{white-space:nowrap!important;word-break:normal!important;overflow-wrap:normal!important;width:auto!important;max-width:none!important}
.st-key-bp_toolbar [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:8px!important}
.st-key-bp_toolbar [data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important;width:calc(50% - 4px)!important}
.st-key-bp_toolbar button{min-height:44px;white-space:nowrap}
.st-key-bp_toolbar [data-testid="stCaptionContainer"] p{font-size:.7rem;line-height:1.35}
</style>''',unsafe_allow_html=True)

@st.fragment(run_every='60s')
def render_score_refresh():
    feed=load_scores();stamp_value=feed.get('updated_at_utc');old=st.session_state.get('bp_score_version');st.session_state['bp_score_version']=stamp_value
    if old and stamp_value and old!=stamp_value:
        st.cache_data.clear();st.rerun()
    if st.button('Refresh',key='bp_refresh_scores',use_container_width=True):
        st.cache_data.clear();st.rerun()
    when=stamp(stamp_value)
    label=when.tz_convert('America/Chicago').strftime('%b %-d · %-I:%M %p CT') if pd.notna(when) else 'unavailable'
    delayed=pd.notna(when) and pd.Timestamp.now(tz='UTC')-when>pd.Timedelta(minutes=30)
    st.caption('Updated '+label+(' · delayed' if delayed else ''))


def render_header():
    st.markdown('''<div class="bp-nav"><div class="bp-logo"><div class="bp-mark">BP</div><div><div class="bp-wordmark">B.P. <span>SPORTS</span></div><div class="bp-kicker">YOUR SPORTS DESK</div></div></div><div class="live-pill"><span class="live-dot"></span> FROZEN</div></div>''',unsafe_allow_html=True)


def render_host_chrome():
    # Same-origin Community Cloud wrapper. Only its two floating badges are hidden.
    # Keep this optional so embedding the app elsewhere still works normally.
    st.html('''<script>(() => {
      try {
        const host = window.parent.document;
        if (!host.getElementById('bp-host-chrome')) {
          const style = host.createElement('style');
          style.id = 'bp-host-chrome';
          style.textContent = '[data-testid="manage-app-button"], a[href="https://streamlit.io/cloud"], a:has(>img[data-testid="appCreatorAvatar"]){display:none!important}';
          host.head.appendChild(style);
        }
      } catch (_) {}
    })();</script>''',unsafe_allow_javascript=True)

