import json, joblib, pandas as pd

def test_frozen_bundle_rules():
    b=joblib.load('model/v4/frozen_bundle.joblib')
    assert b['bundle_version']=='BP_V4_2026_FROZEN_20261005'
    assert b['market_used_for_pick'] is False
    assert set(b['risk_thresholds'])=={'explosive_last5_abs_q75','turnover_last5_abs_q75','early_success_last5_abs_q75'}

def test_week5_forward_snapshot_is_preserved():
    ledger=pd.read_csv('data/ledger/prediction_ledger.csv')
    x=ledger[ledger.snapshot_id.eq('BPV4_W5_EARLY_20261006T012922Z')]
    matchups={'TB_DAL','PHI_JAX','CHI_GB','CIN_MIA','LV_NE','MIN_NO','CLE_NYJ',
              'IND_PIT','HOU_TEN','NYG_WAS','DEN_LAC','DET_ARI','SF_SEA','BAL_ATL','BUF_LA'}
    assert set(x.game_id)=={'2026_05_'+game for game in matchups}
    assert x.game_id.nunique()==len(x)==15
    assert x.captured_at_utc.eq('2026-10-06T01:29:22.467309+00:00').all()
    assert x.set_index('game_id').loc['2026_05_MIN_NO','v4_pick']=='NO'
    assert x.set_index('game_id').loc['2026_05_BAL_ATL','v4_pick']=='BAL'

def test_current_slate_matches_its_metadata():
    x=pd.read_csv('data/current/website_feed.csv')
    assert x.game_id.nunique()==len(x)
    assert {'v3_pick','v4_pick','v4_core_confidence','v4_adjusted_confidence'}.issubset(x.columns)
    assert ((x.v4_core_confidence>=.5)&(x.v4_adjusted_confidence>=.5)).all()
    metadata=json.load(open('data/current/prediction_metadata.json'))
    assert len(x)==metadata['display_games']
    assert metadata['bundle_version']=='BP_V4_2026_FROZEN_20261005'

def test_config_forbids_market_pick_selection():
    c=json.load(open('model/v4/bp_v4_frozen_config.json'))
    assert c['market_in_core_model'] is False
    assert all(not v['can_flip_pick'] for v in c['confidence_layers'].values())
