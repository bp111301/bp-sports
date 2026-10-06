"""Chronological calibration of saved, season-walk-forward leader predictions.

First OOF season is calibration warm-up only. Each later season is calibrated
using earlier OOF seasons, never its own labels. Fixed three-method comparison.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

DEV=['20212022','20222023','20232024','20242025']
METHODS=['raw','temperature','sigmoid']

def fit_calibrator(method,p,y):
    p=np.clip(np.asarray(p,dtype=float),1e-6,1-1e-6);y=np.asarray(y)
    if method=='raw':return {'method':method}
    if len(p)==0 or len(np.unique(y))<2:raise ValueError('Calibration requires earlier OOF labels from both classes')
    if method=='temperature':
        z=logit(p)
        result=minimize_scalar(lambda t:log_loss(y,expit(z/t),labels=[0,1]),bounds=(.25,4.),method='bounded',options={'xatol':1e-8})
        if not result.success:raise ValueError('Temperature fit failed')
        return {'method':method,'temperature':float(result.x)}
    if method=='sigmoid':
        m=LogisticRegression(C=1.,solver='lbfgs',max_iter=3000).fit(logit(p).reshape(-1,1),y)
        return {'method':method,'slope':float(m.coef_[0,0]),'intercept':float(m.intercept_[0])}
    raise ValueError(method)

def apply_calibrator(spec,p):
    p=np.asarray(p,dtype=float)
    if spec['method']=='raw':return p.copy()
    z=logit(np.clip(p,1e-6,1-1e-6))
    if spec['method']=='temperature':return expit(z/spec['temperature'])
    if spec['method']=='sigmoid':return expit(spec['slope']*z+spec['intercept'])
    raise ValueError(spec)

def chronological(d,method):
    d=d.sort_values(['season','game_date','game_id']).copy();out=[];fits=[]
    for season in sorted(d.season.unique()):
        earlier=d[d.season<season];current=d[d.season==season].copy()
        spec={'method':'raw'} if earlier.empty else fit_calibrator(method,earlier.home_win_prob,earlier.home_win)
        current['calibrated_prob']=apply_calibrator(spec,current.home_win_prob);current['method']=method;out.append(current)
        fits.append({'season':str(season),'calibration_seasons':sorted(earlier.season.unique().tolist()),'calibration_games':len(earlier),'spec':spec})
    return pd.concat(out,ignore_index=True),fits

def metrics(d,column='calibrated_prob'):
    y=d.home_win.to_numpy();p=d[column].to_numpy()
    return {'games':len(d),'accuracy':float(accuracy_score(y,p>=.5)),'brier':float(brier_score_loss(y,p)),'log_loss':float(log_loss(y,p,labels=[0,1]))}

def bucket_table(d,column='calibrated_prob'):
    p=d[column].to_numpy();y=d.home_win.to_numpy();confidence=np.maximum(p,1-p);correct=((p>=.5)==y).astype(float)
    bins=[.5,.55,.60,.65,.70,.75,.80,.90,1.000001];rows=[]
    for low,high in zip(bins[:-1],bins[1:]):
        mask=(confidence>=low)&(confidence<high);n=int(mask.sum());k=int(correct[mask].sum());rate=k/n if n else None
        if n:
            den=1+1.96**2/n;center=(rate+1.96**2/(2*n))/den;half=1.96*np.sqrt(rate*(1-rate)/n+1.96**2/(4*n*n))/den
        rows.append({'bucket':f'{low:.0%}–{min(high,1):.0%}','games':n,'wins':k,'mean_predicted':float(confidence[mask].mean()) if n else None,'actual_win_rate':rate,'wilson_low':float(center-half) if n else None,'wilson_high':float(center+half) if n else None})
    return rows

def reliability(d):
    rows=[];ece=0.;p=d.calibrated_prob.to_numpy();y=d.home_win.to_numpy()
    for i in range(10):
        mask=(p>=i/10)&(p<(i+1)/10 if i<9 else p<=1);n=int(mask.sum())
        pred=float(p[mask].mean()) if n else None;actual=float(y[mask].mean()) if n else None
        if n:ece+=n/len(d)*abs(pred-actual)
        rows.append({'home_probability_bin':f'{i/10:.0%}–{(i+1)/10:.0%}','games':n,'predicted':pred,'actual_home_win_rate':actual})
    return rows,float(ece)

def main():
    path=Path('research/nhl/results/factor_oof_predictions.csv');d=pd.read_csv(path,dtype={'season':str});d=d[d.candidate=='advanced_all_w20'].copy()
    if set(d.season)!=set(DEV) or d.game_id.duplicated().any() or len(d)!=5248:raise ValueError('Unexpected leader OOF source')
    if not np.isfinite(d.home_win_prob).all() or not d.home_win_prob.between(0,1).all():raise ValueError('Invalid probabilities')
    parts={};results=[];fits={}
    for method in METHODS:
        q,f=chronological(d,method);parts[method]=q;fits[method]=f
        evaluation=q[q.season>DEV[0]]
        results.append({'method':method,'evaluation':metrics(evaluation),'all_development':metrics(q),'by_season':[{'season':s,**metrics(z)} for s,z in q.groupby('season')]})
    reference=results[0]
    for r in results:
        r['seasons_with_brier_improvement']=sum(a['brier']<b['brier'] for a,b in zip(r['by_season'],reference['by_season']))
        r['eligible_for_promotion']=r['method']!='raw' and r['evaluation']['brier']<reference['evaluation']['brier'] and r['evaluation']['log_loss']<reference['evaluation']['log_loss'] and r['evaluation']['accuracy']>=reference['evaluation']['accuracy'] and r['seasons_with_brier_improvement']>=3
    eligible=[r for r in results if r['eligible_for_promotion']]
    selected=min(eligible,key=lambda r:(r['evaluation']['brier'],r['evaluation']['log_loss']))['method'] if eligible else 'raw'
    q=parts[selected];final_spec=fit_calibrator(selected,d.home_win_prob,d.home_win);buckets=bucket_table(q);rel,ece=reliability(q)
    payload={'candidate':'advanced_all_w20','selection_seasons':DEV,'excluded_from_selection':['20252026'],'warmup_season':DEV[0],'calibration_evaluation_seasons':DEV[1:],'ranking':results,'selected_method':selected,'final_calibrator':final_spec,'fit_audit':fits,'selected_confidence_buckets':buckets,'home_probability_reliability':rel,'ece_fixed_home_deciles':ece,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'decision_rule':'improve Brier/log loss, preserve accuracy, improve Brier in >=3/4 seasons (warmup is raw for all methods)','limitations':'Reused development seasons; binomial intervals are descriptive, not a guarantee of future performance or independence.'}
    out=Path('research/nhl/results');(out/'calibration.json').write_text(json.dumps(payload,indent=2)+'\n');pd.concat(parts.values(),ignore_index=True).to_csv(out/'calibration_oof_predictions.csv',index=False)
    lines=['# NHL Leader Calibration','','Each season uses only earlier season OOF labels. 2021–22 is warm-up; fair calibration comparison is 2022–23 through 2024–25 (3,936 games). No 2025–26 input.','','| Method | Accuracy | Brier | Log loss | Seasons improved | Eligible |','|---|---:|---:|---:|---:|---|']
    for r in results:
        z=r['evaluation'];lines.append(f"| {r['method']} | {z['accuracy']:.2%} | {z['brier']:.6f} | {z['log_loss']:.6f} | {r['seasons_with_brier_improvement']} | {r['eligible_for_promotion']} |")
    lines+=['',f'Selected method: **{selected}**.','', '## Selected confidence buckets (all development, 5,248 games)','','| Predicted winner confidence | Games | Mean confidence | Actual win rate | 95% Wilson interval |','|---|---:|---:|---:|---|']
    for r in buckets:
        if r['games']:lines.append(f"| {r['bucket']} | {r['games']} | {r['mean_predicted']:.2%} | {r['actual_win_rate']:.2%} | {r['wilson_low']:.2%}–{r['wilson_high']:.2%} |")
        else:lines.append(f"| {r['bucket']} | 0 | — | — | — |")
    lines+=['',payload['limitations']];(out/'CALIBRATION.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
