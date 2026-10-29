"""Registered confidence-only mappings on earlier-season OOF predictions."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.isotonic import IsotonicRegression

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('confidence_audit',ROOT/'confidence_audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
BINS=np.array([.5,.6,.7,.8,.9,1.00000001])
def fit_mapping(p,y):
 p=np.asarray(p,float);y=np.asarray(y,int)
 if len(p)<200 or not np.isfinite(p).all() or not np.isin(y,[0,1]).all():raise ValueError('Invalid or insufficient calibration data')
 conf=np.maximum(p,1-p);correct=((p>=.5)==y).astype(int);xs=[];ys=[];weights=[]
 for lo,hi in zip(BINS[:-1],BINS[1:]):
  mask=(conf>=lo)&(conf<hi);n=int(mask.sum());center=float(conf[mask].mean()) if n else (lo+min(hi,1))/2
  xs.append(center);ys.append((int(correct[mask].sum())+100*center)/(n+100));weights.append(n+100)
 iso=IsotonicRegression(y_min=.500001,y_max=.999999,out_of_bounds='clip');iso.fit(xs,ys,sample_weight=weights)
 return iso

def apply_mapping(p,mapping):
 p=np.asarray(p,float);c=mapping.predict(np.maximum(p,1-p));q=np.where(p>=.5,c,1-c);q[p==.5]=.5
 if not np.array_equal(p>=.5,q>=.5):raise ValueError('Calibration changed winners')
 return q

def run(sport):
 old=ROOT/'research/challengers_20261028/results'/sport/'development_predictions.csv.gz'
 d=pd.read_csv(old);d=d[d.candidate.eq('control')].copy();d['season']=d.season.astype(str)
 if d.duplicated('game_id').any() or d.season.max()>('2025' if sport=='cfb' else '20242025'):raise ValueError('Invalid development boundary')
 if sport=='cfb':
  spec=importlib.util.spec_from_file_location('original_cfb',ROOT/'research/challengers_20261028/cfb.py');cfb=importlib.util.module_from_spec(spec);spec.loader.exec_module(cfb)
  raw=cfb.guarded_data(ROOT/'runtime/challengers_20261028/cfb/matchup_line');p4={'SEC','Big Ten','Big 12','ACC'}
  groups=raw.set_index('game_id').apply(lambda r:'p4_vs_p4' if r.home_conference in p4 and r.away_conference in p4 else 'other',axis=1)
  d['group']=d.game_id.map(groups)
  if d.group.isna().any():raise ValueError('Missing conference join')
 else:d['group']='pooled'
 rows=[];boundaries=[]
 seasons=sorted(d.season.unique())
 for season in seasons[1:]:
  prior=sorted(s for s in seasons if s<season)[-3:];train=d[d.season.isin(prior)];test=d[d.season.eq(season)]
  pooled=fit_mapping(train.probability,train.home_win);p=test.probability.to_numpy();cal={'control':p,'pooled_isotonic':apply_mapping(p,pooled)}
  mapping_record={'pooled':{'x':pooled.X_thresholds_.tolist(),'y':pooled.y_thresholds_.tolist(),'games':len(train)}}
  if sport=='cfb':
   grouped=cal['pooled_isotonic'].copy()
   for group in ['p4_vs_p4','other']:
    tr=train[train.group.eq(group)];mask=test.group.eq(group).to_numpy()
    if len(tr)>=200:
     mapping=fit_mapping(tr.probability,tr.home_win);grouped[mask]=apply_mapping(p[mask],mapping)
     mapping_record[group]={'x':mapping.X_thresholds_.tolist(),'y':mapping.y_thresholds_.tolist(),'games':len(tr)}
    else:mapping_record[group]={'fallback':'pooled','games':len(tr)}
   cal['group_isotonic']=grouped
  boundaries.append({'test_season':season,'training_seasons':prior,'mappings':mapping_record})
  for name,prob in cal.items():
   for r,v in zip(test.itertuples(),prob):rows.append({'game_id':int(r.game_id),'season':season,'group':r.group,'candidate':name,'home_win':int(r.home_win),'raw_probability':float(r.probability),'probability':float(v)})
 pred=pd.DataFrame(rows);scores={}
 for name,g in pred.groupby('candidate'):
  recent=g[g.season.ge('2023' if sport=='cfb' else '20232024')]
  scores[name]={'overall':audit.summarize(g.probability,g.home_win),'recent':audit.summarize(recent.probability,recent.home_win),'by_season':[{'season':s,**audit.summarize(q.probability,q.home_win)} for s,q in g.groupby('season')],'winner_changes':int(((g.probability>=.5)!=(g.raw_probability>=.5)).sum()),'confidence_increases':int((np.maximum(g.probability,1-g.probability)>np.maximum(g.raw_probability,1-g.raw_probability)+1e-12).sum()),'confidence_decreases':int((np.maximum(g.probability,1-g.probability)<np.maximum(g.raw_probability,1-g.raw_probability)-1e-12).sum())}
 decisions={};control=scores['control']
 for name,s in scores.items():
  if name=='control':continue
  a=s['overall'];b=control['overall'];better=sum(q['overall']['brier']<c['overall']['brier'] for q,c in zip(s['by_season'],control['by_season']))
  checks={'brier':a['overall']['brier']<b['overall']['brier'],'log_loss':a['overall']['log_loss']<b['overall']['log_loss'],'ece':a['ece']<=b['ece'],'winners_preserved':s['winner_changes']==0,'season_consistency':better>=(5 if sport=='cfb' else 2),'recent_brier':s['recent']['overall']['brier']<=control['recent']['overall']['brier'],'recent_log_loss':s['recent']['overall']['log_loss']<=control['recent']['overall']['log_loss']}
  decisions[name]={'research_eligible':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'seasons_brier_improved':better,'production_promoted':False}
 result={'sport':sport,'status':'reused_historical_development_only','protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),'input_oof_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'live_labels_used':False,'scores':scores,'decisions':decisions,'fit_boundaries':boundaries}
 out=ROOT/'runtime/confidence_20261028'/sport;out.mkdir(parents=True,exist_ok=True);pred.to_csv(out/'predictions.csv',index=False);(out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'sport':sport,'scores':{n:{**s['overall']['overall'],'ece':s['overall']['ece']} for n,s in scores.items()},'decisions':decisions},indent=2))
 return result
if __name__=='__main__':
 for sport in ['cfb','nhl']:run(sport)
