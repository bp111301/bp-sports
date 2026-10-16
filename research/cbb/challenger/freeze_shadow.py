"""Fit the precommitted shadow coefficients once; do not evaluate 2026."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import develop as v1
from evaluate_holdout import predict_bundle
from run import VARIANTS, extra_features, development_only
from shadow_data import load_history


def fit(frame, lock):
    if lock['training_seasons']!=list(range(2020,2025)) or lock['calibration_season']!=2025:
        raise ValueError('Unexpected locked training/calibration split')
    if not set(frame.season.unique()) <= set(range(2020,2026)):
        raise ValueError('No 2026 or future rows allowed in coefficient fitting')
    features = VARIANTS['combined']
    train = frame[frame.season.isin(lock['training_seasons'])]
    cal = frame[frame.season == lock['calibration_season']]
    if set(train.season.unique()) != set(lock['training_seasons']) or cal.empty:
        raise ValueError('Missing frozen training/calibration seasons')
    model = make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),
                          LogisticRegression(C=1.,max_iter=2000,random_state=0))
    model.fit(train[features],train.y)
    raw = model.predict_proba(cal[features])[:,1].clip(1e-8,1-1e-8)
    logits = np.log(raw/(1-raw)).reshape(-1,1)
    calibrator = LogisticRegression(C=100.,max_iter=1000,random_state=0).fit(logits,cal.y)
    bundle = dict(version=lock['version'],status='shadow_only_no_public_promotion',features=features,
                  training_seasons=lock['training_seasons'],calibration_season=lock['calibration_season'],
                  imputer=model[0].statistics_.tolist(),mean=model[1].mean_.tolist(),scale=model[1].scale_.tolist(),
                  coefficients=model[2].coef_[0].tolist(),intercept=float(model[2].intercept_[0]),
                  calibration_coefficient=float(calibrator.coef_[0,0]),
                  calibration_intercept=float(calibrator.intercept_[0]))
    expected = calibrator.predict_proba(logits)[:,1]
    np.testing.assert_allclose(predict_bundle(bundle,cal),expected,rtol=1e-12,atol=1e-12)
    return bundle


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',default='runtime/cbb');args=parser.parse_args()
    root=Path(__file__).parent;target=root/'results/shadow_bundle.json'
    if target.exists():raise SystemExit('Frozen shadow bundle exists; refusing to refit')
    lock_path=root/'SHADOW_LOCK.json';lock=json.loads(lock_path.read_text());cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
    games,players,audits=load_history(cache,range(2020,2026));development_only(games)
    original=json.loads((root.parent/'results/development.json').read_text())['data_audit']
    if [[s['sha256'] for s in a['sources']] for a in audits] != [[s['sha256'] for s in a['sources']] for a in original]:
        raise ValueError('Historical team inputs changed from V1')
    frame=v1.build_features(games).merge(extra_features(games,players),on='game_id',validate='one_to_one')
    bundle=fit(frame,lock)
    bundle.update(shadow_lock_sha256=hashlib.sha256(lock_path.read_bytes()).hexdigest(),
                  control_bundle_sha256=hashlib.sha256((root.parent/'results/candidate_bundle.json').read_bytes()).hexdigest(),
                  source_audits=audits,fit_rows=int(frame.season.isin(lock['training_seasons']).sum()),
                  calibration_rows=int(frame.season.eq(lock['calibration_season']).sum()),
                  portable_inference_verified=True)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x') as f:f.write(json.dumps(bundle,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'version':bundle['version'],'fit_rows':bundle['fit_rows'],'calibration_rows':bundle['calibration_rows'],
                      'bundle_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'no_2026_evaluation':True},indent=2))


if __name__=='__main__':main()
