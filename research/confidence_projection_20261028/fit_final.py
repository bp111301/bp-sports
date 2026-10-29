"""Final fixed research bundles. No evaluation, live forecasts or production writes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'runtime/confidence_projection_20261028/final_bundles'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

e=module('freeze_features',HERE.parent/'feature_challengers_20261028/experiment.py')
s=module('freeze_strength',HERE.parent/'strength_challengers_20261028/experiment.py')
projection=module('freeze_projection',HERE/'evaluate.py')


def predict_features(bundle,features,reference_probability):
    """Caller must supply same-time, provenance-checked pregame features/reference."""
    columns=bundle['feature_columns']
    if list(features.columns)!=columns:raise ValueError('Exact frozen feature order required')
    reference=np.asarray(reference_probability,float)
    if reference.shape!=(len(features),) or not np.isfinite(reference).all() or ((reference<0)|(reference>1)).any():raise ValueError('Invalid same-time reference probability')
    values=features.to_numpy(float)
    if np.isinf(values).any():raise ValueError('Infinite input feature')
    raw=bundle['model'].predict_proba(features)[:,1]
    proposed=.5*reference+.5*raw if bundle['sport']=='cfb' else raw
    adjusted=projection.project(reference,proposed)
    if not np.array_equal(adjusted>=.5,reference>=.5):raise ValueError('Reference pick changed')
    return adjusted


def fit(sport):
    if sport=='cfb':
        d=e.cfb.guarded_data(ROOT/'runtime/challengers_20261028/cfb/matchup_line')
        x,px,cf,pf=e.cfb.matrices(d)
        games=d.rename(columns={'start_date':'date','home_team_id':'home_id','away_team_id':'away_id','home_points':'home_score','away_points':'away_score'}).copy();games['home_field']=x.home_field
        strength,boundaries=s.strength_features(games,'cfb');px['strength_diff']=strength.strength_diff
        columns=pf+['strength_diff'];features=px[columns];model=s.nonlinear();max_season=2025
        source_dir=ROOT/'runtime/challengers_20261028/cfb/matchup_line'
    else:
        source_dir=ROOT/'runtime/confidence_projection_20261028/final_nhl_sources'
        wanted=[str(y)+str(y+1) for y in range(2018,2026)]
        if sorted(p.stem.split('_')[-1] for p in source_dir.glob('summary_*.csv'))!=wanted:raise ValueError('Final NHL fit requires exact registered seasons')
        t=e.nhl.adv.load_team_stats(source_dir)
        if not t.season.astype(str).isin(wanted).all() or t.duplicated(['season','gameId','teamId']).any():raise ValueError('Invalid final NHL source')
        d=e.nhl.historical_games(t);x,af=e.nhl.adv.attach(d,e.nhl.base.build_features(d),t,20)
        extra,boundaries=e.pooled_rates(d,t)
        retain=[f for f in af if not any(k in f for k in ['shoot_pct','save_pct','pp_rate','pk_rate'])]
        columns=e.nhl.base.FEATURES+retain+list(extra);features=x.join(extra)[columns]
        model=e.nhl.learner(columns,False);max_season='20252026'
    if str(d.season.max())!=str(max_season):raise ValueError('Unexpected final training cutoff')
    model.fit(features,d.home_win)
    bundle={'version':'confidence_only_research_20261028','sport':sport,'model':model,'feature_columns':columns,'training_season_max':str(max_season),'training_rows':len(d),'production_promoted':False,'same_time_shadow_started':False,'required_new_paired_finals':200 if sport=='cfb' else 300,'environment':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__}}
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/f'{sport}.joblib';joblib.dump(bundle,path,compress=3)
    reloaded=joblib.load(path);sample=features.iloc[np.linspace(0,len(features)-1,128,dtype=int)]
    # Deliberately arbitrary fixed reference probes; no labels or scoring involved.
    reference=np.linspace(.01,.99,len(sample));a=predict_features(bundle,sample,reference);b=predict_features(reloaded,sample,reference)
    if not np.array_equal(a,b):raise ValueError('Artifact reload changed predictions')
    if not np.array_equal(a>=.5,reference>=.5):raise ValueError('Artifact smoke test changed winners')
    metadata={k:v for k,v in bundle.items() if k!='model'}
    metadata.update(artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),protocol_sha256=hashlib.sha256((HERE/'FINAL_FIT_PROTOCOL.md').read_bytes()).hexdigest(),fit_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_file_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_dir.glob('*.csv'))},reload_predictions_byte_identical=True,reload_smoke_rows=len(sample),reference_winners_preserved=True,performance_evaluated_on_final_training=False)
    (OUT/f'{sport}.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (OUT/f'{sport}_temporal_boundaries.json').write_text(json.dumps(boundaries,indent=2)+'\n')
    print(json.dumps({k:v for k,v in metadata.items() if k!='source_file_sha256'},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sport',choices=['cfb','nhl'],required=True);a=p.parse_args();fit(a.sport)
