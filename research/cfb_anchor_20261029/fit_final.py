"""Fit the single development-qualified research recipe; never touch V1 weights."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import joblib,numpy as np,pandas as pd,sklearn,catboost
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
s=module('anchor_structure',HERE.parent/'structural_challengers_20261028/experiment.py')
a=module('anchor_transform',HERE/'evaluate.py')

def raw_probability(bundle,raw):
 if list(raw.columns)!=bundle['raw_feature_columns']:raise ValueError('Frozen raw feature columns/order changed')
 numeric=bundle['numeric_features'];cats=bundle['categorical_features'];z=pd.DataFrame(bundle['imputer'].transform(raw[numeric]),index=raw.index,columns=numeric)
 for c in cats:z[c]=raw[c].fillna('__missing__').astype(str)
 if np.isinf(raw[numeric].to_numpy(float)).any():raise ValueError('Infinite numerical source feature')
 p=bundle['model'].predict_proba(z[bundle['model_feature_columns']])[:,1]
 if not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid frozen tree probability')
 return p

def predict(bundle,raw,reference):
 r=np.asarray(reference,float);p=raw_probability(bundle,raw);q=.5*r+.5*p
 return a.anchor(r,q),q,p

def run():
 result=json.loads((HERE/'results/results.json').read_text())
 if not result['decisions'][a.NAME]['research_eligible']:raise ValueError('Unqualified recipe cannot be frozen for this trial')
 if catboost.__version__!='1.2.8':raise ValueError('Wrong registered CatBoost version')
 d=s.e.cfb.guarded_data(ROOT/'runtime/challengers_20261028/cfb/matchup_line');x,cats,_=s.cfb_features(d)
 if int(d.season.max())!=2025 or int(d.season.min())!=2015:raise ValueError('Wrong final training boundary')
 tr=d.sort_values(['start_date','game_id']).index;sample=tr[np.linspace(0,len(tr)-1,128,dtype=int)];train,_,imputer,numeric=s.prepare(x,tr,sample,cats)
 model=s.CatBoostClassifier(**s.params(5,5));model.fit(train,d.loc[tr,'home_win'],cat_features=cats)
 bundle={'version':'CFB_ANCHOR_20261029','model':model,'imputer':imputer,'numeric_features':numeric,'categorical_features':cats,'raw_feature_columns':list(x),'model_feature_columns':list(train),'training_first_season':2015,'training_last_season':2025,'training_games':len(d),'production_promoted':False}
 out=HERE/'final_bundle';out.mkdir(parents=True,exist_ok=True);path=out/'challenger.joblib';joblib.dump(bundle,path,compress=3);reloaded=joblib.load(path)
 reference=np.linspace(.01,.99,len(sample));p,q,tree=predict(bundle,x.loc[sample],reference);rp,rq,rt=predict(reloaded,x.loc[sample],reference)
 if not np.array_equal(p,rp) or not np.array_equal(tree,rt) or not np.array_equal(p>=.5,q>=.5):raise ValueError('Frozen artifact replay contract failed')
 codes=[Path(__file__),HERE/'evaluate.py',HERE/'PROTOCOL.md',HERE.parent/'structural_challengers_20261028/experiment.py',HERE.parent/'feature_challengers_20261028/experiment.py',HERE.parent/'feature_challengers_20261028/postseason.py',HERE.parent/'challengers_20261028/cfb.py',ROOT/'research/cfb/backtest_baseline.py',ROOT/'research/cfb/experiment_priors.py']
 metadata={k:v for k,v in bundle.items() if k not in ['model','imputer']}
 metadata.update(artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),code_sha256={str(c.relative_to(ROOT)):hashlib.sha256(c.read_bytes()).hexdigest() for c in codes},source_sha256={str(c.relative_to(ROOT)):hashlib.sha256(c.read_bytes()).hexdigest() for c in sorted((ROOT/'runtime/challengers_20261028/cfb/matchup_line').glob('*.csv'))},environment={'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__,'catboost':catboost.__version__,'joblib':joblib.__version__},reload_smoke_rows=len(sample),reload_predictions_identical=True,parent_winners_preserved=True,performance_scored_on_final_training=False)
 (out/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps({k:v for k,v in metadata.items() if k not in ['source_sha256','code_sha256','raw_feature_columns','numeric_features','model_feature_columns']},indent=2),flush=True)
if __name__=='__main__':run()
