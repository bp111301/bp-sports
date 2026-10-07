"""Shared scores, preferences and probability guidance for the web UI."""
UI_REVISION="mobile-layout-20261007"
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
    if not st.session_state.get('bp_favorites'):st.info('Choose teams in My teams above to use this filter.')
    return frame[favorites_mask(frame,sport,home,away)]

def save_favorites():
    picks=st.session_state.get('bp_favorites',[])
    if picks:st.query_params['teams']='|'.join(picks)
    elif 'teams' in st.query_params:del st.query_params['teams']

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
    if 'bp_favorites' not in st.session_state:st.session_state['bp_favorites']=[k for k in st.query_params.get('teams','').split('|') if k in options]
    with st.popover('Board options',use_container_width=True):
        st.markdown('**My teams**')
        st.multiselect('Choose favorite teams',sorted(options,key=options.get),format_func=options.get,key='bp_favorites',on_change=save_favorites)
        st.caption('Your teams are saved in this page’s link. Bookmark it to keep your selection. Use My teams only on any board; records still include all tracked picks.')
        st.markdown('**What confidence means**')
        st.write('70% is the model’s estimated chance of winning: it still gives the opponent 30%. Across many well-calibrated 70% predictions, about 7 in 10 should win. A single game can go either way.')
        st.write('These models are collecting prospective evidence. High estimates are not locks; the confidence table on Overview compares saved probabilities with actual win rates. NHL remains experimental.')
        st.markdown('**Score updates**')
        st.caption('This page checks every minute. The source feed refreshes about every 15 minutes; source or workflow delays can take longer. Confirmed finals may await grading. Refresh reloads saved feeds for all four sports.')
    st.markdown('''<style>
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
          style.textContent = 'a[href="https://streamlit.io/cloud"], a:has(>img[data-testid="appCreatorAvatar"]){display:none!important}';
          host.head.appendChild(style);
        }
      } catch (_) {}
    })();</script>''',unsafe_allow_javascript=True)
