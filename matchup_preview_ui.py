"""Short editorial previews grounded in saved probabilities and sourced prior finals."""
import html,json,math
from pathlib import Path
from urllib.request import Request,urlopen
import pandas as pd
import streamlit as st
from preview_data import game_id
PREVIEW_PATH=Path(__file__).parent/'data/matchup_previews.json'
PREVIEW_URL='https://raw.githubusercontent.com/bp111301/bp-sports/main/data/matchup_previews.json'

def valid_latest_context(context,sport,r,now=None):
    if not context:return None
    try:
        saved=pd.to_datetime(r.get('snapshot_created_utc',r.get('created_at_utc',r.get('captured_at_utc'))),utc=True)
        cutoff=pd.to_datetime(context['cutoff_utc'],utc=True);start=pd.to_datetime(context['start_time_utc'],utc=True)
        now=pd.Timestamp.now(tz='UTC') if now is None else pd.to_datetime(now,utc=True)
        if context['sport']!=sport or (context['home_team'],context['away_team'])!=(str(r['home_team']),str(r['away_team'])):return None
        if str(context.get('game_id'))!=game_id(r['game_id']) or not saved<=cutoff<start or cutoff>now:return None
        expected=pd.to_datetime(r.get('kickoff_utc',r.get('start_time_utc')),utc=True,errors='coerce')
        if pd.notna(expected) and start!=expected:return None
        return context
    except (ValueError,TypeError,KeyError):return None

@st.cache_data(ttl=120,show_spinner=False)
def load_previews():
    try:
        with urlopen(Request(PREVIEW_URL,headers={'User-Agent':'BP-Sports-Stories/1.0'}),timeout=8) as response:
            raw=response.read(16*1024*1024+1)
        if len(raw)>16*1024*1024:raise ValueError('Story feed too large')
        return json.loads(raw).get('games',{})
    except Exception:pass
    try:return json.loads(PREVIEW_PATH.read_text()).get('games',{})
    except (OSError,ValueError):return {}

def valid_context(context,sport,r):
    if not context:return None
    try:
        saved=pd.to_datetime(r.get('snapshot_created_utc',r.get('created_at_utc',r.get('captured_at_utc'))),utc=True)
        captured=pd.to_datetime(context['cutoff_utc'],utc=True);start=pd.to_datetime(context['start_time_utc'],utc=True)
        if context['sport']!=sport or (context['home_team'],context['away_team'])!=(str(r['home_team']),str(r['away_team'])) or not captured<=saved<start:return None
        if context.get('game_id') is not None and r.get('game_id') is not None and str(context['game_id'])!=game_id(r['game_id']):return None
        expected=pd.to_datetime(r.get('kickoff_utc',r.get('start_time_utc')),utc=True,errors='coerce')
        if pd.notna(expected) and start!=expected:return None
        return context
    except (ValueError,TypeError,KeyError):return None

def form_paragraph(name,p,sport):
    if not p or not p['games']:return f'{name} has no earlier-date regular-season finals in this preview’s source window. There is not yet a recent-results sample to summarize.'
    unit='goals' if sport=='NHL' else 'points'
    record=f"{p['wins']}–{p['losses']}"+(f"–{p['ties']}" if p['ties'] else '')
    opening=f"{name} has won {p['wins']} of its {p['games']} games" if sport=='NHL' else f'{name} enters this matchup {record}'
    last=p['last'];outcome={'W':'win over','L':'loss to','T':'tie with'}[last['outcome']];high=max(last['for'],last['against']);low=min(last['for'],last['against'])
    recent=p.get('recent',[]);form=(' Its last '+str(len(recent))+' results: '+', '.join(recent)+'.') if len(recent)>1 else ''
    return f"{opening} in the regular season. Its latest result was a {high:g}–{low:g} {outcome} {last['opponent']}. Across those games, {name} averaged {p['scored_per_game']:.1f} {unit} scored and {p['allowed_per_game']:.1f} allowed."+form

