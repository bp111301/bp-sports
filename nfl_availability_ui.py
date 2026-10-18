"""Read-only NFL availability context and explicitly labeled pregame refreshes."""
import html,json
from urllib.request import Request,urlopen
import pandas as pd
import streamlit as st

URL='https://raw.githubusercontent.com/bp111301/bp-sports/main/data/current/nfl_availability.json'

@st.cache_data(ttl=60)
def load_availability():
    try:
        with urlopen(Request(URL,headers={'User-Agent':'BP-Sports-Availability/1.0'}),timeout=8) as response:return json.loads(response.read(4*1024*1024))
    except Exception:return {}

def context_for(game_id,payload=None):return (load_availability() if payload is None else payload).get('games',{}).get(str(game_id),{})
def stamp(value):return pd.to_datetime(value,utc=True,errors='coerce')
def checked_label(entry,now=None):
    if not entry:return 'Availability not checked yet'
    now=stamp(now) if now is not None else pd.Timestamp.now(tz='UTC');checked=stamp(entry.get('checked_at_utc'));start=stamp(entry.get('kickoff_utc'))
    if pd.isna(checked) or pd.isna(start) or checked>=start or checked>now:return 'Pregame availability unavailable'
    if entry.get('qb_review_required'):return 'QB input needs review'
    if entry.get('source_errors'):return 'Availability source delayed'
    if not all(entry.get(side,{}).get('injury_report_available') for side in ['home','away']):return 'Injury report unavailable'
    if now<start and start-now<=pd.Timedelta(minutes=100) and now-checked>pd.Timedelta(minutes=35):return 'Pregame check delayed'
    if all(entry.get(side,{}).get('inactives_published') for side in ['home','away']):return 'Inactives checked'
    if entry.get('qb_uncertain'):return 'QB questionable · inactives pending'
    return 'Inactives pending'

def project_row(row,payload=None,now=None):
    """Presentation only. Official first-snapshot records are never rewritten."""
    r=dict(row);entry=context_for(r.get('game_id'),payload);latest=entry.get('latest_forecast',{})
    if bool(r.get('settled',False)) or not latest or entry.get('qb_review_required'):return r
    start=stamp(entry.get('kickoff_utc'));created=stamp(latest.get('captured_at_utc'));checked=stamp(entry.get('checked_at_utc'))
    now=stamp(now) if now is not None else pd.Timestamp.now(tz='UTC')
    if pd.isna(start) or pd.isna(created) or pd.isna(checked) or not checked<=created<start or created>now:return r
    if stamp(latest.get('kickoff_utc'))!=start:return r
    home=r.get('home',r.get('home_team'));away=r.get('away',r.get('away_team'))
    if latest.get('bundle_version')!='BP_V4_2026_FROZEN_20261005' or latest.get('home_team')!=home or latest.get('away_team')!=away:return r
    probability=pd.to_numeric(latest.get('v4_adjusted_confidence'),errors='coerce')
    if not .5<=probability<=1 or latest.get('v4_pick') not in (home,away):return r
    original=dict(r.get('details') or r)
    if created<=stamp(r.get('created',original.get('captured_at_utc'))):return r
    r.update(p=float(probability) if latest['v4_pick']==home else 1-float(probability),confidence=float(probability),created=created,
             details={**original,**latest,'original_snapshot_captured_at_utc':original.get('captured_at_utc'),'display_uses_latest_pregame':True})
    return r

def card_note(game_id,now=None):
    entry=context_for(game_id);label=checked_label(entry,now)
    return '<div style="font-size:.64rem;color:#b9cbe1;margin-top:9px;overflow-wrap:anywhere">'+html.escape(label)+'</div>'

def render_availability(game_id):
    entry=context_for(game_id)
    with st.expander('Player availability · official reports'):
        if not entry:
            st.info('No saved pregame availability check for this game.');return
        label=checked_label(entry);checked=stamp(entry.get('checked_at_utc'))
        if entry.get('qb_review_required'):st.warning('The assumed starting QB is confirmed out/inactive. The saved probability needs review; no new forecast is accepted with that QB input.')
        else:st.caption(label)
        if pd.notna(checked):st.caption('Checked '+checked.tz_convert('America/Chicago').strftime('%b %-d · %-I:%M %p CT'))
        for side in ['away','home']:
            team=entry.get(side,{})
            st.write(str(team.get('team',''))+' · QB input: '+str(team.get('assumed_qb','Unknown'))+' · '+str(team.get('qb_status','Unknown')))
            if team.get('starter_source_url'):st.link_button('QB announcement · '+str(team.get('team','')),team['starter_source_url'])
            players=team.get('players',[])
            if players:st.dataframe(pd.DataFrame(players)[['name','position','status']].rename(columns={'name':'Player','position':'Pos','status':'Status'}),hide_index=True,width='stretch')
            else:st.caption('No listed game designation found; this does not confirm the entire roster is active.')
        for label,url in [('Official injury report',entry.get('injuries_url')),('Official inactive lists',entry.get('inactives_url'))]:
            if url:st.link_button(label,url)
        st.caption('Confirmed QB changes can update the existing QB model inputs. Other absences are context; their probability effects have not been calibrated. Missing inactive lists remain pending.')
