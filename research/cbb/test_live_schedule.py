import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from live_schedule import merge_schedule, normalize, supplement
from prospective import targets


def fixture():
    return json.loads((Path(__file__).parent/'fixtures/opening_20261101.json').read_text())


def test_openers_missing_from_archive_are_eligible_and_keep_central_date():
    rows = normalize(fixture())
    archive = rows.iloc[:0].copy()
    merged = merge_schedule(archive, rows)
    games, _, exclusions = targets(merged, pd.Timestamp('2026-10-30T01:00Z'))
    assert not exclusions
    assert {g['game_id'] for g in games} == {'401920982', '401920409'}
    assert all(g['neutral'] for g in games)
    assert all(g['start'].tz_convert('America/Chicago').strftime('%Y-%m-%d') == '2026-11-01' for g in games)


def test_live_schedule_updates_unconfirmed_archive_but_rejects_identity_conflict():
    rows = normalize(fixture())
    archive = rows.copy()
    archive['time_valid'] = False
    archive['away_non_div1_team'] = False
    merged = merge_schedule(archive, rows)
    assert merged.time_valid.all()
    assert not merged.away_non_div1_team.any()
    bad = rows.copy()
    bad.loc[0, 'home_id'] = 999
    with pytest.raises(ValueError, match='identity mismatch'):
        merge_schedule(archive, bad)


def test_unconfirmed_times_and_unknown_eligibility_still_excluded():
    payload = copy.deepcopy(fixture())
    payload['events'][0]['competitions'][0]['timeValid'] = False
    payload['events'][1]['competitions'][0]['competitors'][1]['team']['conferenceId'] = None
    games, _, exclusions = targets(normalize(payload), pd.Timestamp('2026-10-30T01:00Z'))
    assert not games
    assert exclusions == {'tipoff_time_unconfirmed':1, 'division_or_conference_unknown':1}


def test_neutral_side_reversal_retains_archive_orientation_and_maps_scores():
    rows = normalize(fixture()).iloc[:1].copy()
    reversed_rows = rows.copy()
    for suffix in ['id','display_name','conference_id','score']:
        reversed_rows['home_'+suffix] = rows['away_'+suffix]
        reversed_rows['away_'+suffix] = rows['home_'+suffix]
    reversed_rows['home_score'] = 60
    reversed_rows['away_score'] = 70
    merged = merge_schedule(rows, reversed_rows)
    assert merged.iloc[0].home_id == rows.iloc[0].home_id
    assert merged.iloc[0].home_score == 70
    assert merged.iloc[0].away_score == 60
    reversed_rows['neutral_site'] = False
    with pytest.raises(ValueError, match='identity mismatch'):
        merge_schedule(rows, reversed_rows)


def test_receipts_use_schedule_fields_only_and_pending_dates_are_rechecked():
    payload = fixture()
    payload['events'][0]['competitions'][0]['odds'] = [{'details':'unused'}]
    seen = []
    def fetcher(url):
        seen.append(url)
        return payload if 'dates=20261101&' in url else {'events':[]}
    rows, receipt = supplement(normalize(fixture()).iloc[:0], {'sha256':'archive'},
                               pd.Timestamp('2026-11-10T00:00Z'),
                               [{'status':'pending', 'start_time_utc':'2026-11-01T14:30Z'}], fetcher)
    assert len(rows) == 2
    assert any('dates=20261101&' in url for url in seen)
    assert receipt['archive_sha256'] == 'archive'
    assert 'odds' not in rows.columns
    assert 'unused' not in json.dumps(receipt)


def test_conflicting_identity_is_quarantined_without_losing_other_openers():
    archive = normalize(fixture()).iloc[:1].copy()
    archive.loc[0, 'home_id'] = 999
    rows, receipt = supplement(archive, {'sha256':'archive'}, pd.Timestamp('2026-10-30T00:00Z'),
        fetcher=lambda url: fixture() if 'dates=20261101&' in url else {'events':[]})
    assert set(rows.game_id) == {401920409}
    assert receipt['identity_conflicts'][0]['game_id'] == 401920982
