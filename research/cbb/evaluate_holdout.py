"""One-time evaluation of the precommitted CBB candidate. Refuse overwrites."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from develop import BASE, FEATURES, build_features, develop, score, season_games


def gate(report, lock):
    models=report['models']; candidate=models['team_stats']; reference=models['elo_logistic']; rules=lock['historical_gate']
    return dict(
        sample=candidate['games']>=rules['minimum_games'],
        accuracy=candidate['accuracy']>=models['elo']['accuracy'],
        brier=candidate['brier']<=reference['brier'],
        log_loss=candidate['log_loss']<=reference['log_loss'],
        neutral_sample=candidate['neutral']['games']>=rules['minimum_neutral_games'],
        neutral_brier=candidate['neutral']['brier']<=reference['neutral']['brier']+rules['neutral_brier_max_excess_over_calibrated_elo'],
        early_sample=candidate['early_season']['games']>=rules['minimum_early_season_games'],
        early_brier=candidate['early_season']['brier']<=reference['early_season']['brier']+rules['early_season_brier_max_excess_over_calibrated_elo'])


def fit_bundle(frame, lock):
    train=frame[frame.season.isin(lock['training_seasons'])];cal=frame[frame.season.eq(lock['calibration_season'])]
    model=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0))
    model.fit(train[FEATURES],train.y)
    probabilities=model.predict_proba(cal[FEATURES])[:,1].clip(1e-8,1-1e-8)
    calibrator=LogisticRegression(C=100.,max_iter=1000,random_state=0).fit(np.log(probabilities/(1-probabilities)).reshape(-1,1),cal.y)
    return dict(version=lock['version'],features=FEATURES,training_seasons=lock['training_seasons'],calibration_season=lock['calibration_season'],
                imputer=model[0].statistics_.tolist(),mean=model[1].mean_.tolist(),scale=model[1].scale_.tolist(),
                coefficients=model[2].coef_[0].tolist(),intercept=float(model[2].intercept_[0]),
                calibration_coefficient=float(calibrator.coef_[0,0]),calibration_intercept=float(calibrator.intercept_[0]))


def predict_bundle(bundle, frame):
    x=frame[bundle['features']].to_numpy(dtype=float)
    x=np.where(np.isnan(x),np.array(bundle['imputer']),x)
    x=(x-np.array(bundle['mean']))/np.array(bundle['scale'])
    z=x@np.array(bundle['coefficients'])+bundle['intercept']
    raw=1/(1+np.exp(-z));raw=raw.clip(1e-8,1-1e-8)
    logits=np.log(raw/(1-raw))*bundle['calibration_coefficient']+bundle['calibration_intercept']
    return 1/(1+np.exp(-logits))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',default='runtime/cbb');parser.add_argument('--output',default='research/cbb/results/holdout_2026.json')
    args=parser.parse_args();output=Path(args.output)
    if output.exists():raise SystemExit('Holdout already evaluated: refusing to overwrite or rerun it.')
    lock_path=Path(__file__).with_name('EVALUATION_LOCK.json');lock=json.loads(lock_path.read_text())
    if lock['features']!=FEATURES or lock['holdout_season']!=2026:raise ValueError('Evaluation lock mismatch')
    cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:seasons=list(pool.map(lambda year:season_games(year,cache),range(2020,2027)))
    frame=build_features([g for games,_ in seasons for g in games])
    report,predictions=develop(frame,2026)
    report.pop('untouched_holdout_season',None)
    report['holdout_season']=2026
    report['evaluation_type']='previously untouched final holdout'
    early=pd.to_datetime(predictions.start,utc=True).dt.tz_convert('America/Chicago').dt.month.eq(11).to_numpy()
    for name in report['models']:
        report['models'][name]['early_season']=score(predictions.y.to_numpy()[early],predictions[name].to_numpy()[early])
    checks=gate(report,lock)
    bundle=fit_bundle(frame,lock)
    test=frame[frame.season.eq(2026)]
    np.testing.assert_allclose(predict_bundle(bundle,test),predictions.team_stats.to_numpy(),rtol=1e-12,atol=1e-12)
    report.update(status='passed_historical_gate_pending_live_validation' if all(checks.values()) else 'failed_historical_gate',
                  gate_checks=checks,evaluation_lock_sha256=hashlib.sha256(lock_path.read_bytes()).hexdigest(),data_audit=[a for _,a in seasons],
                  evaluated_at_utc=pd.Timestamp.now(tz='UTC').isoformat())
    # Approximate game-level paired bootstrap; team/time dependence is not modeled.
    y=predictions.y.to_numpy();p=predictions.team_stats.to_numpy();base=predictions.elo.to_numpy()
    delta=((p>=.5)==y).astype(float)-((base>=.5)==y).astype(float)
    rng=np.random.default_rng(0);samples=np.array([rng.choice(delta,len(delta),replace=True).mean() for _ in range(2000)])
    report['accuracy_improvement_over_elo']={'difference':float(delta.mean()),'approximate_game_bootstrap_95_interval':np.quantile(samples,[.025,.975]).tolist(),'limitation':'Games share teams and time; interval is descriptive, not a formal independence-adjusted significance test.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    predictions.to_csv(output.with_name('holdout_2026_predictions.csv'),index=False)
    bundle['status']=report['status'];bundle['evaluation_lock_sha256']=report['evaluation_lock_sha256']
    output.with_name('candidate_bundle.json').write_text(json.dumps(bundle,indent=2)+'\n')
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'gate_checks':checks,'models':{k:{m:v[m] for m in ['games','accuracy','brier','log_loss']} for k,v in report['models'].items()}},indent=2))


if __name__=='__main__':main()
