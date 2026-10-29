"""One registered transform of immutable OOF probabilities. No fitting."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PARENT='cat_d5_l2_5_halfblend';NAME='reference_confidence_anchor'
SOURCE_GIT_BLOB="11580a672fbe22945504cfd620da1c86d3a19d6d"
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
e=module('anchor_features',HERE.parent/'feature_challengers_20261028/experiment.py')

def anchor(reference,challenger):
 r=np.asarray(reference,float);q=np.asarray(challenger,float)
 if r.ndim!=1 or r.shape!=q.shape or not np.isfinite(r).all() or not np.isfinite(q).all() or ((r<0)|(r>1)|(q<0)|(q>1)).any():raise ValueError('Invalid paired probability vectors')
 return np.where((r>=.5)==(q>=.5),r,q)

def paired(source):
 d=source[source.candidate.isin(['control',PARENT])].copy()
 if d.duplicated(['candidate','game_id']).any():raise ValueError('Duplicate archived prediction')
 r=d[d.candidate.eq('control')].set_index('game_id').sort_index();q=d[d.candidate.eq(PARENT)].set_index('game_id').sort_index()
 if not len(r) or not r.index.equals(q.index):raise ValueError('Paired archive cohort mismatch')
 for c in ['season','home_win','block']:
  if not np.array_equal(r[c],q[c]):raise ValueError('Archive metadata/label mismatch')
 if not r.home_win.isin([0,1]).all() or not r.season.astype(int).between(2018,2025).all():raise ValueError('Excluded season or invalid label')
 for frame in [r,q]:
  if not frame.training_max_season.astype(int).lt(frame.season.astype(int)).all():raise ValueError('Non-prior OOF training season')
 return r,q

def run():
 path=HERE.parent/'structural_challengers_20261028/results/cfb/predictions.csv.gz';raw=path.read_bytes()
 if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=SOURCE_GIT_BLOB:raise ValueError('Immutable archive changed')
 ref,parent=paired(pd.read_csv(path));r=ref.probability.to_numpy();q=parent.probability.to_numpy();p=anchor(r,q)
 if len(ref)!=5733:raise ValueError('Wrong historical cohort')
 if not np.array_equal(p>=.5,q>=.5):raise ValueError('Transform changed parent winner')
 same=(r>=.5)==(q>=.5)
 if not np.array_equal(p[same],r[same]) or not np.array_equal(p[~same],q[~same]):raise ValueError('Anchor contract failed')
 original=json.loads((HERE.parent/'structural_challengers_20261028/results/cfb/results.json').read_text());summaries={}
 for name,frame in [('control',ref),(PARENT,parent)]:
  got=e.audit.summarize(frame.probability,frame.home_win);saved=original['scores'][name]['overall']
  for metric in ['games','wins','accuracy','brier','log_loss']:
   if not np.isclose(got['overall'][metric],saved['overall'][metric],atol=1e-12,rtol=0):raise ValueError('Original metric reproduction failed')
  summaries[name]=got
 control=ref.reset_index().copy();control['candidate']='control';candidate=control.copy();candidate['candidate']=NAME;candidate['probability']=p
 pred=pd.concat([control,candidate],ignore_index=True);pred['season']=pred.season.astype(str);scores,decisions=e.score_predictions(pred,'cfb')
 result={'candidate':NAME,'status':'adaptively_motivated_reused_historical_development','new_model_fitted':False,'live_2026_outcome_used':False,'original_parent_still_failed':not original['decisions'][PARENT]['research_eligible'],'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),'archive_git_blob_sha':SOURCE_GIT_BLOB,'scores':scores,'decisions':decisions,'contract':{'all_parent_winners_preserved':True,'reference_probability_retained_on_all_unchanged_picks':True,'unchanged_pick_games':int(same.sum()),'changed_pick_games':int((~same).sum())},'production_promoted':False,'prospective_model_bundle_built':False,'prospective_shadow_started':False,'required_new_paired_finals_before_review':200}
 out=ROOT/'runtime/cfb_anchor_20261029/results';out.mkdir(parents=True,exist_ok=True);pred.to_csv(out/'predictions.csv',index=False);(out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'overall':{n:s['overall'] for n,s in scores.items()},'decisions':decisions,'contract':result['contract']},indent=2),flush=True)
 return result
if __name__=='__main__':run()
