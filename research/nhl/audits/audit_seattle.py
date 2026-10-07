"""Read-only attribution of the saved Seattle forecast; never fits or edits a model."""
from pathlib import Path
import hashlib,json,warnings,importlib.metadata
import joblib,numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[3]

def main():
    manifest=json.loads((ROOT/'model/nhl/v2_research/manifest.json').read_text())
    path=ROOT/'model/nhl/v2_research/watchlist.joblib'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['bundle_sha256']:raise ValueError('Frozen bundle hash mismatch')
    pairs=[json.loads(line) for line in (ROOT/'data/nhl/goalie_experiment/paired_ledger.jsonl').read_text().splitlines()]
    pair=next(r for r in pairs if r['game_id']==2026020051)
    if pair['reference_bundle_sha256']!=manifest['bundle_sha256']:raise ValueError('Snapshot bundle mismatch')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore');bundle=joblib.load(path)
    x=pd.DataFrame([{k:np.nan if v is None else v for k,v in pair['feature_snapshot']['team_features'].items()}])
    m=bundle['reference'];v=m['prep'].transform(x)[0];names=list(m['prep'].get_feature_names_out());coef=m['model'].coef_[0]
    p=float(m.predict_proba(x)[0,1]);saved=pair['probabilities']['team_control']
    if abs(p-saved)>1e-12:raise ValueError('Saved probability did not reproduce')
    idx=names.index('num__missingindicator_pp_rate_20_diff');scale=m['prep'].transformers_[0][1]['scale'].scale_[idx]
    effect=float(coef[idx]/scale);logit=float(m['model'].intercept_[0]+v@coef)
    ledger=pd.read_csv(ROOT/'data/nhl/v2_research/prediction_ledger.csv');saved_rows=ledger[ledger.game_id.eq(2026020051)]
    if abs(float(saved_rows[saved_rows.candidate.eq('reference_control')].iloc[0].home_win_prob)-p)>1e-12:raise ValueError('Watchlist differs from paired snapshot')
    print(json.dumps({'game_id':2026020051,'snapshot_created_utc':pair['created_at_utc'],'bundle_sha256':manifest['bundle_sha256'],'package_versions':{k:importlib.metadata.version(k) for k in ['numpy','pandas','scikit-learn','scipy','joblib']},'frozen_package_versions':manifest['package_versions'],'reference_reproduced':p,'decay_reproduced':float(bundle['decay'].predict_proba(x)[0,1]),'missing_pp_flag_log_odds_effect':effect,'diagnostic_probability_with_only_missing_pp_flag_disabled':float(1/(1+np.exp(-(logit-effect)))),'diagnostic_only_not_a_new_forecast':True,'contributions':sorted([{'feature':n,'scaled_value':float(a),'coefficient':float(c),'log_odds_contribution':float(a*c)} for n,a,c in zip(names,v,coef)],key=lambda r:abs(r['log_odds_contribution']),reverse=True)},indent=2))
if __name__=='__main__':main()
