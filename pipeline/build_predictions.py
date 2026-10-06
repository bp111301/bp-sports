"""Build frozen B.P. Sports V4 pregame predictions from current nflverse data."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import joblib,numpy as np,pandas as pd
ALIASES={'STL':'LA','LAR':'LA','SD':'LAC','OAK':'LV','JAC':'JAX'}
COLS=['game_id','season','week','game_date','posteam','defteam','epa','success','pass_attempt','rush_attempt','yards_gained','play_type','qb_kneel','qb_spike','qb_dropback','passer_player_id','passer_player_name','cpoe','sack','interception','fumble_lost','down']
def logit(p): p=np.clip(np.asarray(p,float),.001,.999); return np.log(p/(1-p))
def sigmoid(x): return 1/(1+np.exp(-x))
def kickoff_utc(f): return pd.to_datetime(f.gameday.astype(str)+' '+f.gametime.fillna('12:00').astype(str)).dt.tz_localize('America/New_York').dt.tz_convert('UTC')
def load_inputs(root,season):
 s=pd.read_csv(root/'schedules.csv');s=s[s.season.eq(season)].copy()
 for c in ['home_team','away_team']:s[c]=s[c].replace(ALIASES)
 s['gameday']=pd.to_datetime(s.gameday);s['kickoff_utc']=kickoff_utc(s)
 p=pd.read_csv(root/f'play_by_play_{season}.csv.gz',usecols=lambda c:c in COLS,low_memory=False)
 for c in ['posteam','defteam']:p[c]=p[c].replace(ALIASES)
 p['gameday']=pd.to_datetime(p.game_date);return s,p
def team_games(pbp,sched,asof):
 done=sched[sched.home_score.notna()&sched.away_score.notna()&(sched.kickoff_utc<asof)].copy()
 p=pbp[pbp.game_id.isin(done.game_id)&pbp.posteam.notna()&pbp.defteam.notna()].copy()
 s=p[p.play_type.isin(['pass','run'])&pd.to_numeric(p.qb_kneel,errors='coerce').fillna(0).eq(0)&pd.to_numeric(p.qb_spike,errors='coerce').fillna(0).eq(0)].copy()
 for c in ['epa','success','pass_attempt','rush_attempt','yards_gained','interception','fumble_lost','down']:s[c]=pd.to_numeric(s[c],errors='coerce')
 pa=s.pass_attempt.fillna(0).eq(1);ra=s.rush_attempt.fillna(0).eq(1);s['pass_value']=s.epa.where(pa);s['rush_value']=s.epa.where(ra);s['exp_pass']=s.yards_gained.ge(20).astype(float).where(pa);s['exp_rush']=s.yards_gained.ge(10).astype(float).where(ra);s['giveaway']=s.interception.fillna(0)+s.fumble_lost.fillna(0);s['early_success']=s.success.where(s['down'].isin([1,2]))
 keys=['game_id','season','week','game_date','posteam','defteam']
 off=s.groupby(keys,as_index=False).agg(off_epa=('epa','mean'),off_success=('success','mean'),pass_epa=('pass_value','mean'),rush_epa=('rush_value','mean'),off_exp_pass=('exp_pass','mean'),off_exp_rush=('exp_rush','mean'),off_giveaways=('giveaway','sum'),off_plays=('epa','size'),early_success=('early_success','mean'))
 opp=off[['game_id','posteam','defteam','off_epa','off_success','off_exp_pass','off_exp_rush','off_giveaways','off_plays','early_success']].rename(columns={'posteam':'defteam','defteam':'posteam','off_epa':'def_epa','off_success':'def_success','off_exp_pass':'def_exp_pass_allowed','off_exp_rush':'def_exp_rush_allowed','off_giveaways':'takeaways','off_plays':'opp_plays','early_success':'def_early_success_allowed'})
 tg=off.merge(opp,on=['game_id','posteam','defteam'],validate='one_to_one').rename(columns={'posteam':'team','defteam':'opponent'});meta=[]
 for side,other in [('home','away'),('away','home')]:
  x=done[['game_id','gameday',f'{side}_team',f'{other}_team',f'{side}_score',f'{other}_score']].copy();x.columns=['game_id','gameday','team','opponent','team_score','opp_score'];x['margin']=x.team_score-x.opp_score;meta.append(x)
 tg=tg.merge(pd.concat(meta),on=['game_id','team','opponent'],validate='one_to_one').sort_values(['gameday','game_id','team']).reset_index(drop=True)
 for m in ['off_epa','def_epa']:tg[f'{m}_prior']=tg.groupby('team')[m].transform(lambda z:z.shift(1).expanding(min_periods=1).mean())
 o=tg[['game_id','team','off_epa_prior','def_epa_prior']].rename(columns={'team':'opponent','off_epa_prior':'opp_off_prior','def_epa_prior':'opp_def_prior'});tg=tg.merge(o,on=['game_id','opponent'],validate='one_to_one');tg['adjusted_off_epa']=tg.off_epa-tg.opp_def_prior.fillna(0);tg['adjusted_def_epa']=tg.def_epa-tg.opp_off_prior.fillna(0);tg['off_give_rate']=tg.off_giveaways/tg.off_plays.replace(0,np.nan);tg['def_take_rate']=tg.takeaways/tg.opp_plays.replace(0,np.nan);return done,tg
def elo(bundle,done):
 r=dict(bundle['elo_start_2026'])
 for g in done.sort_values(['gameday','game_id']).itertuples():
  h,a=r.get(g.home_team,1500),r.get(g.away_team,1500);p=1/(1+10**(-(h-a+65*float(g.location=='Home'))/400));y=.5 if g.home_score==g.away_score else float(g.home_score>g.away_score);d=20*(y-p);r[g.home_team]=h+d;r[g.away_team]=a-d
 return r
def profile(tg,team,date):
 h=tg[(tg.team==team)&(tg.gameday<pd.Timestamp(date))].sort_values(['gameday','game_id'])
 if len(h)<2:raise ValueError(f'{team} has fewer than two prior games')
 m=lambda c,n=None:h[c].tail(n).mean() if n else h[c].mean()
 return {'margin_season':m('margin'),'margin_5':m('margin',5),'off_success_5':m('off_success',5),'def_success_5':m('def_success',5),'pass_epa_5':m('pass_epa',5),'rush_epa_5':m('rush_epa',5),'adjusted_off_epa_season':m('adjusted_off_epa'),'adjusted_def_epa_season':m('adjusted_def_epa'),'adjusted_off_epa_5':m('adjusted_off_epa',5),'adjusted_def_epa_5':m('adjusted_def_epa',5),'rest_days':float(np.clip((pd.Timestamp(date)-h.gameday.max()).days,3,21))}
def base_features(targets,tg,ratings):
 rows=[]
 for r in targets.itertuples():
  h,a=profile(tg,r.home_team,r.gameday),profile(tg,r.away_team,r.gameday);x={'game_id':r.game_id,'home_field':float(r.location=='Home'),'div_game':float(r.div_game),'elo_rating_diff':ratings.get(r.home_team,1500)-ratings.get(r.away_team,1500)}
  for k in h:x[f'{k}_diff']=h[k]-a[k]
  rows.append(x)
 return pd.DataFrame(rows)
def qb_games(pbp,done):
 d=pbp[pbp.game_id.isin(done.game_id)&pd.to_numeric(pbp.qb_dropback,errors='coerce').fillna(0).eq(1)&pbp.passer_player_id.notna()].copy()
 for c in ['epa','cpoe','sack','interception']:d[c]=pd.to_numeric(d[c],errors='coerce')
 d['sack']=d.sack.fillna(0);d['interception']=d.interception.fillna(0);q=d.groupby(['game_id','season','week','game_date','posteam','passer_player_id'],as_index=False).agg(dropbacks=('qb_dropback','sum'),epa_sum=('epa','sum'),cpoe_sum=('cpoe','sum'),cpoe_n=('cpoe','count'),sacks=('sack','sum'),ints=('interception','sum'));q['gameday']=pd.to_datetime(q.game_date);return q.sort_values(['gameday','game_id'])
def qb_state(b,q,pid,date):
 if pd.isna(pid):return dict(qb_prior_db=np.nan,qb_career_epa=np.nan,qb_career_cpoe=np.nan,qb_recent5_epa=np.nan)
 seed=b['qb_summary_through_2025'];z=seed[seed.passer_player_id.eq(pid)];base={k:0. for k in ['dropbacks','epa_sum','cpoe_sum','cpoe_n','sacks','ints']}
 if len(z):base.update({k:float(z.iloc[0][k]) for k in base})
 cur=q[(q.passer_player_id==pid)&(q.gameday<pd.Timestamp(date))];tot={k:base[k]+float(cur[k].sum()) for k in base};recent=pd.concat([b['qb_last5_through_2025'][b['qb_last5_through_2025'].passer_player_id.eq(pid)],cur],ignore_index=True).sort_values(['gameday','game_id']).tail(5);rdb=recent.dropbacks.sum()
 return {'qb_prior_db':tot['dropbacks'],'qb_career_epa':tot['epa_sum']/tot['dropbacks'] if tot['dropbacks'] else np.nan,'qb_career_cpoe':tot['cpoe_sum']/tot['cpoe_n'] if tot['cpoe_n'] else np.nan,'qb_recent5_epa':recent.epa_sum.sum()/rdb if rdb else np.nan}
def prev_qb(b,q,team,date):
 z=q[(q.posteam==team)&(q.gameday<pd.Timestamp(date))]
 if len(z):
  last=z.gameday.max();x=z[z.gameday.eq(last)].groupby('passer_player_id',as_index=False).dropbacks.sum().sort_values('dropbacks',ascending=False);return x.iloc[0].passer_player_id
 return b['last_starter_2025'].get(team,np.nan)
def qb_features(b,q,targets,over):
 rows=[]
 for r in targets.itertuples():
  x={'game_id':r.game_id};cfg=over.get(r.game_id,{})
  for side in ['home','away']:
   team=getattr(r,f'{side}_team');pid=getattr(r,f'{side}_qb_id');name=getattr(r,f'{side}_qb_name');ov=cfg.get(side,{})
   if ov.get('team') in (None,team):pid=ov.get('qb_id',pid);name=ov.get('qb_name',name)
   st=qb_state(b,q,pid,r.gameday);prev=prev_qb(b,q,team,r.gameday);ps=qb_state(b,q,prev,r.gameday);chg=float(pd.notna(pid) and pd.notna(prev) and pid!=prev);x[f'{side}_qb_name_assumed']=name;x[f'{side}_qb_changed']=chg
   for k,v in st.items():x[f'{side}_{k}']=v
   x[f'{side}_qb_shock_epa']=0. if not chg else st['qb_career_epa']-ps['qb_career_epa'];x[f'{side}_qb_shock_recent']=0. if not chg else st['qb_recent5_epa']-ps['qb_recent5_epa']
  for c in ['qb_career_epa','qb_career_cpoe','qb_recent5_epa','qb_shock_epa','qb_shock_recent']:x[f'{c}_diff']=x[f'home_{c}']-x[f'away_{c}']
  x['qb_changed_diff']=x['home_qb_changed']-x['away_qb_changed'];x['qb_experience_diff']=np.log1p(x['home_qb_prior_db'])-np.log1p(x['away_qb_prior_db']);rows.append(x)
 return pd.DataFrame(rows)
def risk(tg,targets):
 rows=[]
 for r in targets.itertuples():
  v={}
  for side in ['home','away']:
   h=tg[(tg.team==getattr(r,f'{side}_team'))&(tg.gameday<pd.Timestamp(r.gameday))].sort_values(['gameday','game_id']).tail(5);v[f'{side}_net']=h.off_exp_pass.mean()+h.off_exp_rush.mean()-h.def_exp_pass_allowed.mean()-h.def_exp_rush_allowed.mean();v[f'{side}_give']=h.off_give_rate.mean();v[f'{side}_take']=h.def_take_rate.mean();v[f'{side}_early']=h.early_success.mean();v[f'{side}_defearly']=h.def_early_success_allowed.mean()
  rows.append({'game_id':r.game_id,'net_explosive_5':v['home_net']-v['away_net'],'to_recent_edge_5':(v['away_give']+v['home_take'])-(v['home_give']+v['away_take']),'early_success_matchup_5':(v['home_early']-v['away_defearly'])-(v['away_early']-v['home_defearly'])})
 return pd.DataFrame(rows)
def append_ledger(path,feed,at):
 x=feed.copy();x['snapshot_id']=at.strftime('%Y%m%dT%H%M%SZ');x['prediction_id']=x.snapshot_id+':'+x.game_id;x['actual_home_score']=np.nan;x['actual_away_score']=np.nan;x['settlement_status']='pending';x['scored_at_utc']='';path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():
  old=pd.read_csv(path);x=x[~x.prediction_id.isin(old.get('prediction_id',pd.Series(dtype=str)))];x=pd.concat([old,x],ignore_index=True)
 x.to_csv(path,index=False)
def main():
 p=argparse.ArgumentParser();p.add_argument('--season',type=int,required=True);p.add_argument('--week',type=int);p.add_argument('--as-of');p.add_argument('--data-dir',default='data/current');p.add_argument('--bundle',default='model/v4/frozen_bundle.joblib');p.add_argument('--overrides',default='config/qb_overrides.json');p.add_argument('--ledger',default='data/ledger/prediction_ledger.csv');a=p.parse_args();root=Path(a.data_dir);b=joblib.load(a.bundle);over=json.loads(Path(a.overrides).read_text()) if Path(a.overrides).exists() else {};at=pd.Timestamp(a.as_of) if a.as_of else pd.Timestamp.now(tz='UTC');at=at.tz_localize('UTC') if at.tzinfo is None else at.tz_convert('UTC');sched,pbp=load_inputs(root,a.season);done,tg=team_games(pbp,sched,at);cur=sched[sched.game_type.eq('REG')].copy();future=cur[(cur.kickoff_utc>at)&cur.home_score.isna()&cur.away_score.isna()];week=a.week or int(future.week.min());targets=future[future.week.eq(week)].copy().sort_values(['gameday','gametime','game_id'])
 if targets.empty:raise ValueError('No unstarted target games')
 base=base_features(targets,tg,elo(b,done));q=qb_features(b,qb_games(pbp,done),targets,over);rf=risk(tg,targets);x=targets[['game_id','away_team','home_team','gameday','gametime','away_qb_id','away_qb_name','home_qb_id','home_qb_name']].merge(base,on='game_id').merge(q,on='game_id').merge(rf,on='game_id')
 m=b['v3'];v3=m['win_model'].predict_proba(x[m['features']])[:,1]
 if m.get('calibrator') is not None:v3=m['calibrator'].predict_proba(logit(v3).reshape(-1,1))[:,1]
 pc=b['qb_change_model'].predict_proba(x[b['base_features']+b['qb_change_features']])[:,1];pq=b['qb_quality_model'].predict_proba(x[b['base_features']+b['qb_quality_features']])[:,1];pc=b['qb_change_calibrator'].predict_proba(logit(pc).reshape(-1,1))[:,1];pq=b['qb_quality_calibrator'].predict_proba(logit(pq).reshape(-1,1))[:,1];v4=.5*v3+.5*(.75*pc+.25*pq);side=v4>=.5;th=b['risk_thresholds'];mult=np.ones(len(x));ee=x.net_explosive_5.abs().to_numpy()>=th['explosive_last5_abs_q75'];es=x.net_explosive_5.to_numpy()>=0;mult[ee&(side==es)]*=1.2;mult[ee&(side!=es)]*=.6;adj=sigmoid(logit(v4)*mult);te=x.to_recent_edge_5.abs().to_numpy()>=th['turnover_last5_abs_q75'];ts=x.to_recent_edge_5.to_numpy()>=0;tf=te&(side!=ts);adj[tf]=.5+(adj[tf]-.5)*.7;de=x.early_success_matchup_5.abs().to_numpy()>=th['early_success_last5_abs_q75'];ds=x.early_success_matchup_5.to_numpy()>=0;df=de&(side!=ds);adj[df]=.5+(adj[df]-.5)*.7
 f=x[['game_id','away_team','home_team']].copy();f['v3_pick']=np.where(v3>=.5,f.home_team,f.away_team);f['v3_confidence']=np.maximum(v3,1-v3);f['v4_pick']=np.where(v4>=.5,f.home_team,f.away_team);f['v4_core_confidence']=np.maximum(v4,1-v4);f['v4_adjusted_confidence']=np.maximum(adj,1-adj);f['explosive_extreme']=ee;f['turnover_risk_flag']=tf;f['early_down_risk_flag']=df;pending=cur[(cur.home_score.isna()|cur.away_score.isna())&(cur.week<week)];pt=set(pending.home_team)|set(pending.away_team);f['prediction_status']=np.where(f.home_team.isin(pt)|f.away_team.isin(pt),'PROVISIONAL_REFRESH_AFTER_PENDING_GAME','EARLY_LOCK');notes=[]
 for r in targets.itertuples():
  cfg=over.get(r.game_id,{});note=''
  for s in ['home','away']:
   if cfg.get(s,{}).get('status_note'):note=cfg[s]['status_note']
  notes.append(note)
 f['qb_status_flag']=notes;f['captured_at_utc']=at.isoformat();assert np.all((v4>=.5)==(adj>=.5)) and b['market_used_for_pick'] is False;display=f.copy();oldp=root/'website_feed.csv'
 if oldp.exists():
  old=pd.read_csv(oldp);started=set(cur[cur.week.eq(week)].game_id)-set(f.game_id);keep=old[old.game_id.isin(started)] if 'game_id' in old else pd.DataFrame()
  if len(keep):display=pd.concat([keep,f],ignore_index=True).drop_duplicates('game_id',keep='last')
 display.to_csv(root/'website_feed.csv',index=False);append_ledger(Path(a.ledger),f,at);meta={'season':a.season,'week':week,'captured_at_utc':at.isoformat(),'completed_games_used':len(done),'target_games':len(f),'display_games':len(display),'bundle_version':b['bundle_version'],'market_used_for_pick':False,'pending_earlier_games':pending.game_id.tolist()};(root/'prediction_metadata.json').write_text(json.dumps(meta,indent=2)+'\n');print(display.to_string(index=False))
if __name__=='__main__':main()
