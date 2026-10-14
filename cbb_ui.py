"""Read-only presentation of the separately tracked CBB research candidate."""
import html
import json
from urllib.request import Request, urlopen
import pandas as pd
import streamlit as st

FEED_URL = 'https://raw.githubusercontent.com/bp111301/bp-sports/cbb-v1-research/data/cbb/prospective/dashboard.json'
UI_REVISION = 'cbb-board-20261013'

def team_block(name, home=False):
    words = str(name).replace('–', ' ').split()
    initials = ''.join(word[0] for word in words[:3]).upper()
    badge = f'<div class="team-dot" style="background:#315d96">{html.escape(initials)}</div>'
    text = f'<div><div class="team-abbr">{html.escape(initials)}</div><div class="team-name">{html.escape(str(name))}</div></div>'
    return f'<div class="team-box{" home" if home else ""}">{text+badge if home else badge+text}</div>'

def card_html(row):
    p = float(row['prob']); confidence = float(row['confidence'])
    tier, css, accent = ('STRONG','tier-strong','#44d17a') if confidence >= .7 else ('SOLID','tier-solid','#6ea8fe') if confidence >= .6 else ('LEAN','tier-lean','#f5c451') if confidence >= .55 else ('TOSS-UP','tier-toss','#ff6b7a')
    start = row['start'].tz_convert('America/Chicago')
    settled = row['status'] == 'settled'
    state = ('WIN' if row['correct'] else 'LOSS') if settled else 'PENDING'
    result = f"{html.escape(row['away_team'])} {int(row['away_score'])} – {int(row['home_score'])} {html.escape(row['home_team'])}" if settled else 'Result pending · excluded from record'
    captured = pd.to_datetime(row['created_at_utc'], utc=True).tz_convert('America/Chicago').strftime('%b %d · %-I:%M %p CT')
    note = 'Early forecast · current roster and injuries are not included.'
    if confidence >= .9: note += ' Unusually high estimate; no live evidence at this confidence level yet.'
    return f'''<div class="card" style="border-left-color:{accent}">
      <div class="card-top"><div class="game-meta">{start.strftime('%a %b %d · %-I:%M %p CT')} · {state}</div><div class="tier {css}">{tier}</div></div>
      <div class="match-row">{team_block(row['away_team'])}<div class="at">{'VS' if row['neutral_site'] else '@'}</div>{team_block(row['home_team'],True)}</div>
      <div class="pick-panel"><div><div class="pick-label">B.P. SPORTS CBB V1 CANDIDATE PICK</div><div class="pick-name">{html.escape(row['predicted_winner'])}</div></div><div class="prob">{confidence:.1%}<span>WIN CONFIDENCE</span></div></div>
      <div class="bar"><div class="fill" style="width:{confidence*100:.1f}%"></div></div>
      <div class="badges"><span class="badge badge-lock">PREGAME SNAPSHOT</span><span class="badge">MARKET-FREE PICK</span>{'<span class="badge">NEUTRAL SITE</span>' if row['neutral_site'] else ''}</div>
      <div class="model-strip"><div class="model-cell"><div class="m">AWAY WIN</div><div class="v">{1-p:.1%}</div></div><div class="model-cell"><div class="m">HOME WIN</div><div class="v">{p:.1%}</div></div><div class="model-cell"><div class="m">MODEL</div><div class="v">CBB V1 candidate</div></div></div>
      <div class="layer-note">{result}</div><div class="bp-confidence"><span>{note}</span></div>
      <div class="layer-note">Saved {captured}</div>
    </div>'''

@st.cache_data(ttl=60)
def load_feed():
    try:
        with urlopen(Request(FEED_URL, headers={'User-Agent': 'BP-Sports-CBB-UI/1.0'}), timeout=8) as response:
            feed = json.loads(response.read(4*1024*1024))
        if feed.get('feed_status') != 'research_preview' or not isinstance(feed.get('predictions'), list):
            return None
        return feed
    except (OSError, ValueError):
        return None

def board_rows(feed):
    rows = pd.DataFrame(feed.get('predictions', []))
    if rows.empty:
        return rows
    rows['start'] = pd.to_datetime(rows['start_time_utc'], utc=True, errors='coerce')
    rows['prob'] = pd.to_numeric(rows['home_win_prob'], errors='coerce')
    rows = rows[rows['start'].notna() & rows['prob'].between(0, 1)].copy()
    rows['date'] = rows['start'].dt.tz_convert('America/Chicago').dt.strftime('%Y-%m-%d')
    rows['confidence'] = rows['prob'].where(rows['prob'] >= .5, 1-rows['prob'])
    return rows.sort_values(['start', 'game_id'], kind='stable')

def render_cbb():
    st.markdown('<style>.cbb-hero{background:radial-gradient(ellipse at 100% 0,rgba(212,124,44,.19),transparent 60%),linear-gradient(135deg,#1d202a,#10151e)}.cbb-hero .eyebrow{color:#f7ad68}</style>',unsafe_allow_html=True)
    feed = load_feed()
    if feed is None:
        st.warning('The CBB research feed is unavailable. Try Refresh shortly; saved forecasts remain in the research ledger.')
        return
    updated = pd.to_datetime(feed.get('updated_at_utc'), utc=True, errors='coerce')
    if pd.notna(updated):
        st.caption('CBB feed checked '+updated.tz_convert('America/Chicago').strftime('%b %d · %-I:%M %p CT')+' · scheduled checks about every six hours')
        if pd.Timestamp.now(tz='UTC')-updated > pd.Timedelta(hours=8):
            st.warning('CBB updates are delayed. These are the last saved forecasts; source or workflow delays may take longer.')
    board_tab, record_tab, model_tab = st.tabs(['PREDICTIONS', 'MODEL RECORD', 'THE MODEL'])
    summary = feed.get('summary', {})
    with record_tab:
        render_record(summary)
    with model_tab:
        render_model()
    with board_tab:
        render_board(feed)

