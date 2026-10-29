from pathlib import Path
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest

def nhl():
    return pd.DataFrame([{'game_id':1,'candidate':'a','home_win_prob':.8,
        'created_at_utc':'2026-10-26T10:00Z','start_time_utc':'2026-10-27T00:00Z',
        'settled_at_utc':'2026-10-27T03:00Z','status':'settled','actual_home_win':0},
        {'game_id':2,'candidate':'a','home_win_prob':.2,
        'created_at_utc':'2026-10-26T10:00Z','start_time_utc':'2026-10-27T00:00Z',
        'settled_at_utc':'2026-10-27T03:00Z','status':'settled','actual_home_win':0}])



def test_confidence_table_shows_observed_rate_and_limited_support():
    with patch('confidence_ui.audit_ledger') as mocked:
        from confidence_audit import audit_ledger
        mocked.return_value=audit_ledger(nhl(),'NHL','a',now='2026-10-28T23:58:00Z')
        at=AppTest.from_string("import pandas as pd\nfrom confidence_ui import render_confidence_check\nrender_confidence_check(pd.DataFrame(), 'NHL', 'a')").run()
        assert not at.exception
        assert [m.value for m in at.metric]==['80.0%','50.0%','2']
        row=at.dataframe[0].value.query('Games > 0').iloc[0]
        assert row['Actual win rate']=='50.0%' and row['Evidence']=='Limited sample'
        assert any('do not change any pick' in x.value for x in at.caption)


def test_invalid_or_empty_evidence_is_never_shown_as_confident():
    with patch('confidence_ui.audit_ledger',side_effect=ValueError('duplicate')):
        at=AppTest.from_string("import pandas as pd\nfrom confidence_ui import render_confidence_check\nrender_confidence_check(pd.DataFrame(), 'CFB')").run()
        assert not at.exception and not at.metric
        assert any('could not be verified' in x.value for x in at.warning)


def test_full_cfb_board_and_nhl_record_have_confidence_evidence():
    root=Path(__file__).resolve().parents[1]
    with patch('game_center_ui.load_scores',return_value={}):
        at=AppTest.from_file(root/'app.py',default_timeout=20)
        at.session_state['bp_sport']='CFB';at.session_state['bp_board_view']='Detailed';at.run()
        assert not at.exception
        assert any(x.label=='How reliable are these confidence levels?' for x in at.expander)
        assert sum(x.label=='Average model confidence' for x in at.metric)==2
        assert not any('STRONG' in x.value and 'tier ' in x.value for x in at.markdown)
    import nhl_ui
    records=nhl();records['home_team']='TOR';records['away_team']='DET';records['candidate']='reference_control'
    challenger=records.copy();challenger['candidate']='decay2_logistic';challenger['actual_home_win']=[1,0]
    data={'predictions':pd.concat([records,challenger]).to_dict('records'),'goalies':[]}
    with patch('nhl_ui.load_dashboard',return_value=(data,False)),patch('game_center_ui.load_scores',return_value={}):
        at=AppTest.from_file(root/'app.py',default_timeout=20)
        at.session_state['bp_sport']='NHL';at.session_state['bp_board_view']='Detailed';at.run()
        assert not at.exception
        assert at.selectbox(key='nhl_confidence_candidate').value=='reference_control'
        at.selectbox(key='nhl_confidence_candidate').set_value('decay2_logistic').run()
        assert not at.exception
        assert any(x.label=='Actual win rate' and x.value=='100.0%' for x in at.metric)


def test_missing_nhl_update_time_is_unavailable_across_dependency_versions():
    import nhl_ui
    for value in [None, '', float('nan'), 'invalid']:
        assert nhl_ui.ct(value)=='Time unavailable'
    assert 'CT' in nhl_ui.ct('2026-10-28T23:00:00Z')