def synopsis(sport,r,context=None,model_label=None):
    home,away=str(r['home_team']),str(r['away_team'])
    if sport=='NFL':pick=str(r['v4_pick']);prob=float(r['v4_adjusted_confidence']);label='NFL V4'
    else:
        p=float(r['home_win_prob']);pick=home if p>=.5 else away;prob=max(p,1-p);label=model_label or {'CFB':'CFB V1','NHL':'NHL reference','NBA':'NBA V1','CBB':'CBB V1 candidate'}[sport]
    if not math.isfinite(prob) or not .5<=prob<=1:return []
    opponent=away if pick==home else home;venue=context.get('venue') if context else None
    matchup=f'{away} meets {home}' if context and context.get('neutral_site') else f'{away} visits {home}'
    start=r.get('kickoff_utc',r.get('start_time_utc',context.get('start_time_utc') if context else None))
    date=pd.to_datetime(start,utc=True,errors='coerce')
    if pd.isna(date) and context:date=pd.to_datetime(context.get('start_time_utc'),utc=True,errors='coerce')
    when=(' on '+date.tz_convert('America/Chicago').strftime('%A, %b %d, at %I:%M %p CT').replace(' 0',' ')) if pd.notna(date) and str(r.get('kickoff_time_tbd',False)).lower() not in ('true','1','1.0') else ''
    intro=f"{matchup}"+(f" at {venue}" if venue else '')+when+f". The saved {label} forecast favors {pick} at {prob*100:.1f}%, leaving {opponent} a {(1-prob)*100:.1f}% chance according to the model."
    paragraphs=[intro]
    if context:paragraphs.extend(form_paragraph(name,context.get(side),sport) for name,side in [(away,'away_form'),(home,'home_form')])
    else:paragraphs.append('Recent-results context is not available for this saved forecast yet. The probability above comes from the preserved prediction.')
    if context:
        hf,af=context.get('home_form') or {},context.get('away_form') or {}
        if hf.get('games') and af.get('games'):
            unit='goals' if sport=='NHL' else 'points'
            hm=hf['scored_per_game']-hf['allowed_per_game'];am=af['scored_per_game']-af['allowed_per_game']
            paragraphs.append(f"The scoring comparison: {away} carries an average differential of {am:+.1f} {unit} per game, versus {hm:+.1f} for {home}. These are raw season averages across different opponents, not an opponent-adjusted rating or a new prediction.")
    if sport=='NFL':
        notes=[]
        if str(r.get('explosive_extreme')).lower() in ('true','1','1.0'):notes.append('The saved explosive-play matchup reached the model’s extreme-signal threshold.')
        if str(r.get('turnover_risk_flag')).lower() in ('true','1','1.0'):notes.append('The turnover matchup reduced confidence in this pick.')
        if str(r.get('early_down_risk_flag')).lower() in ('true','1','1.0'):notes.append('Early-down efficiency also reduced confidence.')
        takeaway=' '.join(notes) or 'The saved confidence flags show no secondary adjustment to the core forecast.'
    elif sport=='CFB':takeaway='CFB V1 combines efficiency, team strength and college-football context, balancing current-season information with prior-season performance.'
    elif sport=='NHL':takeaway='This frozen research forecast combines team strength, recent results, scoring, rest and team statistics. Starting-goalie reports belong to a separate paired experiment.'
    elif sport=='CBB':takeaway='The CBB candidate uses prior-season team efficiency, shooting, rebounding, rest and home-court context. Current rosters, transfers and injuries are not included.'
    else:takeaway='The NBA team model weighs efficiency, recent form, rest and home court. This pick also uses verified pregame injury data.' if r.get('nba_pick_source')=='injury' else 'The NBA team model weighs efficiency, recent form, rest and home court.'
    if prob<.55:takeaway+=' The probability is close to even, so the model sees only a small edge.'
    elif prob<.65:takeaway+=' The opponent still has a substantial chance to win.'
    else:takeaway+=' A stronger model preference still leaves room for an upset.'
    paragraphs.append(takeaway)
    return paragraphs

def record_text(form,recent=False):
    if not form or not form.get('games'):return '—'
    if recent:
        results=form.get('recent_games') or []
        outcomes=[g['outcome'] for g in results] if results else form.get('recent',[])
        if not outcomes:return '—'
        wins,losses,ties=[outcomes.count(k) for k in ('W','L','T')]
        return f'{wins}–{losses}'+(f'–{ties}' if ties else '')+f' in {len(outcomes)}'
    return f"{form['wins']}–{form['losses']}"+(f"–{form['ties']}" if form.get('ties') else '')


