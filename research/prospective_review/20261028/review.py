"""Read-only prospective review. No fitting or forecast/settlement writes."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).parent
INPUT=ROOT/'inputs'
NOW=pd.Timestamp('2026-10-28T23:08:00Z')
RNG=np.random.default_rng(20261028)
def ts(s):return pd.to_datetime(s,utc=True,format='mixed',errors='coerce')
def wilson(w,n):
    if not n:return [None,None]
    z=1.959963984540054;p=w/n;den=1+z*z/n
    a=(p+z*z/(2*n))/den;b=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [a-b,a+b]
def metric(d):
    if not len(d):return {'n':0}
    p=d.p.to_numpy(float);y=d.y.to_numpy(float);q=np.clip(p,1e-12,1-1e-12)
    c=np.maximum(p,1-p);ok=(p>=.5)==y
    return dict(n=len(d),wins=int(ok.sum()),losses=int((~ok).sum()),accuracy=float(ok.mean()),accuracy_ci95=wilson(ok.sum(),len(d)),mean_confidence=float(c.mean()),expected_wins=float(c.sum()),brier=float(np.mean((p-y)**2)),log_loss=float(np.mean(-y*np.log(q)-(1-y)*np.log(1-q))),home_win_rate=float(y.mean()),home_pick_rate=float(np.mean(p>=.5)))
def sections(d):
    out={'overall':metric(d),'confidence':{},'weekly':{},'pick_side':{},'high_confidence_misses':[]}
    for lo,hi in [(0.5,.6),(.6,.7),(.7,.8),(.8,.9),(.9,1.000001)]:
        x=d[d.conf.ge(lo)&d.conf.lt(hi)];out['confidence'][f'{lo:.0%}–{min(hi,1):.0%}']=metric(x)
    for wk,x in d.groupby(d.start.dt.tz_convert('America/Chicago').dt.strftime('%G-W%V')):out['weekly'][wk]=metric(x)
    for label,mask in [('home',d.p.ge(.5)),('away',d.p.lt(.5))]:out['pick_side'][label]=metric(d[mask])
    for threshold in [.6,.7,.8,.9]:out[f'selected_ge_{threshold}']=metric(d[d.conf.ge(threshold)])
    x=d[((d.p>=.5)!=d.y)].sort_values('conf',ascending=False).head(12)
    out['high_confidence_misses']=[dict(game_id=str(r.game_id),home=r.home_team,away=r.away_team,confidence=r.conf,start=r.start.isoformat()) for r in x.itertuples()]
    out['baselines']={'always_home_accuracy':float(d.y.mean()),'coin_brier':.25,'coin_log_loss':math.log(2),'fixed_home_55':metric(d.assign(p=.55))}
    return out
def compare(a,b):
    d=a[['game_id','p','y','start']].merge(b[['game_id','p','y']],on='game_id',suffixes=('_a','_b'),validate='one_to_one')
    assert np.all(d.y_a==d.y_b)
    y=d.y_a.to_numpy(float);a=d.p_a.to_numpy(float);b=d.p_b.to_numpy(float)
    acc=((b>=.5)==y).astype(float)-((a>=.5)==y).astype(float)
    br=(b-y)**2-(a-y)**2
    log=lambda p:-y*np.log(np.clip(p,1e-12,1-1e-12))-(1-y)*np.log(np.clip(1-p,1e-12,1-1e-12))
    ll=log(b)-log(a)
    out={'n':len(d),'winner_disagreements':int(np.sum((a>=.5)!=(b>=.5))),'challenger_only_correct':int(np.sum(acc==1)),'control_only_correct':int(np.sum(acc==-1))}
    if not len(d):return out
    ix=RNG.integers(0,len(d),(10000,len(d)))
    days=d.start.dt.tz_convert('America/Chicago').dt.strftime('%Y-%m-%d').to_numpy();unique=np.unique(days)
    clusters=RNG.integers(0,len(unique),(10000,len(unique)))
    counts=np.array([np.sum(days==day) for day in unique])
    for name,v in [('accuracy',acc),('brier',br),('log_loss',ll)]:
        sums=np.array([v[days==day].sum() for day in unique]);boot=sums[clusters].sum(axis=1)/counts[clusters].sum(axis=1)
        out[name]={'challenger_minus_control':float(v.mean()),'paired_game_ci95':np.quantile(v[ix].mean(axis=1),[.025,.975]).tolist(),'paired_day_block_ci95':np.quantile(boot,[.025,.975]).tolist()}
    out['day_blocks']=len(unique)
    return out
def prep_csv(name,sport):
    d=pd.read_csv(INPUT/(name+'.csv'));d['game_id']=d.game_id.astype(str)
    d['p']=pd.to_numeric(d.home_win_prob,errors='coerce')
    d['start']=ts(d.schedule_kickoff_utc.fillna(d.kickoff_utc)) if sport=='CFB' else ts(d.start_time_utc)
    d['created']=ts(d.snapshot_created_utc if sport=='CFB' else d.created_at_utc)
    d['settled']=d.correct.notna() if sport=='CFB' else d.status.eq('settled')
    d['y']=np.where(d.actual_winner==d.home_team,1.,np.where(d.actual_winner==d.away_team,0.,np.nan)) if sport=='CFB' else pd.to_numeric(d.actual_home_win,errors='coerce')
    d['conf']=np.maximum(d.p,1-d.p)
    return d
def audit(d,group=None):
    keys=['game_id']+([group] if group else [])
    settled=d[d.settled]
    bad=(d.created.isna()|d.start.isna()|d.created.ge(d.start)|d.created.gt(NOW)|~d.p.between(0,1))
    return dict(rows=len(d),unique_games=int(d.game_id.nunique()),duplicate_keys=int(d.duplicated(keys).sum()),invalid_timing_or_probability=int(bad.sum()),invalid_settled_labels=int((~settled.y.isin([0,1])).sum()),settled_in_future=int(settled.start.gt(NOW).sum()),pending_started=int((~d.settled&d.start.le(NOW)).sum()))
def clean(d):return d[d.settled&d.start.le(NOW)&d.created.lt(d.start)&d.y.isin([0,1])&d.p.between(0,1)].copy()
def main():
    global ROOT,INPUT
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input-dir',type=Path,default=Path('runtime/prospective_review/20261028/inputs'))
    ap.add_argument('--output-dir',type=Path,default=Path('runtime/prospective_review/20261028'))
    args=ap.parse_args();INPUT=args.input_dir;ROOT=args.output_dir;ROOT.mkdir(parents=True,exist_ok=True)
    c=prep_csv('cfb','CFB');b=prep_csv('shadow','CFB');n=prep_csv('nhlledger','NHL')
    consumed={'cfb.csv','shadow.csv','nhlledger.csv','goalie.jsonl','scores.json','provenance.json','schedule_metadata.json','upstream_coverage.json'}
    out={'cutoff_utc':NOW.isoformat(),'provenance':json.loads((INPUT/'provenance.json').read_text()),'input_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(INPUT.iterdir()) if p.name in consumed},'audit':{'cfb':audit(c),'candidate_b':audit(b),'nhl':audit(n,'candidate')}}
    out['audit']['cfb_correct_label_disagreements']=int((c[c.settled].correct!=((c[c.settled].p>=.5)==c[c.settled].y).astype(float)).sum())
    out['audit']['cfb_brier_disagreements']=int((np.abs(c[c.settled].brier-(c[c.settled].p-c[c.settled].y)**2)>1e-10).sum())
    out['audit']['candidate_b_hashes']=b.bundle_sha256.unique().tolist();out['audit']['nhl_hashes']=n.bundle_sha256.unique().tolist()
    out['audit']['cfb_winner_probability_disagreements']=int((c.predicted_winner!=np.where(c.p.ge(.5),c.home_team,c.away_team)).sum())
    out['audit']['candidate_b_before_freeze']=int(b.created.lt(ts(b.bundle_frozen_at_utc)).sum())
    out['cfb_v1']=sections(clean(c));out['cfb_candidate_b']=sections(clean(b));out['cfb_paired']=compare(clean(c),clean(b))
    out['cfb_baseline_paired']=compare(clean(c).assign(p=.55),clean(c))
    ref=clean(n[n.candidate.eq('reference_control')]);out['nhl']={name:sections(clean(d)) for name,d in n.groupby('candidate')}
    out['nhl_paired']={name:compare(ref,clean(d)) for name,d in n.groupby('candidate') if name!='reference_control'}
    out['nhl_baseline_paired']=compare(ref.assign(p=.55),ref)
    pairs=[json.loads(line) for line in (INPUT/'goalie.jsonl').read_text().splitlines() if line]
    p=pd.DataFrame(pairs);p.game_id=p.game_id.astype(str);p['start']=ts(p.start_time_utc);p['created']=ts(p.created_at_utc);p['settled']=p.status.eq('settled');p['y']=pd.to_numeric(p.actual_home_win,errors='coerce')
    versions={}
    for name in ['team_control','inferred_goalie','confirmed_goalie']:
        x=p.copy();x['p']=x.probabilities.map(lambda v:v[name]);x['conf']=np.maximum(x.p,1-x.p);versions[name]=clean(x)
    out['audit']['goalie']=audit(p.assign(p=p.probabilities.map(lambda v:v['team_control'])))
    out['audit']['goalie_bundle_hashes']=p.bundle_sha256.unique().tolist()
    out['audit']['goalie_reference_bundle_hashes']=p.reference_bundle_sha256.unique().tolist()
    out['audit']['goalie_confirmations_invalid']=sum(not all(o.get('confirmed_eligible') and ts(o.get('captured_at_utc'))<ts(r['start_time_utc']) for o in r['goalie_observations'].values()) for r in pairs)
    out['goalie']={name:sections(d) for name,d in versions.items()};out['goalie_paired']={name:compare(versions['team_control'],d) for name,d in versions.items() if name!='team_control'}
    g=versions['team_control'].copy()
    g['pp_missing']=g.feature_snapshot.map(lambda f:f['team_features'].get('pp_rate_20_diff') is None)
    g['other_missing']=g.feature_snapshot.map(lambda f:sum(v is None for k,v in f['team_features'].items() if k!='pp_rate_20_diff'))
    out['goalie_feature_slices']={}
    for name,mask in [('pp_missing',g.pp_missing),('isolated_pp_missing',g.pp_missing&g.other_missing.eq(0)),('pp_present',~g.pp_missing)]:out['goalie_feature_slices'][name]=metric(g[mask])
    score=json.loads((INPUT/'scores.json').read_text());alias={'Louisiana Monroe':'UL Monroe','Southern Mississippi':'Southern Miss','UT San Antonio':'UTSA','Sam Houston State':'Sam Houston','Connecticut':'UConn','UMass':'Massachusetts'}
    canonical=lambda s:alias.get(s,s)
    checks=[];ungraded=[]
    for sport,d in [('CFB',c),('NHL',n[n.candidate.eq('reference_control')])]:
        checked=0;different=[];wrong_team=[];missing=[]
        for row in d.itertuples():
            actual=score.get('games',{}).get(sport+':'+row.game_id)
            if not actual:missing.append(row.game_id);continue
            if canonical(actual['home_team'])!=canonical(row.home_team) or canonical(actual['away_team'])!=canonical(row.away_team):wrong_team.append(row.game_id);continue
            if actual['state']=='final':
                if row.settled:
                    checked+=1;h=actual['home_score'];a=actual['away_score']
                    if int(h>a)!=row.y:different.append(row.game_id)
                else:ungraded.append({'sport':sport,'id':row.game_id,'start':str(row.start)})
        checks.append(dict(sport=sport,checked_finals=checked,label_disagreements=different,team_disagreements=wrong_team,not_in_scorefeed=missing))
    out['audit']['score_crosscheck']=checks;out['audit']['ungraded_confirmed_finals']=ungraded
    out['audit']['cfb_capture_after_original_kickoff']=int(c.created.ge(ts(c.kickoff_utc)).sum())
    out['audit']['cfb_invalid_settlement_timestamp']=int((ts(c.loc[c.settled,'settled_at_utc']).isna()|ts(c.loc[c.settled,'settled_at_utc']).le(c.loc[c.settled,'start'])|ts(c.loc[c.settled,'settled_at_utc']).gt(NOW)).sum())
    out['audit']['nhl_invalid_settlement_timestamp']=int((ts(n.loc[n.settled,'settled_at_utc']).isna()|ts(n.loc[n.settled,'settled_at_utc']).le(n.loc[n.settled,'start'])|ts(n.loc[n.settled,'settled_at_utc']).gt(NOW)).sum())
    out['audit']['nhl_snapshot_after_capture']=int(ts(n.data_snapshot_at_utc).gt(n.created).sum())
    out['audit']['goalie_cutoff_after_capture']=int(ts(p.input_cutoff_utc).gt(p.created).sum())
    out['audit']['goalie_settled_coverage']=dict(paired=len(g),watchlist=len(ref),excluded_from_pair=int(len(ref)-len(g)))
    evidence=json.loads((INPUT/'schedule_metadata.json').read_text())
    if (INPUT/'upstream_coverage.json').exists():out['audit']['cfb_upstream_coverage']=json.loads((INPUT/'upstream_coverage.json').read_text())
    sch=pd.DataFrame(evidence['cfb']);sch.game_id=sch.game_id.astype(str)
    fbs=sch[sch.fbs_game.eq(True)]
    out['audit']['independent_cfb_schedule']=dict(eligible_due_games=len(fbs),missing=fbs[~fbs.game_id.isin(c.game_id)].game_id.tolist(),outside_fbs_only_scope=sch[~sch.fbs_game.eq(True)][['game_id','home_team','away_team']].to_dict('records'))
    nh=pd.DataFrame(evidence['nhl']);nh.game_id=nh.game_id.astype(str)
    out['audit']['independent_nhl_schedule']=dict(eligible_due_games=len(nh),missing=nh[~nh.game_id.isin(n.game_id)].game_id.tolist())
    official=nh[nh.state.isin(['OFF','FINAL'])].merge(ref[['game_id','y']],on='game_id',validate='one_to_one')
    out['audit']['official_nhl_label_disagreements']=int(((official.home_score>official.away_score).astype(int)!=official.y).sum())
    x=clean(c).merge(sch[['game_id','conference_game','neutral_site','home_conference','away_conference']],on='game_id',validate='one_to_one')
    power=['SEC','Big Ten','Big 12','ACC'];power_mask=x.home_conference.isin(power)&x.away_conference.isin(power)
    out['cfb_schedule_slices']={'power_vs_power':metric(x[power_mask]),'other':metric(x[~power_mask]),'conference':metric(x[x.conference_game.eq(True)]),'nonconference':metric(x[x.conference_game.eq(False)]),'neutral_site':metric(x[x.neutral_site.eq(True)])}
    (ROOT/'results.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    for name in ['cfb_v1','cfb_candidate_b']:print(name,json.dumps(out[name]['overall']));print('confidence',json.dumps(out[name]['confidence']))
    print('AUDIT',json.dumps(out['audit']));print('CFB PAIRED',json.dumps(out['cfb_paired']))
    for name,d in out['nhl'].items():print('NHL',name,json.dumps(d['overall']),json.dumps(d['confidence']))
    print('NHL PAIRED',json.dumps(out['nhl_paired']))
    for name,d in out['goalie'].items():print('GOALIE',name,json.dumps(d['overall']))
    print('GOALIE PAIRED',json.dumps(out['goalie_paired']));print('FEATURE SLICES',json.dumps(out['goalie_feature_slices']))
if __name__=='__main__':main()
