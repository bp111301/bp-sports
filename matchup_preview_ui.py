"""Short editorial previews grounded in saved probabilities and sourced prior finals."""
import json,math
from pathlib import Path
import pandas as pd
import streamlit as st
from preview_data import game_id

@st.cache_data(ttl=120)
def load_previews():
    try:return json.loads((Path(__file__).parent/'data/matchup_previews.json').read_text()).get('games',{})
    except (OSError,ValueError):return {}

def valid_context(context,sport,r):
    if not context:return None
    try:
        saved=pd.to_datetime(r.get('snapshot_created_utc',r.get('created_at_utc',r.get('captured_at_utc'))),utc=True)
        captured=pd.to_datetime(context['cutoff_utc'],utc=True);start=pd.to_datetime(context['start_time_utc'],utc=True)
        if context['sport']!=sport or (context['home_team'],context['away_team'])!=(str(r['home_team']),str(r['away_team'])) or not captured<=saved<start:return None
        return context
    except (ValueError,TypeError,KeyError):return None

def form_paragraph(name,p,sport):
    if not p or not p['games']:return f'{name} has no earlier-date regular-season finals in this preview’s source window. There is not yet a recent-results sample to summarize.'
    unit='goals' if sport=='NHL' else 'points'
    record=f"{p['wins']}–{p['losses']}"+(f"–{p['ties']}" if p['ties'] else '')
    opening=f"{name} has won {p['wins']} of its {p['games']} games" if sport=='NHL' else f'{name} enters this matchup {record}'
    last=p['last'];outcome={'W':'win over','L':'loss to','T':'tie with'}[last['outcome']];high=max(last['for'],last['against']);low=min(last['for'],last['against'])
    return f"{opening} in the regular season. Its latest result was a {high:g}–{low:g} {outcome} {last['opponent']}. Across those games, {name} averaged {p['scored_per_game']:.1f} {unit} scored and {p['allowed_per_game']:.1f} allowed."

def synopsis(sport,r,context=None,model_label=None):
    home,away=str(r['home_team']),str(r['away_team'])
    if sport=='NFL':pick=str(r['v4_pick']);prob=float(r['v4_adjusted_confidence']);label='NFL V4'
    else:
        p=float(r['home_win_prob']);pick=home if p>=.5 else away;prob=max(p,1-p);label=model_label or {'CFB':'CFB V1','NHL':'NHL reference','NBA':'NBA V1'}[sport]
    if not math.isfinite(prob) or not .5<=prob<=1:return []
    opponent=away if pick==home else home;venue=context.get('venue') if context else None
    matchup=f'{away} meets {home}' if context and context.get('neutral_site') else f'{away} visits {home}'
    start=r.get('kickoff_utc',r.get('start_time_utc',context.get('start_time_utc') if context else None))
    date=pd.to_datetime(start,utc=True,errors='coerce')
    when=(' on '+date.tz_convert('America/Chicago').strftime('%A, %b %d, at %I:%M %p CT').replace(' 0',' ')) if pd.notna(date) and str(r.get('kickoff_time_tbd',False)).lower() not in ('true','1','1.0') else ''
    intro=f"{matchup}"+(f" at {venue}" if venue else '')+when+f". The saved {label} forecast favors {pick} at {prob*100:.1f}%, leaving {opponent} a {(1-prob)*100:.1f}% chance according to the model."
    paragraphs=[intro]
    if context:paragraphs.extend(form_paragraph(name,context.get(side),sport) for name,side in [(away,'away_form'),(home,'home_form')])
    else:paragraphs.append('Recent-results context is not available for this saved forecast yet. The probability above comes from the preserved prediction.')
    if sport=='NFL':
        notes=[]
        if str(r.get('explosive_extreme')).lower() in ('true','1','1.0'):notes.append('The saved explosive-play matchup reached the model’s extreme-signal threshold.')
        if str(r.get('turnover_risk_flag')).lower() in ('true','1','1.0'):notes.append('The turnover matchup reduced confidence in this pick.')
        if str(r.get('early_down_risk_flag')).lower() in ('true','1','1.0'):notes.append('Early-down efficiency also reduced confidence.')
        takeaway=' '.join(notes) or 'The saved confidence flags show no secondary adjustment to the core forecast.'
    elif sport=='CFB':takeaway='CFB V1 combines efficiency, team strength and college-football context, balancing current-season information with prior-season performance.'
    elif sport=='NHL':takeaway='This frozen research forecast combines team strength, recent results, scoring, rest and team statistics. Starting-goalie reports belong to a separate paired experiment.'
    else:takeaway='NBA V1 weighs team efficiency, recent form, rest and home-court context for regular-season games.'
    if prob<.55:takeaway+=' The probability is close to even, so the model sees only a small edge.'
    elif prob<.65:takeaway+=' The opponent still has a substantial chance to win.'
    else:takeaway+=' A stronger model preference still leaves room for an upset.'
    paragraphs.append(takeaway)
    return paragraphs

def render_preview(sport,r,model_label=None):
    context=valid_context(load_previews().get(sport+':'+game_id(r['game_id'])),sport,r)
    st.markdown('#### Matchup synopsis')
    for paragraph in synopsis(sport,r,context,model_label):st.write(paragraph)
    if context:
        cutoff=pd.to_datetime(context['cutoff_utc'],utc=True).tz_convert('America/Chicago').strftime('%b %d, %I:%M %p CT')
        st.caption(f'Recent results through the preview cutoff ({cutoff}). These describe team form; they are not individual feature contributions to the model probability.')
        if context.get('sources'):st.caption('Recent-results sources: '+' · '.join(f'[{s["name"]}]({s["url"]})' for s in context['sources']))

