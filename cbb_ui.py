"""Read-only presentation of the separately tracked CBB research candidate."""
import html
import json
from urllib.request import Request, urlopen
import pandas as pd
import streamlit as st

FEED_URL = 'https://raw.githubusercontent.com/bp111301/bp-sports/cbb-v1-research/data/cbb/prospective/dashboard.json'

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
    st.title('College basketball')
    st.caption('MEN’S DIVISION I · 2026–27 · RESEARCH PREVIEW')
    st.info('This candidate is gathering prospective evidence. Early picks use team history and prior-season stats; current roster, transfer and injury information is not included. These are estimates, never guarantees.')
    feed = load_feed()
    if feed is None:
        st.warning('The CBB research feed is unavailable. Try Refresh shortly; saved forecasts remain in the research ledger.')
        return
    updated = pd.to_datetime(feed.get('updated_at_utc'), utc=True, errors='coerce')
    if pd.notna(updated):
        st.caption('CBB feed checked '+updated.tz_convert('America/Chicago').strftime('%b %d · %-I:%M %p CT')+' · scheduled checks about every six hours')
        if pd.Timestamp.now(tz='UTC')-updated > pd.Timedelta(hours=8):
            st.warning('CBB updates are delayed. These are the last saved forecasts; source or workflow delays may take longer.')
    summary = feed.get('summary', {})
    cols = st.columns(3)
    cols[0].metric('Prospective record', f"{summary.get('wins',0)}–{summary.get('losses',0)}")
    cols[1].metric('Accuracy', f"{summary['accuracy']:.1%}" if summary.get('settled_games') and summary.get('accuracy') is not None else 'Awaiting finals')
    cols[2].metric('Pending', summary.get('pending_games',0))
    if summary.get('settled_games'):
        st.caption('Probability quality · Brier '+f"{summary['brier']:.3f}"+' · Log loss '+f"{summary['log_loss']:.3f}"+' · lower is better')
    excluded = feed.get('excluded', {})
    st.warning(f"Partial schedule coverage: {summary.get('saved_games',0)} saved games. In the latest 30-day source window, {excluded.get('tipoff_time_unconfirmed',0)} games have unconfirmed tipoff times and {excluded.get('division_or_conference_unknown',0)} have unknown eligibility. Missing teams may appear as schedules are confirmed.")
    with st.expander('About the CBB candidate'):
        st.write('Inputs include Elo, home or neutral venue, offensive and defensive efficiency, shooting, turnovers, rebounding, free throws, pace, rest and experience. Pregame snapshots are preserved; confirmed finals settle the original picks. Regular-season games only, with no preseason tests.')
        st.write('Historical 2025–26 holdout: 71.8% correct across 5,647 games. Historical testing is separate from the prospective record above.')
        st.link_button('Research report', 'https://github.com/bp111301/bp-sports/blob/cbb-v1-research/research/cbb/HANDOFF.md')
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
        with st.container(border=True):
            st.caption(start.strftime('%-I:%M %p CT') + (' · Neutral site' if row['neutral_site'] else ''))
            st.markdown('**'+html.escape(row['away_team'])+'** '+('vs.' if row['neutral_site'] else 'at')+' **'+html.escape(row['home_team'])+'**')
            st.markdown(f"**Research pick: {html.escape(row['predicted_winner'])} · {row['confidence']:.1%}**")
            st.caption(f"Home win {row['prob']:.1%} · Away win {1-row['prob']:.1%}")
            if row['status'] == 'settled':
                st.write(f"Final: {row['away_team']} {int(row['away_score'])} – {int(row['home_score'])} {row['home_team']}")
                st.success('Correct pick') if row['correct'] else st.error('Missed pick')
            else:
                st.caption('Pending result · original pregame snapshot saved')
            captured = pd.to_datetime(row['created_at_utc'], utc=True).tz_convert('America/Chicago')
            st.caption('Saved '+captured.strftime('%b %d · %-I:%M %p CT')+' · early research forecast')
    st.download_button('Download displayed picks', rows.drop(columns=['features'], errors='ignore').to_csv(index=False), 'cbb-research-picks.csv', 'text/csv')
