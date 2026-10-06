import json, joblib, pandas as pd

def test_frozen_bundle_rules():
    b=joblib.load('model/v4/frozen_bundle.joblib')
    assert b['bundle_version']=='BP_V4_2026_FROZEN_20261005'
    assert b['market_used_for_pick'] is False
    assert set(b['risk_thresholds'])=={'explosive_last5_abs_q75','turnover_last5_abs_q75','early_success_last5_abs_q75'}

def test_week5_forward_snapshot_is_preserved():
    x=pd.read_csv('data/current/website_feed.csv')
    assert x.game_id.nunique()==len(x)
    assert {'v3_pick','v4_pick','v4_core_confidence','v4_adjusted_confidence'}.issubset(x.columns)
    assert ((x.v4_core_confidence>=.5)&(x.v4_adjusted_confidence>=.5)).all()
    assert len(x)==15

def test_config_forbids_market_pick_selection():
    c=json.load(open('model/v4/bp_v4_frozen_config.json'))
    assert c['market_in_core_model'] is False
    assert all(not v['can_flip_pick'] for v in c['confidence_layers'].values())
