"""One read-only matchup view shared by the four sport boards and Overview."""
import math
import pandas as pd
import streamlit as st
from game_center_ui import score_html,confidence_html,context,esc
from matchup_preview_ui import render_preview
from preview_data import stamp,game_id

LABELS={'NFL':'NFL V4','CFB':'CFB V1','NHL':'NHL reference','NBA':'NBA V1'}

def detail_payload(sport,row,model_label=None,settled=None):
    r=dict(row);source=dict(r.get('details') or r)
    home=str(r.get('home',r.get('home_team')));away=str(r.get('away',r.get('away_team')))
    if sport=='NFL':
        pick=str(source.get('v4_pick',home if float(r.get('p',.5))>=.5 else away))
        prob=float(source.get('v4_adjusted_confidence',max(float(r.get('p',.5)),1-float(r.get('p',.5)))))
        p=prob if pick==home else 1-prob
    else:p=float(r.get('p',r.get('home_win_prob')));pick=home if p>=.5 else away;prob=max(p,1-p)
    if not math.isfinite(p) or not 0<=p<=1:raise ValueError('Invalid saved probability')
    capture=r.get('created',source.get('snapshot_created_utc',source.get('created_at_utc',source.get('captured_at_utc'))))
    start=r.get('start',r.get('schedule_kickoff_utc',r.get('kickoff_utc',r.get('start_time_utc'))))
    if pd.isna(stamp(start)):start=source.get('kickoff_utc',source.get('start_time_utc'))
    done=bool(r.get('settled',r.get('_settled',r.get('status')=='settled' or r.get('settlement_status') in ('final','tie')))) if settled is None else bool(settled)
    result='Pending · excluded from record'
    if done:
        correct=r.get('correct');y=r.get('y',r.get('actual_home_win'))
        if pd.notna(correct):result='Win' if float(correct)==1 else 'Loss'
        elif y in (0,1):result='Win' if (p>=.5)==int(y) else 'Loss'
        elif sport=='NFL':
            h,a=pd.to_numeric(r.get('actual_home_score'),errors='coerce'),pd.to_numeric(r.get('actual_away_score'),errors='coerce')
            if pd.notna(h) and pd.notna(a):result='Tie · excluded from record' if h==a else 'Win' if (pick==home)==(h>a) else 'Loss'
            else:result='Final · grade unavailable'
        else:result='Final · grade unavailable'
    preview={**source,'game_id':r['game_id'],'home_team':home,'away_team':away,'home_win_prob':p,'created_at_utc':capture,'start_time_utc':start}
    if sport=='NFL':preview.update(v4_pick=pick,v4_adjusted_confidence=prob,captured_at_utc=capture)
    if sport=='CFB':preview.update(snapshot_created_utc=capture,kickoff_utc=source.get('kickoff_utc',start))
    return dict(sport=sport,game_id=game_id(r['game_id']),home=home,away=away,p=p,pick=pick,prob=prob,capture=capture,start=start,settled=done,result=result,label=model_label or LABELS[sport],preview=preview)

def render_details(payload,extras=None,now=None):
    d=payload;sport=d['sport']
    st.markdown(f'### {esc(d["away"])} @ {esc(d["home"])}')
    st.caption(sport+' · '+d['label']+(' · experimental' if sport=='NHL' else ' · frozen model'))
    st.markdown(score_html(sport,d['game_id'],d['home'],d['away'],d['settled'],d['start'],now),unsafe_allow_html=True)
    a,b=st.columns([2,1]);a.metric('Saved pick',d['pick']);b.metric('Saved confidence',f'{d["prob"]*100:.1f}%')
    if d['result']=='Win':st.success('Saved pick result: Win')
    elif d['result']=='Loss':st.error('Saved pick result: Loss')
    else:st.info('Saved pick result: '+d['result'])
    audit=None
    if sport=='NHL':
        from nhl_ui import audit_note
        audit=audit_note(d['game_id'],d['preview'].get('bundle_sha256'))
    st.markdown(confidence_html(d['prob'],sport,bool(audit)),unsafe_allow_html=True)
    if audit:
        st.warning(audit['message']);st.link_button('View input audit',audit['report_url'])
    st.divider();render_preview(sport,d['preview'],d['label'])
    if extras and extras.get('goalies'):
        from nhl_ui import goalie_text
        st.markdown('#### Saved goalie reports')
        for side,name in [('away',d['away']),('home',d['home'])]:
            report=extras['goalies'].get(side)
            st.write(name+': '+goalie_text(report))
            if report:st.caption('Captured '+str(report.get('captured_at_utc')))
        st.caption('Goalie reports are separate from the team-model probabilities above.')
    capture=stamp(d['capture']);at=capture.tz_convert('America/Chicago').strftime('%b %d, %Y · %-I:%M %p CT') if pd.notna(capture) else 'unavailable'
    st.caption('Prediction saved: '+at+' · Game ID: '+d['game_id']+'. The saved pick and probability stay fixed after game time.')

@st.dialog('Game details',width='large')
def open_details(payload,extras=None,now=None):
    render_details(payload,extras,now)

def details_button(sport,row,key,model_label=None,settled=None,extras=None,now=None):
    home=row.get('home',row.get('home_team'));away=row.get('away',row.get('away_team'))
    if st.button(f'Game details · {away} @ {home}',key=key,width='stretch'):
        open_details(detail_payload(sport,row,model_label,settled),extras,now)
