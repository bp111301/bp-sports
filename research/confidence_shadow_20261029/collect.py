"""Real paired pregame confidence research. Original production files are read-only."""
import argparse,concurrent.futures,gzip,hashlib,importlib.metadata,importlib.util,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen
import joblib,numpy as np,pandas as pd

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
import events

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
fit=module('shadow_fixed_bundle',ROOT/'research/confidence_projection_20261028/fit_final.py')
e=fit.e
audit=fit.e.audit
CONFIG=json.loads((HERE/'config.json').read_text())
RESEARCH_VERSIONS={'numpy':'2.3.5','pandas':'2.2.3','scikit-learn':'1.8.0','scipy':'1.17.0','joblib':'1.5.3','requests':'2.34.2'}
OUT=ROOT/'data/confidence_shadow_20261029';RUNTIME=ROOT/'runtime/confidence_shadow';RUNTIME.mkdir(parents=True,exist_ok=True)
TEAM_ABBREVS=['ANA','BOS','BUF','CAR','CBJ','CGY','CHI','COL','DAL','DET','EDM','FLA','LAK','MIN','MTL','NJD','NSH','NYI','NYR','OTT','PHI','PIT','SEA','SJS','STL','TBL','TOR','UTA','VAN','VGK','WPG','WSH']

def now():return pd.Timestamp.now(tz='UTC')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def jsonable(value):
 if isinstance(value,dict):return {str(k):jsonable(v) for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [jsonable(v) for v in value]
 if isinstance(value,(pd.Timestamp,datetime)):return value.isoformat()
 if isinstance(value,np.generic):return jsonable(value.item())
 if value is None or (isinstance(value,float) and not np.isfinite(value)):return None
 return value

def records(frame):return jsonable(frame.to_dict('records'))
def fetch(url):
 error=None
 for attempt in range(3):
  try:
   with urlopen(Request(url,headers={'User-Agent':'BP-Sports-Confidence-Shadow/1.0'}),timeout=60) as r:raw=r.read()
   return raw,{'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'observed_at_utc':now().isoformat()}
  except Exception as exc:
   error=exc
   if attempt<2:time.sleep(attempt+1)
 raise error

def table(url,compression=None):
 import io
 raw,receipt=fetch(url);return pd.read_csv(io.BytesIO(raw),compression=compression,low_memory=False),receipt

def frozen_bundle(sport):
 path=ROOT/f'research/confidence_projection_20261028/final_bundles/{sport}.joblib'
 if sha(path)!=CONFIG['challenger_bundle_sha256'][sport]:raise ValueError('Frozen confidence artifact changed')
 b=joblib.load(path)
 if b['sport']!=sport or b['version']!='confidence_only_research_20261028':raise ValueError('Wrong confidence artifact')
 return b

def fresh_reference(snapshot,python,nhl_root):
 token=hashlib.sha256(events.canonical(snapshot).encode()).hexdigest();inp=RUNTIME/f'{token}.input.json';output=RUNTIME/f'{token}.reference.json';inp.write_text(events.canonical(snapshot))
 subprocess.run([str(python),str(HERE/'reference_worker.py'),'--input',str(inp),'--output',str(output),'--nhl-root',str(nhl_root)],check=True,timeout=600)
 result=json.loads(output.read_text())
 if result['reference_bundle_sha256']!=CONFIG['reference_bundle_sha256'][snapshot['sport']]:raise ValueError('Unexpected fresh reference identity')
 return result

def strength_at(history,target):
 """Exactly the registered CFB ridge value, fitted once for this target only."""
 date=pd.to_datetime(target['start_date'],utc=True).normalize();dates=pd.to_datetime(history.start_date,utc=True).dt.normalize();age=(date-dates).dt.days
 g=history[(age>=2)&(age<=365)].copy();ages=age.loc[g.index].to_numpy()
 ids=sorted(set(g.home_team_id.astype(int))|set(g.away_team_id.astype(int))|{int(target['home_team_id']),int(target['away_team_id'])});lookup={t:i for i,t in enumerate(ids)}
 a=np.zeros((len(g),len(ids)));a[np.arange(len(g)),g.home_team_id.astype(int).map(lookup)]=1;a[np.arange(len(g)),g.away_team_id.astype(int).map(lookup)]=-1
 neutral=g.neutral_site.astype(str).str.lower().isin(['true','1','yes']);home_field=(~neutral).astype(float).to_numpy()
 y=np.clip(g.home_points.to_numpy(float)-g.away_points.to_numpy(float),-42,42)-3*home_field
 w=np.exp2(-ages/180);coef=np.linalg.solve(a.T@(w[:,None]*a)+10*np.eye(len(ids)),a.T@(w*y))
 value=coef[lookup[int(target['home_team_id'])]]-coef[lookup[int(target['away_team_id'])]]
 return float(value),{'source_games':len(g),'source_max_date':str(pd.to_datetime(g.start_date,utc=True).max()) if len(g) else None,'target_source_calendar_date':str(date)}

def cfb_inputs(existing):
 sources=[]
 raw,r=table('https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_matchup_line/cfb_matchup_line_2026.csv');sources.append(r)
 schedule,r=table('https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_schedules/cfb_schedules_2026.csv.gz','gzip');sources.append(r)
 prior_path=ROOT/'runtime/challengers_20261028/cfb/matchup_line/cfb_matchup_line_2025.csv'
 expected=json.loads((ROOT/'research/confidence_projection_20261028/final_bundles/cfb.json').read_text())['source_file_sha256'][str(prior_path.relative_to(ROOT))]
 if not prior_path.exists():
  data,r=fetch('https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_matchup_line/cfb_matchup_line_2025.csv');prior_path.parent.mkdir(parents=True,exist_ok=True);prior_path.write_bytes(data)
 if sha(prior_path)!=expected:raise ValueError('Frozen CFB history source changed')
 sources.append({'path':str(prior_path.relative_to(ROOT)),'sha256':expected,'role':'frozen_completed_history'})
 prior=pd.read_csv(prior_path,low_memory=False)
 if not raw.season.eq(2026).all() or not schedule.season.eq(2026).all():raise ValueError('Wrong live CFB source season')
 for df in [raw,schedule]:
  df['game_id']=pd.to_numeric(df.game_id,errors='raise').astype(int)
  if df.game_id.duplicated().any():raise ValueError('Duplicate CFB source identity')
 starts=pd.to_datetime(schedule.start_date,utc=True,format='mixed',errors='coerce');current=now();truth=lambda x:x.astype(str).str.lower().isin(['true','1','1.0'])
 eligible=schedule[starts.gt(current)&starts.le(current+pd.Timedelta(days=CONFIG['cfb_horizon_days']))&~truth(schedule.completed)&~truth(schedule.start_time_tbd)].copy()
 eligible['exact_start']=starts.loc[eligible.index]
 supported=eligible[truth(eligible.fbs_game)]
 missing=set(supported.game_id)-set(raw.game_id)
 if missing:raise ValueError('Missing FBS-vs-FBS shadow inputs: '+str(sorted(missing)))
 targets=[];lookup=raw.set_index('game_id',drop=False)
 bases=set(e.cfb.base.PAIR_BASES+e.cfb.base.PRIOR_BASES+e.cfb.pri.BLEND_BASES)
 feature_cols={f'{prefix}{side}_{f}' for prefix in ['', 'prev_'] for side in ['home','away'] for f in bases}
 feature_cols|={f'{side}_{f}' for side in ['home','away'] for f in ['pregame_elo','opp_elo_roll_avg','talent','team_talent_weighted','ovr_rtprod','hc_tenure']}
 keep=feature_cols|{'game_id','season','week','start_date','neutral_site','conference_game','home_team_id','away_team_id','home_team','away_team'}
 summaries={}
 needed=set(supported.game_id)|{int(f['game_id']) for f in existing.values() if f['sport']=='cfb' and events.stamp(f['start_time_utc'])<=current}
 def official_summary(gid):
  data,r=fetch(f'https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={gid}');header=json.loads(data)['header'];c=header['competitions'][0];sides={t['homeAway']:t for t in c['competitors']}
  if int(header['id'])!=gid:raise ValueError('Wrong ESPN CFB event identity')
  return gid,{'game_id':gid,'home_id':int(sides['home']['id']),'away_id':int(sides['away']['id']),'home_score':sides['home'].get('score'),'away_score':sides['away'].get('score'),'start_time_utc':events.stamp(c['date']).isoformat(),'state':c['status']['type']['name'],'completed':c['status']['type']['completed'],'phase':c['status']['type']['state'],'source_receipt':r}
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  for gid,result in pool.map(official_summary,sorted(needed)):summaries[gid]=result;sources.append(result['source_receipt'])
 for s in supported.sort_values('exact_start').to_dict('records'):
  key=f"{CONFIG['version']}:cfb:{s['game_id']}"
  if key in existing:continue
  official=summaries[int(s['game_id'])]
  if official['state']!='STATUS_SCHEDULED' or official['completed'] or official['phase']!='pre':continue
  if events.stamp(official['start_time_utc'])!=s['exact_start'] or official['home_id']!=int(s['home_id']) or official['away_id']!=int(s['away_id']):raise ValueError('CFB official schedule/identity mismatch')
  t=lookup.loc[int(s['game_id'])]
  if int(t.home_team_id)!=int(s['home_id']) or int(t.away_team_id)!=int(s['away_id']):raise ValueError('CFB scheduled/source team mismatch')
  target=jsonable({c:t[c] for c in keep if c in t.index});target.update(start_time_utc=s['exact_start'].isoformat(),game_state='STATUS_SCHEDULED',home_id=int(s['home_id']),away_id=int(s['away_id']))
  targets.append(target)
 histcols=['game_id','season','start_date','home_team_id','away_team_id','home_points','away_points','neutral_site']
 finals=schedule[truth(schedule.completed)&starts.le(current)]
 complete=raw[raw.game_id.isin(finals.game_id)].copy()
 history=pd.concat([prior[histcols],complete[histcols]],ignore_index=True)
 if history.game_id.duplicated().any() or history[['home_points','away_points']].isna().any().any():raise ValueError('Invalid completed CFB strength history')
 snapshot={'sport':'cfb','input_snapshot_at_utc':now().isoformat(),'sources':sources,'targets':targets,'history':records(history)}
 official={gid:r for gid,r in summaries.items() if r['state']=='STATUS_FINAL' and r['completed'] and r['phase']=='post'}
 coverage={'supported_future_games':len(supported),'new_targets':len(targets),'unsupported_fbs_fcs_future_games':len(eligible[truth(eligible.fbs_participant)&~truth(eligible.fbs_game)])}
 return jsonable(snapshot),official,coverage

def nhl_history_sources():
 directory=ROOT/'runtime/confidence_projection_20261028/final_nhl_sources';directory.mkdir(parents=True,exist_ok=True)
 expected=json.loads((ROOT/'research/confidence_projection_20261028/final_bundles/nhl.json').read_text())['source_file_sha256']
 def one(item):
  path,digest=item;p=ROOT/path;name=p.stem;report,season=name.rsplit('_',1)
  url='https://api.nhle.com/stats/rest/en/team/'+report+'?'+urlencode({'isAggregate':'false','isGame':'true','start':0,'limit':-1,'factCayenneExp':'gamesPlayed>=1','cayenneExp':f'seasonId={season} and gameTypeId=2'})
  if not p.exists():
   data,_=fetch(url);pd.DataFrame(json.loads(data)['data']).to_csv(p,index=False)
  if sha(p)!=digest:raise ValueError('Frozen NHL history source changed: '+p.name)
  return {'url':url,'sha256':digest,'path':str(p.relative_to(ROOT)),'role':'frozen_completed_history'}
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:sources=list(pool.map(one,expected.items()))
 return e.nhl.adv.load_team_stats(directory),sources

def nhl_inputs(existing):
 histstats,sources=nhl_history_sources()
 def club(team):
  data,r=fetch(f'https://api-web.nhle.com/v1/club-schedule-season/{team}/20262027');return json.loads(data),r
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:clubs=list(pool.map(club,TEAM_ABBREVS))
 games={}
 for data,r in clubs:
  sources.append(r)
  for g in data.get('games',[]):
   if int(g.get('gameType',0))!=2:continue
   h=g['homeTeam'];a=g['awayTeam'];gid=int(g['id'])
   record=dict(game_id=gid,season=str(g['season']),game_date=g['gameDate'],start_time_utc=g['startTimeUTC'],game_state=g['gameState'],home_id=int(h['id']),away_id=int(a['id']),home_team=h['abbrev'],away_team=a['abbrev'],home_score=h.get('score'),away_score=a.get('score'))
   if gid in games and games[gid]!=record:raise ValueError('Conflicting official NHL schedules')
   games[gid]=record
 if not games:raise ValueError('Empty NHL current schedule')
 if any(g['season']!='20262027' for g in games.values()):raise ValueError('Wrong live NHL source season')
 raw=pd.DataFrame(games.values());starts=pd.to_datetime(raw.start_time_utc,utc=True,errors='coerce');current=now()
 final=raw[raw.game_state.isin(['OFF','FINAL'])&starts.le(current)].copy()
 if final[['home_score','away_score']].isna().any().any() or final.home_score.eq(final.away_score).any():raise ValueError('Invalid official NHL final')
 def stats(report):
  url='https://api.nhle.com/stats/rest/en/team/'+report+'?'+urlencode({'isAggregate':'false','isGame':'true','start':0,'limit':-1,'factCayenneExp':'gamesPlayed>=1','cayenneExp':'seasonId=20262027 and gameTypeId=2'})
  data,r=fetch(url);return report,pd.DataFrame(json.loads(data)['data']),r
 currentdir=RUNTIME/'current_nhl_team_stats';currentdir.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for report,df,r in pool.map(stats,['summary','powerplay','penaltykill']):
   if df.empty:raise ValueError('Empty current NHL stat report')
   df.to_csv(currentdir/f'{report}_20262027.csv',index=False);sources.append(r)
 ct=e.nhl.adv.load_team_stats(currentdir);ct=ct[ct.gameId.isin(final.game_id)]
 dcurrent=e.nhl.historical_games(ct)
 if set(dcurrent.game_id)!=set(final.game_id):raise ValueError('Current NHL final/stat coverage incomplete')
 check=final.set_index('game_id')
 for row in dcurrent.itertuples():
  f=check.loc[row.game_id]
  if row.home_id!=int(f.home_id) or row.away_id!=int(f.away_id) or row.home_score!=float(f.home_score) or row.away_score!=float(f.away_score):raise ValueError('NHL final score/identity reports disagree')
 history=pd.concat([e.nhl.historical_games(histstats),dcurrent],ignore_index=True).sort_values(['season','game_date','game_id']).reset_index(drop=True)
 allstats=pd.concat([histstats,ct],ignore_index=True)
 if history.game_id.duplicated().any() or allstats.duplicated(['season','gameId','teamId']).any():raise ValueError('Duplicate NHL historical identity')
 upcoming=raw[raw.game_state.isin(['FUT','PRE'])&starts.gt(current)&starts.le(current+pd.Timedelta(hours=CONFIG['nhl_horizon_hours']))].sort_values(['start_time_utc','game_id'])
 targets=[jsonable(r) for r in upcoming.to_dict('records') if f"{CONFIG['version']}:nhl:{r['game_id']}" not in existing]
 statscols=list(dict.fromkeys(['season','gameId','gameDate','teamId']+e.nhl.adv.RAW+['goalsFor','goalsAgainst','shotsForPerGame','shotsAgainstPerGame','powerPlayGoalsFor','ppOpportunities','ppGoalsAgainst','timesShorthanded']))
 snapshot={'sport':'nhl','input_snapshot_at_utc':now().isoformat(),'sources':sources,'targets':targets,'history':records(history),'stats':records(allstats[statscols])}
 official={int(r['game_id']):{'game_id':int(r['game_id']),'home_id':int(r['home_id']),'away_id':int(r['away_id']),'home_score':r['home_score'],'away_score':r['away_score'],'start_time_utc':r['start_time_utc'],'state':r['game_state'],'source_receipts':[s for s in sources if 'club-schedule' in s.get('url','')]} for r in final.to_dict('records')}
 return jsonable(snapshot),official,{'supported_future_games':len(upcoming),'new_targets':len(targets),'completed_current_games':len(final)}

def save_snapshot(snapshot):
 raw=events.canonical(snapshot).encode();digest=hashlib.sha256(raw).hexdigest();path=OUT/'inputs'/f'{digest}.json.gz'
 if path.exists():
  if gzip.decompress(path.read_bytes())!=raw:raise ValueError('Cannot rewrite content-addressed snapshot')
 else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(gzip.compress(raw,mtime=0))
 return digest,str(path.relative_to(ROOT))

def forecasts(snapshot,reference_python,nhl_root):
 if not snapshot['targets']:return []
 sport=snapshot['sport'];bundle=frozen_bundle(sport);reference=fresh_reference(snapshot,reference_python,nhl_root);targets=snapshot['targets'];p=np.array(reference['probabilities'])
 if len(p)!=len(targets):raise ValueError('Reference cohort changed')
 boundaries=[]
 if sport=='cfb':
  x=pd.DataFrame(reference['feature_vectors']['prior']);history=pd.DataFrame(snapshot['history']);strength=[]
  for t in targets:
   value,boundary=strength_at(history,t);strength.append(value);boundaries.append(boundary)
  x['strength_diff']=strength
 else:
  stats=pd.DataFrame(snapshot['stats']);stats['gameDate']=pd.to_datetime(stats.gameDate);stats['season']=stats.season.astype(str)
  td=pd.DataFrame(targets);td['season']=td.season.astype(str);extra,boundaries=e.pooled_rates(td,stats)
  x=pd.DataFrame(reference['feature_vectors']['reference']).join(extra)
 x=x[bundle['feature_columns']];q=fit.predict_features(bundle,x,p);snapshot_sha,snapshot_path=save_snapshot(snapshot);rows=[]
 captured=now()
 for i,target in enumerate(targets):
  r={'forecast_key':f"{CONFIG['version']}:{sport}:{target['game_id']}",'version':CONFIG['version'],'sport':sport,'game_id':int(target['game_id']),'home_id':int(target['home_id']),'away_id':int(target['away_id']),'home_team':str(target['home_team']),'away_team':str(target['away_team']),'game_state':target['game_state'],'start_time_utc':events.stamp(target['start_time_utc']).isoformat(),'input_snapshot_at_utc':snapshot['input_snapshot_at_utc'],'captured_at_utc':captured.isoformat(),'reference_home_win_prob':float(p[i]),'challenger_home_win_prob':float(q[i]),'comparison_role':'same_snapshot_fresh_reference_not_original_first_forecast','reference_bundle_sha256':reference['reference_bundle_sha256'],'challenger_bundle_sha256':CONFIG['challenger_bundle_sha256'][sport],'input_snapshot_sha256':snapshot_sha,'input_snapshot_path':snapshot_path,'reference_feature_vectors':{k:v[i] for k,v in reference['feature_vectors'].items()},'challenger_feature_vector':records(x.iloc[[i]])[0],'feature_temporal_boundary':boundaries[i] if sport=='cfb' else next(b for b in boundaries if pd.Timestamp(b['target_date']).date()==pd.Timestamp(target['game_date']).date()),'reference_producer_code_sha256':reference['producer_code_sha256'],'reference_environment':reference['producer_versions'],'collector_code_sha256':sha(Path(__file__)),'reference_worker_code_sha256':sha(HERE/'reference_worker.py'),'protocol_sha256':sha(HERE/'PROTOCOL.md')}
  # A game can cross its start while the models run. Do not backfill it.
  if events.stamp(r['start_time_utc'])<=captured:continue
  rows.append(events.validate_forecast(r,now()))
 return rows

def report(forecasts,settled):
 results={};nowstamp=now().isoformat()
 for sport in ['cfb','nhl']:
  fs=[f for f in forecasts.values() if f['sport']==sport];paired=[]
  for f in fs:
   s=settled.get(f['forecast_key'])
   if not s:continue
   if s['forecast_event_sha256']!=f['event_sha256']:raise ValueError('Settlement receipt does not match forecast')
   paired.append((f,s))
  n=len(paired);entry={'captured_games':len(fs),'paired_settled_games':n,'pending_games':len(fs)-n,'required_new_paired_finals_before_review':CONFIG['minimum_paired_finals'][sport],'minimum_review_sample_reached':n>=CONFIG['minimum_paired_finals'][sport],'production_promoted':False,'metrics':{}}
  for name,col in [('reference','reference_home_win_prob'),('confidence_challenger','challenger_home_win_prob')]:
   entry['metrics'][name]=audit.summarize([f[col] for f,s in paired],[s['actual_home_win'] for f,s in paired])
  results[sport]=entry
 return {'version':CONFIG['version'],'as_of_utc':nowstamp,'status':'prospective_confidence_research_only','comparison':'fresh reference and confidence challenger on the same captured inputs; original first forecasts unchanged','results':results}

def main():
 a=argparse.ArgumentParser();a.add_argument('--reference-python',required=True);a.add_argument('--nhl-root',default=str(RUNTIME/'nhl_reference'));a.add_argument('--sport',choices=['cfb','nhl','both'],default='both');args=a.parse_args()
 versions={k:importlib.metadata.version(k) for k in RESEARCH_VERSIONS}
 if versions!=RESEARCH_VERSIONS:raise ValueError('Frozen challenger environment changed: '+str(versions))
 OUT.mkdir(parents=True,exist_ok=True)
 protected=[ROOT/'model/cfb/v1/frozen_bundle.joblib',ROOT/'data/cfb/ledger/prediction_ledger.csv',Path(args.nhl_root)/'model/nhl/v2_research/watchlist.joblib',Path(args.nhl_root)/'data/nhl/v2_research/prediction_ledger.csv']
 before={str(p):sha(p) for p in protected if p.exists()}
 fs=events.read_events(OUT/'forecasts.jsonl','forecast_key');ss=events.read_events(OUT/'settlements.jsonl','forecast_key');health={'checked_at_utc':now().isoformat(),'sports':{},'errors':[]};new_forecasts=[];new_settlements=[]
 try:
  for sport in (['cfb','nhl'] if args.sport=='both' else [args.sport]):
   snapshot,official,coverage=(cfb_inputs if sport=='cfb' else nhl_inputs)(fs);health['sports'][sport]=coverage
   new_forecasts+=forecasts(snapshot,args.reference_python,args.nhl_root)
   for key,f in fs.items():
    if f['sport']!=sport or key in ss or int(f['game_id']) not in official:continue
    new_settlements.append(events.settlement(f,official[int(f['game_id'])],now()))
  if any(sha(p)!=digest for p,digest in before.items()):raise ValueError('Protected reference or original ledger changed')
  append_time=now();eligible=[r for r in new_forecasts if events.stamp(r['start_time_utc'])>append_time]
  health['dropped_crossed_start_before_persistence']=len(new_forecasts)-len(eligible)
  for r in eligible:events.validate_forecast(r,append_time)
  new_forecasts=eligible
  health['new_paired_forecasts']=events.append(OUT/'forecasts.jsonl',new_forecasts,'forecast_key');health['new_settlements']=events.append(OUT/'settlements.jsonl',new_settlements,'forecast_key')
  summary=report(events.read_events(OUT/'forecasts.jsonl','forecast_key'),events.read_events(OUT/'settlements.jsonl','forecast_key'));(OUT/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');print(json.dumps(health,indent=2),flush=True)
 except Exception as exc:
  health['errors'].append(f'{type(exc).__name__}: {exc}');raise
 finally:(OUT/'health.json').write_text(json.dumps(health,indent=2)+'\n')
if __name__=='__main__':main()