def render_record(summary):
    st.markdown(f'<div class="record-hero"><div class="record-label">CBB V1 CANDIDATE · PROSPECTIVE RECORD</div><div class="record-big">{summary.get("wins",0)}–{summary.get("losses",0)}</div><div class="section-sub">{summary.get("settled_games",0)} graded games · {summary.get("pending_games",0)} pending snapshots</div></div>', unsafe_allow_html=True)
    cols = st.columns(3)
    cols[0].metric('Prospective record', f"{summary.get('wins',0)}–{summary.get('losses',0)}")
    cols[1].metric('Accuracy', f"{summary['accuracy']:.1%}" if summary.get('settled_games') and summary.get('accuracy') is not None else 'Awaiting finals')
    cols[2].metric('Pending', summary.get('pending_games',0))
    if summary.get('settled_games'):
        st.caption('Probability quality · Brier '+f"{summary['brier']:.3f}"+' · Log loss '+f"{summary['log_loss']:.3f}"+' · lower is better')
    st.caption('Pending games do not count toward accuracy. Historical testing is separate from this prospective record.')

def render_model():
    st.subheader('CBB V1 candidate')
    st.write('The fixed candidate passed its locked historical gate. It is collecting live evidence before promotion to an official model.')
    st.write('Inputs include Elo, home or neutral venue, offensive and defensive efficiency, shooting, turnovers, rebounding, free throws, pace, rest and experience. Data comes from SportsDataverse’s ESPN schedules and team box scores.')
    st.info('Early forecasts use team history and prior-season statistics. Current roster, transfer and injury information is not included. A probability is an estimate, never a guarantee.')
    st.write('Pregame snapshots are preserved; confirmed finals settle the original picks. Regular-season games only, with no preseason tests.')
    st.markdown('<div class="record-hero"><div class="record-label">2025–26 · LOCKED HISTORICAL HOLDOUT</div><div class="record-big">71.8%</div><div class="section-sub">4,052 correct picks across 5,647 games · Brier 0.185 · log loss 0.546</div></div>', unsafe_allow_html=True)
    st.caption('Historical accuracy is not a live record or a promise of future performance.')
    st.link_button('Read the model report', 'https://github.com/bp111301/bp-sports/blob/cbb-v1-research/research/cbb/HANDOFF.md')

def render_board(feed):
    summary = feed.get('summary', {})
    excluded = feed.get('excluded', {})
    st.markdown(f'''<div class="hero cbb-hero"><div class="eyebrow">2026–27 · REGULAR SEASON · CBB V1 CANDIDATE</div><div class="hero-title">The B.P. Sports CBB Board</div><div class="hero-copy">A fixed team model built on efficiency, shooting, rebounding, rest and home-court context. Follow timestamped pregame picks and their results as the season begins.</div><div class="stat-grid"><div class="stat"><div class="stat-v">{summary.get('wins',0)}–{summary.get('losses',0)}</div><div class="stat-l">Prospective record</div></div><div class="stat"><div class="stat-v">{summary.get('settled_games',0)}</div><div class="stat-l">Live games graded</div></div><div class="stat"><div class="stat-v">71.75%</div><div class="stat-l">2025–26 historical test</div></div><div class="stat"><div class="stat-v">Testing</div><div class="stat-l">Candidate status</div></div></div></div>''', unsafe_allow_html=True)
    st.subheader('Full CBB slate')
    st.caption('Games are sorted by date and tipoff · Central time. Early forecasts use prior-season team history; roster and injuries are not included.')
    with st.expander('Schedule coverage · more games will appear as times are confirmed'):
        st.write(f"{summary.get('saved_games',0)} saved games. In the latest 30-day source window, {excluded.get('tipoff_time_unconfirmed',0)} games have unconfirmed tipoff times and {excluded.get('division_or_conference_unknown',0)} have unknown eligibility. This is a partial schedule.")
    rows = board_rows(feed)
    if rows.empty:
        st.info('No eligible saved games yet.')
        return
    search = st.text_input('Search teams', placeholder='Texas Tech, Arizona, UCLA…', key='cbb_search')
    dates = ['All dates'] + list(dict.fromkeys(rows['date']))
    chosen = st.selectbox('Game date · Central time', dates, key='cbb_date')
    state = st.selectbox('Results', ['All games', 'Pending', 'Settled'], key='cbb_state')
    if chosen != 'All dates': rows = rows[rows['date'] == chosen]
    if search: rows = rows[rows['home_team'].str.contains(search, case=False, regex=False) | rows['away_team'].str.contains(search, case=False, regex=False)]
    if state != 'All games': rows = rows[rows['status'] == state.lower()]
    from game_center_ui import filter_favorites
    rows = filter_favorites(rows, 'CBB', 'cbb_favorites')
    if rows.empty: st.info('No saved games match these filters.')
    last_date = None
    for _, row in rows.iterrows():
        start = row['start'].tz_convert('America/Chicago')
        if row['date'] != last_date:
            st.subheader(start.strftime('%A, %B %-d'))
            last_date = row['date']
        st.markdown(card_html(row), unsafe_allow_html=True)
    st.download_button('Download displayed picks', rows.drop(columns=['features'], errors='ignore').to_csv(index=False), 'cbb-research-picks.csv', 'text/csv')
