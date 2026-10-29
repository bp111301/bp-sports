"""Evaluate the registered confidence-only projections; no model/forecast writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('confidence_projection_audit',ROOT/'confidence_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
SOURCES={
    'cfb':('research/strength_challengers_20261028/results/cfb/development_predictions.csv.gz','strength_nonlinear50','f1dbeba23a4c6c729248c0116ce42fd95fe6845d'),
    'nhl':('research/feature_challengers_20261028/results/nhl/predictions.csv.gz','pooled_rates','d4963d192d2f04c1655a20d4e268a74aa54c07ad'),
}


def project(reference,challenger):
    p,q=np.asarray(reference,float),np.asarray(challenger,float)
    if p.shape!=q.shape or not np.isfinite(p).all() or not np.isfinite(q).all() or ((p<0)|(p>1)|(q<0)|(q>1)).any():
        raise ValueError('Invalid probability arrays')
    result=np.where(p>=.5,np.maximum(q,.5),np.where(q>=.5,.499999,q))
    if not np.array_equal(p>=.5,result>=.5):raise ValueError('Original selected winner changed')
    return result


def summary(g,sport):
    recent=g[g.season.ge('2023' if sport=='cfb' else '20232024')]
    return {'overall':audit.summarize(g.probability,g.home_win),
        'by_season':[{'season':s,**audit.summarize(x.probability,x.home_win)} for s,x in g.groupby('season')],
        'recent':audit.summarize(recent.probability,recent.home_win)}


def probability_intervals(d):
    y=d.home_win.to_numpy(float);p=d.reference_probability.to_numpy(float);q=d.probability.to_numpy(float)
    loss=lambda a:-y*np.log(np.clip(a,1e-12,1-1e-12))-(1-y)*np.log(np.clip(1-a,1e-12,1-1e-12))
    delta=pd.DataFrame({'brier':(q-y)**2-(p-y)**2,'log_loss':loss(q)-loss(p),'block':d.block.to_numpy()})
    sums=delta.groupby('block')[['brier','log_loss']].sum().to_numpy();counts=delta.groupby('block').size().to_numpy()
    rng=np.random.default_rng(20261028);ix=rng.integers(0,len(counts),(2000,len(counts)))
    draws=sums[ix].sum(axis=1)/counts[ix].sum(axis=1)[:,None]
    return {name:{'challenger_minus_control':float(delta[name].mean()),'paired_block_95pct':np.quantile(draws[:,i],[.025,.975]).tolist()} for i,name in enumerate(['brier','log_loss'])}


def paired_source(raw,name,sport):
    raw=raw.copy();raw['season']=raw.season.astype(str)
    control=raw[raw.candidate.eq('control')].copy();candidate=raw[raw.candidate.eq(name)].copy()
    if control.duplicated('game_id').any() or candidate.duplicated('game_id').any():raise ValueError('Duplicate source game')
    if control.season.gt('2025' if sport=='cfb' else '20242025').any():raise ValueError('Excluded season in development')
    d=control[['game_id','season','block','home_win','probability']].rename(columns={'probability':'reference_probability'}).merge(
        candidate[['game_id','season','home_win','probability']],on='game_id',validate='one_to_one',suffixes=('','_candidate'))
    if len(d)!=len(control) or len(d)!=len(candidate) or not d.home_win.eq(d.home_win_candidate).all() or not d.season.eq(d.season_candidate).all():
        raise ValueError('Source cohort, season or label mismatch')
    if not d.home_win.isin([0,1]).all() or d.block.isna().any():raise ValueError('Invalid labels or bootstrap blocks')
    d=d.rename(columns={'probability':'underlying_probability'})
    d['probability']=project(d.reference_probability,d.underlying_probability)
    return d


def run(sport,out_dir=None):
    path,name,expected=SOURCES[sport];path=ROOT/path;blob=path.read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()
    if actual!=expected:raise ValueError('Immutable archived source changed')
    d=paired_source(pd.read_csv(path),name,sport)
    if len(d)!=(5733 if sport=='cfb' else 5248):raise ValueError('Unexpected evaluation cohort')
    a=summary(d,sport);b=summary(d.assign(probability=d.reference_probability),sport)
    am,bm=a['overall']['overall'],b['overall']['overall'];ar,br=a['recent']['overall'],b['recent']['overall']
    improved=sum(s['overall']['brier']<r['overall']['brier'] for s,r in zip(a['by_season'],b['by_season']))
    checks={'all_original_winners_preserved':bool(np.array_equal(d.probability.ge(.5),d.reference_probability.ge(.5))),
        'identical_accuracy':am['accuracy']==bm['accuracy'],'brier':am['brier']<bm['brier'],
        'log_loss':am['log_loss']<bm['log_loss'],'ece':a['overall']['ece']<=b['overall']['ece'],
        'season_consistency':improved>=(5 if sport=='cfb' else 3),'recent_brier':ar['brier']<=br['brier'],
        'recent_log_loss':ar['log_loss']<=br['log_loss']}
    oldconf=np.maximum(d.reference_probability,1-d.reference_probability);newconf=np.maximum(d.probability,1-d.probability)
    result={'sport':sport,'status':'adaptively_selected_reused_historical_development_only','objective':'confidence_only_original_picks_unchanged',
        'live_labels_used':False,'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),
        'underlying_source':str(path.relative_to(ROOT)),'underlying_candidate':name,'source_git_blob_sha':actual,'source_sha256':hashlib.sha256(blob).hexdigest(),
        'control':b,'confidence_challenger':a,'research_eligible':bool(all(checks.values())),
        'checks':{k:bool(v) for k,v in checks.items()},'seasons_brier_improved':improved,
        'disagreements_projected_to_even_confidence':int((d.reference_probability.ge(.5)!=d.underlying_probability.ge(.5)).sum()),
        'confidence_increases':int((newconf>oldconf+1e-12).sum()),'confidence_decreases':int((newconf<oldconf-1e-12).sum()),
        'probability_score_intervals':probability_intervals(d),'production_promoted':False,'prospective_shadow_deployed':False}
    out=Path(out_dir) if out_dir else ROOT/'runtime/confidence_projection_20261028'/sport;out.mkdir(parents=True,exist_ok=True)
    d.to_csv(out/'predictions.csv',index=False);(out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'sport':sport,'eligible':result['research_eligible'],'control':bm,'challenger':am,
        'ece_control':b['overall']['ece'],'ece_challenger':a['overall']['ece'],'checks':result['checks']},indent=2))
    return result


if __name__=='__main__':
    for sport in ['cfb','nhl']:run(sport)
