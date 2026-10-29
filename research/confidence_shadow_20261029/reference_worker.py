"""Read-only frozen producer replay, executed only in the producer environment."""
import argparse,hashlib,importlib.metadata,importlib.util,json,sys
from pathlib import Path
import joblib,numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[2]
VERSIONS={'numpy':'2.5.3','pandas':'3.0.6','scikit-learn':'1.9.1','scipy':'1.18.1','joblib':'1.6.0','requests':'2.34.2'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def clean(frame):return [{k:None if pd.isna(v) else float(v) for k,v in row.items()} for row in frame.to_dict('records')]
def run(payload,nhl_root):
 versions={k:importlib.metadata.version(k) for k in VERSIONS}
 config=json.loads((Path(__file__).parent/'config.json').read_text())
 if versions!=VERSIONS:raise ValueError('Frozen reference producer environment changed')
 if payload['sport'].startswith('cfb'):
  path=ROOT/'model/cfb/v1/frozen_bundle.joblib';manifest=json.loads(path.with_name('bundle_manifest.json').read_text())
  if sha(path)!=manifest['sha256'] or sha(path)!=config['reference_bundle_sha256']['cfb']:raise ValueError('Frozen CFB reference hash mismatch')
  bundle=joblib.load(path);cf=bundle['context_features'];pf=bundle['prior_features']
  if payload['sport']=='cfb_replay':
   fx=pd.DataFrame(payload['context']);px=pd.DataFrame(payload['prior'])
  else:
   base=module('shadow_cfb_base',ROOT/'research/cfb/backtest_baseline.py');pri=module('shadow_cfb_pri',ROOT/'research/cfb/experiment_priors.py')
   d=pd.DataFrame(payload.get('targets',[payload.get('target')]));fx=base.build_matrix(d);px=pri.matrix(d,float(bundle['prior_k']))
  pc=bundle['context_model'].predict_proba(fx[cf])[:,1];pp=bundle['prior_model'].predict_proba(px[pf])[:,1]
  p=float(bundle['context_weight'])*pc+float(bundle['prior_weight'])*pp
  vectors={'context':clean(fx[cf]),'prior':clean(px[pf])};bundle_sha=sha(path)
  code={str(f.relative_to(ROOT)):sha(f) for f in [ROOT/'research/cfb/backtest_baseline.py',ROOT/'research/cfb/experiment_priors.py']}
  if code!=config['cfb_producer_code_sha256']:raise ValueError('Frozen CFB feature producer changed')
 else:
  r=Path(nhl_root).resolve();path=r/'model/nhl/v2_research/watchlist.joblib';manifest=json.loads(path.with_name('manifest.json').read_text())
  if sha(path)!=config['reference_bundle_sha256']['nhl'] or sha(path)!=manifest['bundle_sha256'] or sha(path.with_name('spec.json'))!=manifest['spec_sha256'] or versions!=manifest['package_versions']:raise ValueError('Frozen NHL reference identity changed')
  code={}
  for name,digest in manifest['code_sha256'].items():
   relative=name[name.index('research/nhl/'):];f=r/relative
   if sha(f)!=digest:raise ValueError('Frozen NHL producer code changed: '+relative)
   code[relative]=digest
  producer=module('shadow_original_nhl_producer',r/'research/nhl/prospective/build_ledger.py')
  history=pd.DataFrame(payload['history']);history['game_date']=pd.to_datetime(history.game_date);history['season']=history.season.astype(str)
  stats=pd.DataFrame(payload['stats']);stats['gameDate']=pd.to_datetime(stats.gameDate);stats['season']=stats.season.astype(str)
  bundle=joblib.load(path);cols=bundle['features'];all_x=[]
  for raw in payload.get('targets',[payload.get('target')]):
   target=dict(raw);target['game_date']=pd.Timestamp(target['game_date']);target['season']=str(target['season'])
   # Each call contains real completed history plus exactly ONE pending target.
   x,_=producer.forecast_inputs(history,stats,target);all_x.append(x[cols])
  x=pd.concat(all_x,ignore_index=True);p=bundle['reference'].predict_proba(x[cols])[:,1]
  vectors={'reference':clean(x[cols])};bundle_sha=sha(path)
 if not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid frozen reference probability')
 return {'probabilities':p.tolist(),'feature_vectors':vectors,'reference_bundle_sha256':bundle_sha,'producer_code_sha256':code,'producer_versions':versions}
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--input',required=True);a.add_argument('--output',required=True);a.add_argument('--nhl-root',default='runtime/confidence_shadow/nhl_reference');args=a.parse_args()
 result=run(json.loads(Path(args.input).read_text()),args.nhl_root);Path(args.output).write_text(json.dumps(result,allow_nan=False)+'\n')
