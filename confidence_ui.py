"""Display empirical reliability separately from frozen game probabilities."""
import pandas as pd
import streamlit as st
from confidence_audit import audit_ledger


def render_confidence_check(frame, sport, candidate=None, now=None):
    st.markdown('#### Confidence check')
    st.caption('Saved model percentages compared with settled pregame results. These summaries do not change any pick or percentage.')
    try:
        report = audit_ledger(frame, sport, candidate, now)
    except (ValueError, TypeError, KeyError):
        st.warning('Confidence evidence is unavailable because this ledger could not be verified.')
        return
    m = report['overall']
    if not m['games']:
        st.info('No verified settled games are available for this model’s confidence check yet.')
        return
    cols = st.columns(3)
    cols[0].metric('Average model confidence', f'{m["mean_confidence"]:.1%}')
    cols[1].metric('Actual win rate', f'{m["accuracy"]:.1%}')
    cols[2].metric('Graded games', str(m['games']))
    gap = m['confidence_minus_accuracy']*100
    st.caption(f'Model confidence minus actual win rate: {gap:+.1f} percentage points. Positive means the model has been overconfident in this sample.')
    rows = []
    for b in report['buckets']:
        n = b['games']
        rows.append({'Model confidence':b['bucket'], 'Games':n,
            'Average estimate':f'{b["mean_confidence"]:.1%}' if n else '—',
            'Actual win rate':f'{b["accuracy"]:.1%}' if n else '—',
            '95% win-rate interval':f'{b["accuracy_ci95"][0]:.1%}–{b["accuracy_ci95"][1]:.1%}' if n else '—',
            'Evidence':'No settled games' if not n else 'Limited sample' if b['limited_sample'] else 'Descriptive only'})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption('Intervals describe each bucket’s observed win rate, not a particular game’s chance. They assume independent games; shared game-day effects can add uncertainty. Fewer than 100 games is a limited sample. No bucket is a guaranteed pick.')
    st.caption(f'As of {report["as_of_utc"]} • {report["pending_games"]} pending games excluded • First saved forecasts only.')