def matchup_story(sport,r,context=None,model_label=None):
    """Pairwise story from observed results; no invented stakes or model causes."""
    base=synopsis(sport,r,context,model_label)
    if not base:return []
    if not context:return base[:2]
    away,home=str(r['away_team']),str(r['home_team']);af=context.get('away_form') or {};hf=context.get('home_form') or {}
    paragraphs=[]
    if af.get('games') and hf.get('games'):
        unit='goals' if sport=='NHL' else 'points'
        attack,defense,ap,dp=(away,home,af,hf) if af['scored_per_game']>=hf['scored_per_game'] else (home,away,hf,af)
        paragraphs.append(f"The matchup starts with {attack}’s offense: {ap['scored_per_game']:.1f} {unit} per game, against a {defense} side allowing {dp['allowed_per_game']:.1f}. At the other end, {defense} averages {dp['scored_per_game']:.1f}, while {attack} allows {ap['allowed_per_game']:.1f}. That scoring-versus-defense contrast is the thread to follow.")
        paragraphs.append(f"Across the verified regular-season results, {away} is {record_text(af)} over {af['games']} games; {home} is {record_text(hf)} over {hf['games']}. Their recent results tell another part of the story: {away} is {record_text(af,True)} and {home} is {record_text(hf,True)} across their most recent sourced games.")
    else:
        paragraphs.extend(form_paragraph(name,form,sport) for name,form in [(away,af),(home,hf)])
    meetings=context.get('previous_meetings',[])
    if meetings:
        last=meetings[0];h,a=last['home_score'],last['away_score'];date=pd.Timestamp(last['start']).tz_convert('America/Chicago').strftime('%b %-d, %Y')
        if h==a:paragraphs.append(f"Their most recent verified meeting in the checked window finished {h:g}–{a:g} on {date}.")
        else:
            winner=last['home'] if h>a else last['away'];loser=last['away'] if h>a else last['home']
            paragraphs.append(f"There is a previous meeting to look back on: {winner} beat {loser} {max(h,a):g}–{min(h,a):g} on {date}. That result gives this game context; it does not decide what happens next.")
    return paragraphs


def comparison_rows(sport,context):
    away,home=context.get('away_form') or {},context.get('home_form') or {}
    unit='Goals' if sport=='NHL' else 'Points'
    def number(form,key,sign=False):
        value=form.get(key)
        return '—' if value is None else f'{value:+.1f}' if sign else f'{value:.1f}'
    def margin(form):
        return '—' if not form.get('games') else f"{form['scored_per_game']-form['allowed_per_game']:+.1f}"
    return [('Results record',record_text(away),record_text(home)),
            (unit+' scored / game',number(away,'scored_per_game'),number(home,'scored_per_game')),
            (unit+' allowed / game',number(away,'allowed_per_game'),number(home,'allowed_per_game')),
            ('Average margin',margin(away),margin(home)),('Recent record',record_text(away,True),record_text(home,True))]


def comparison_html(sport,r,context):
    esc=lambda value:html.escape(str(value),quote=True)
    rows=comparison_rows(sport,context)
    header=f'<div class="story-compare-head" role="row"><span role="columnheader">TEAM COMPARISON</span><b role="columnheader">{esc(r["away_team"])}</b><b role="columnheader">{esc(r["home_team"])}</b></div>'
    return '<div class="story-compare" role="table" aria-label="Team comparison">'+header+''.join(f'<div class="story-compare-row" role="row"><span role="rowheader">{esc(label)}</span><strong role="cell">{esc(away)}</strong><strong role="cell">{esc(home)}</strong></div>' for label,away,home in rows)+'</div>'


def render_preview(sport,r,model_label=None):
    saved=load_previews().get(sport+':'+game_id(r['game_id']))
    latest=valid_latest_context((saved or {}).get('latest_context'),sport,r)
    context=latest or valid_context(saved,sport,r)
    st.markdown('#### Matchup synopsis · The storyline')
    if context and context.get('venue'):st.caption(context['venue']+(' · Neutral site' if context.get('neutral_site') else ''))
    for paragraph in matchup_story(sport,r,context,model_label):st.write(paragraph)
    if context:
        st.markdown(comparison_html(sport,r,context),unsafe_allow_html=True)
        st.caption('Regular-season results before game day. Teams face different schedules; these averages are not adjusted for opponent strength.')
        st.markdown('##### How they got here')
        for side,name in [('away_form',r['away_team']),('home_form',r['home_team'])]:
            form=context.get(side) or {};recent=form.get('recent_games') or ([form['last']] if form.get('last') else [])
            with st.expander(str(name)+' · recent games',expanded=False):
                if not recent:st.caption('No earlier verified results available.')
                for g in recent[:5]:
                    date=pd.Timestamp(g['start']).tz_convert('America/Chicago').strftime('%b %-d')
                    st.write(f"{date} · {g['outcome']} · {g['for']:g}–{g['against']:g} vs {g['opponent']}")
        if not context.get('previous_meetings'):st.caption('No previous meeting was available in the checked source window.')
        cutoff=pd.to_datetime(context['cutoff_utc'],utc=True).tz_convert('America/Chicago').strftime('%b %d, %I:%M %p CT')
        with st.expander('Sources & context'):
            st.caption(f'Results cutoff: {cutoff}. '+('Updated separately from the original prediction. ' if latest else '')+'Earlier-date regular-season finals only. This story describes team form; it does not explain individual model feature contributions or change the saved pick.')
            observed=pd.to_datetime(context.get('observed_at_utc'),utc=True,errors='coerce')
            if pd.notna(observed) and observed>=pd.to_datetime(context['start_time_utc'],utc=True):
                st.caption('Historical game context reconstructed from prior results; this is not an original pregame input receipt.')
            for source in context.get('sources',[]):st.link_button(source['name'],source['url'])

