"""Fixed descriptive analysis of retained OOF forecasts. No model training."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];NAME='cat_d5_l2_5_halfblend'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
cfb=module('audit_cfb',HERE.parent/'challengers_20261028/cfb.py')

def load_predictions(frame,meta):
 required={'game_id','season','home_win','candidate','probability'}
 if not required.issubset(frame):raise ValueError('Incomplete archive')
 selected=frame[frame.candidate.isin(['control',NAME])].copy()
 if selected.duplicated(['candidate','game_id']).any() or meta.game_id.duplicated().any():raise ValueError('Duplicate game identity')
 a=selected[selected.candidate.eq(NAME)].set_index('game_id').sort_index();b=selected[selected.candidate.eq('control')].set_index('game_id').sort_index()
 if not a.index.equals(b.index) or not len(a):raise ValueError('Candidate/control cohorts differ')
 if not np.array_equal(a.season,b.season) or not np.array_equal(a.home_win,b.home_win):raise ValueError('Candidate/control outcomes or seasons differ')
 if not np.isfinite(selected.probability).all() or not selected.probability.between(0,1).all() or not selected.home_win.isin([0,1]).all():raise ValueError('Invalid archived probability/outcome')
 d=meta.set_index('game_id').loc[a.index].copy()
 if not np.array_equal(a.home_win,d.home_win) or not np.array_equal(a.season,d.season) or not a.season.between(2018,2025).all():raise ValueError('Historical metadata/label mismatch')
 d['reference_probability']=b.probability;d['candidate_probability']=a.probability
 return d.reset_index()

def enrich(d,context):
 d=d.copy();r=d.reference_probability.to_numpy();p=d.candidate_probability.to_numpy();y=d.home_win.to_numpy();rc=(r>=.5)==y;pc=(p>=.5)==y
 d['reference_correct']=rc;d['candidate_correct']=pc;d['agreement']=np.where((r>=.5)==(p>=.5),'same_pick','changed_pick')
 d['pick_effect']=np.select([rc&pc,~rc&~pc,~rc&pc,rc&~pc],['both_correct','both_wrong','fixed_original_error','broke_original_correct'],default='invalid')
 d['brier_delta']=(p-y)**2-(r-y)**2;pr=np.clip(p,1e-15,1-1e-15);rr=np.clip(r,1e-15,1-1e-15)
 d['logloss_delta']=(-y*np.log(pr)-(1-y)*np.log1p(-pr))-(-y*np.log(rr)-(1-y)*np.log1p(-rr))
 d['stage']=np.select([d.season_type.eq('postseason'),d.week.le(4),d.week.le(8)],['postseason','regular_1_4','regular_5_8'],default='regular_9_plus')
 d['reference_band']=pd.cut(np.maximum(r,1-r),[.5,.6,.7,.8,.9,1.000001],right=False,labels=['50_60','60_70','70_80','80_90','90_100'])
 d['talent_availability']=np.where(d.weighted_talent_diff.isna(),'missing','present')
 count=d[context].isna().sum(axis=1);d['missing_context']=np.where(count.eq(0),'0',np.where(count.eq(1),'1','2_plus'))
 return d

def metrics(g):
 if g.empty:return {'games':0}
 p=g.candidate_probability.to_numpy();r=g.reference_probability.to_numpy();y=g.home_win.to_numpy();rc=g.reference_correct.to_numpy();pc=g.candidate_correct.to_numpy()
 loss=lambda v:float(np.mean(-y*np.log(np.clip(v,1e-15,1-1e-15))-(1-y)*np.log(np.clip(1-v,1e-15,1-1e-15))))
 return {'games':len(g),'reference_wins':int(rc.sum()),'candidate_wins':int(pc.sum()),'net_extra_wins':int(pc.sum()-rc.sum()),'reference_accuracy':float(rc.mean()),'candidate_accuracy':float(pc.mean()),'reference_brier':float(np.mean((r-y)**2)),'candidate_brier':float(np.mean((p-y)**2)),'brier_delta':float(g.brier_delta.mean()),'total_brier_delta':float(g.brier_delta.sum()),'reference_log_loss':loss(r),'candidate_log_loss':loss(p),'log_loss_delta':float(g.logloss_delta.mean()),'fixed_original_errors':int((~rc&pc).sum()),'broke_original_correct':int((rc&~pc).sum())}

def grouped(d,cols):
 return [{**{c:str(v) for c,v in zip(cols,key if isinstance(key,tuple) else (key,))},**metrics(g)} for key,g in d.groupby(cols,observed=False,dropna=False)]

def live_audit(meta,x,px):
 path=ROOT/'data/confidence_shadow_20261029/forecasts.jsonl';rows=[json.loads(s) for s in path.read_text().splitlines()];rows=[r for r in rows if r['sport']=='cfb'];snapshot=ROOT/'runtime/cfb_failure_audit_20261029/live_snapshot.json';raw=json.loads(snapshot.read_text());targets={int(t['game_id']):t for t in raw['targets']}
 weeks=sorted({int(targets[int(r['game_id'])]['week']) for r in rows});hist=meta.index[meta.week.isin(weeks)]
 # The original receipt did not retain season_type; report the limitation, never invent it.
 result={'captured_games':len(rows),'source_weeks':weeks,'historical_matched_week_games':len(hist),'season_type_match_verified':all('season_type' in targets[int(r['game_id'])] for r in rows),'live_outcomes_used':False,'columns':[]}
 for part,matrix in [('context',x),('prior',px)]:
  frame=pd.DataFrame([r['reference_feature_vectors'][part] for r in rows]);old=matrix.loc[hist,frame.columns]
  for c in frame:
   live=pd.to_numeric(frame[c],errors='coerce');past=pd.to_numeric(old[c],errors='coerce');finite=past.dropna();valid=live.dropna();lo=float(finite.min()) if len(finite) else None;hi=float(finite.max()) if len(finite) else None
   result['columns'].append({'part':part,'feature':c,'live_missing_fraction':float(live.isna().mean()),'historical_missing_fraction':float(past.isna().mean()),'live_nonfinite_nonmissing':int((live.notna()&~np.isfinite(live)).sum()),'live_median':float(valid.median()) if len(valid) else None,'historical_median':float(finite.median()) if len(finite) else None,'outside_historical_range':int(((valid<lo)|(valid>hi)).sum()) if lo is not None else None})
 return result

def run():
 rawdir=ROOT/'runtime/challengers_20261028/cfb/matchup_line';manifest=json.loads((HERE.parent/'structural_challengers_20261028/source_manifest.json').read_text())
 hashes={}
 for path,expected in manifest['input_file_sha256'].items():
  if '/cfb/matchup_line/' not in path:continue
  actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
  if actual!=expected:raise ValueError('Historical source changed: '+path)
  hashes[path]=actual
 if len(hashes)!=11:raise ValueError('Wrong historical source count')
 meta=cfb.guarded_data(rawdir);x,px,cf,pf=cfb.matrices(meta);full=meta.copy();full[x.columns]=x
 archive=HERE.parent/'structural_challengers_20261028/results/cfb/predictions.csv.gz';pred=pd.read_csv(archive);d=enrich(load_predictions(pred,full),cf)
 if len(d)!=5733:raise ValueError('Wrong OOF cohort')
 out=ROOT/'runtime/cfb_failure_audit_20261029/results';out.mkdir(parents=True,exist_ok=True)
 summaries={name:grouped(d,cols) for name,cols in {'season':['season'],'stage':['stage'],'reference_confidence':['reference_band'],'agreement':['agreement'],'pick_effect':['pick_effect'],'weighted_talent':['talent_availability'],'missing_context':['missing_context'],'stage_talent':['stage','talent_availability'],'season_agreement':['season','agreement'],'season_talent':['season','talent_availability']}.items()}
 teams=pd.concat([d.assign(team_id=d.home_team_id,team_name=d.home_team),d.assign(team_id=d.away_team_id,team_name=d.away_team)]);summaries['team_involvement']=[r for r in grouped(teams,['team_id','team_name']) if r['games']>=75]
 failed=[int(r['season']) for r in summaries['season'] if r['brier_delta']>0]
 bad=d[d.season.isin(failed)].nlargest(20,'brier_delta')
 cols=['game_id','season','week','home_team','away_team','home_win','reference_probability','candidate_probability','pick_effect','brier_delta','logloss_delta','talent_availability','missing_context']
 bad[cols].to_csv(out/'largest_adverse_games.csv',index=False)
 d[['game_id','season','week','season_type','reference_probability','candidate_probability','home_win','reference_correct','candidate_correct','stage','reference_band','pick_effect','agreement','talent_availability','missing_context','brier_delta','logloss_delta']].to_csv(out/'paired_diagnostics.csv',index=False)
 result={'candidate':NAME,'status':'descriptive_reused_historical_development_only','new_model_fitted':False,'gate_changed':False,'production_promoted':False,'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),'overall':metrics(d),'groups':summaries,'failed_brier_seasons':failed,'source_sha256':hashes,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'live_input_audit':live_audit(meta,x,px)}
 (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'overall':result['overall'],'failed_seasons':failed,'stage':summaries['stage'],'agreement':summaries['agreement'],'pick_effect':summaries['pick_effect'],'talent':summaries['weighted_talent'],'season_agreement':summaries['season_agreement'],'live_largest_missingness_gaps':sorted(result['live_input_audit']['columns'],key=lambda r:abs(r['live_missing_fraction']-r['historical_missing_fraction']),reverse=True)[:5]},indent=2),flush=True)
if __name__=='__main__':run()
