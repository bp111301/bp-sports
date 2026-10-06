import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import hashlib
import json
import platform
from datetime import datetime,timezone
import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.special import expit,logit
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss
from baseline import ROOT,FEATURES,load_games,build_features,metrics
from tournament import eligibility

HERE=Path(__file__).resolve().parent
OUT=ROOT/'research/nba/results'
MODEL=ROOT/'model/nba/v1'
NAMES=['baseline_control','tree7','tree15','blend7','blend15','linear_platt','linear_temperature','tree7_platt','tree15_platt']
TEMPERATURES=[.8,.9,1.,1.1,1.25]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def source_hashes():
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'data/nba/source').glob('*.parquet')) if int(p.stem.split('_')[-1])<=2025}

def fit_raw(train):
    linear=make_pipeline(StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=42))
    linear.fit(train[FEATURES],train.y)
    models={'linear':linear}
    for leaves in (7,15):
        tree=HistGradientBoostingClassifier(loss='log_loss',learning_rate=.05,max_iter=150,max_leaf_nodes=leaves,min_samples_leaf=60,l2_regularization=5.,early_stopping=False,random_state=42)
        tree.fit(train[FEATURES],train.y);models[f'tree{leaves}']=tree
    return models

def raw_predictions(models,features):
    p={name:model.predict_proba(features[FEATURES])[:,1] for name,model in models.items()}
    p['blend7']=(p['linear']+p['tree7'])/2;p['blend15']=(p['linear']+p['tree15'])/2
    return p

def fit_calibrator(p,y,kind):
    x=logit(np.clip(np.asarray(p),1e-8,1-1e-8))
    if kind=='platt':
        model=LogisticRegression(C=1.,max_iter=2000,random_state=42)
        model.fit(x.reshape(-1,1),y);return dict(kind=kind,model=model)
    t=min(TEMPERATURES,key=lambda t:(log_loss(y,expit(x/t),labels=[0,1]),abs(t-1),t))
    return dict(kind=kind,temperature=t)

def calibrate(p,calibrator):
    x=logit(np.clip(np.asarray(p),1e-8,1-1e-8))
    if calibrator['kind']=='platt':return calibrator['model'].predict_proba(x.reshape(-1,1))[:,1]
    return expit(x/calibrator['temperature'])

def calibration_source(name):
    if name.startswith('linear_'):return 'linear'
    if name.endswith('_platt'):return name.removesuffix('_platt')
    return None

def predict_bundle(bundle,f):
    name=bundle['selected'];p=raw_predictions(bundle['models'],f)
    source=calibration_source(name)
    if source:return calibrate(p[source],bundle['calibrator'])
    return p['linear' if name=='baseline_control' else name]

def compare(features):
    previous=[];outputs=[]
    for season in range(2018,2026):
        train=features[features.season<season];test=features[features.season==season]
        assert train.date.max()<test.date.min()
        models=fit_raw(train);raw=raw_predictions(models,test)
        prior=pd.concat(previous,ignore_index=True) if previous else None
        if season>=2019:
            for name in NAMES:
                source=calibration_source(name)
                if source:
                    assert prior.season.max()<season
                    c=fit_calibrator(prior[source],prior.y,'temperature' if name.endswith('temperature') else 'platt')
                    p=calibrate(raw[source],c)
                else:p=raw['linear' if name=='baseline_control' else name]
                row=test[['game_id','season','date','y']].copy();row['candidate']=name;row['probability']=p;row['training_last_date']=train.date.max()
                row['calibration_last_season']=int(prior.season.max()) if source else None
                outputs.append(row)
        record=test[['game_id','season','date','y']].copy()
        for name,p in raw.items():record[name]=p
        previous.append(record)
    return pd.concat(outputs,ignore_index=True),pd.concat(previous,ignore_index=True)

def main():
    MODEL.mkdir(parents=True,exist_ok=True)
    if (MODEL/'manifest.json').exists():
        m=json.loads((MODEL/'manifest.json').read_text())
        assert sha(MODEL/'frozen_bundle.joblib')==m['bundle_sha256']
        assert sha(HERE/'PROTOCOL.md')==m['protocol_sha256']
        print('Existing NBA artifact preserved; no comparison or retraining');return
    games,_=load_games();f=build_features(games);oof,raw_oof=compare(f)
    original=pd.read_csv(OUT/'baseline_oof_predictions.csv',dtype={'game_id':str})
    control=oof[oof.candidate=='baseline_control'].reset_index(drop=True)
    assert control.game_id.tolist()==original.game_id.tolist()
    np.testing.assert_allclose(control.probability,original.baseline_probability,atol=1e-12,rtol=0)
    scores={};season_rows=[]
    for name,g in oof.groupby('candidate',sort=False):
        assert g.game_id.tolist()==control.game_id.tolist() and np.array_equal(g.y,control.y)
        scores[name]={'pooled':metrics(g.y,g.probability)}
        for season,h in g.groupby('season'):
            scores[name][int(season)]=metrics(h.y,h.probability)
            season_rows.append(dict(candidate=name,season=int(season),**scores[name][int(season)]))
    board=[]
    for name in NAMES:
        checks=eligibility(scores[name],scores['baseline_control'],list(range(2019,2026))) if name!='baseline_control' else dict(eligible=False,checks={},brier_improved_seasons=0)
        board.append(dict(candidate=name,**scores[name]['pooled'],**checks))
    eligible=[r for r in board if r['eligible']]
    selected=min(eligible,key=lambda r:(r['brier'],r['log_loss'],r['candidate']))['candidate'] if eligible else 'baseline_control'
    oof.to_csv(OUT/'final_comparison_oof.csv',index=False)
    pd.DataFrame(season_rows).to_csv(OUT/'final_comparison_by_season.csv',index=False)
    summary=dict(status='development_only',candidate_count=len(NAMES),selected=selected,leaderboard=sorted(board,key=lambda r:r['brier']),holdout_evaluated=False,protocol_sha256=sha(HERE/'PROTOCOL.md'),code_sha256=sha(Path(__file__)))
    (OUT/'final_comparison_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    models=fit_raw(f);source=calibration_source(selected)
    cal=fit_calibrator(raw_oof[source],raw_oof.y,'temperature' if selected.endswith('temperature') else 'platt') if source else None
    bundle=dict(selected=selected,models=models,calibrator=cal,features=FEATURES,home_frequency=float(f.y.mean()))
    joblib.dump(bundle,MODEL/'frozen_bundle.joblib')
    manifest=dict(status='frozen_before_excluded_season',created_at=datetime.now(timezone.utc).isoformat(),selected=selected,features=FEATURES,training_games=len(f),training_seasons=sorted(int(s) for s in f.season.unique()),training_last_date=f.date.max(),excluded_season=2026,bundle_sha256=sha(MODEL/'frozen_bundle.joblib'),protocol_sha256=sha(HERE/'PROTOCOL.md'),compare_code_sha256=sha(Path(__file__)),baseline_code_sha256=sha(ROOT/'research/nba/baseline.py'),evaluation_code_sha256=sha(HERE/'evaluate.py'),source_hashes=source_hashes(),runtime=dict(python=platform.python_version(),sklearn=sklearn.__version__,numpy=np.__version__,pandas=pd.__version__,joblib=joblib.__version__),development_summary_sha256=sha(OUT/'final_comparison_summary.json'))
    (MODEL/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(pd.DataFrame(board)[['candidate','accuracy','brier','log_loss','eligible']].sort_values('brier').to_string(index=False))
    print('FROZEN:',selected,'; excluded season not downloaded')

if __name__=='__main__':main()
