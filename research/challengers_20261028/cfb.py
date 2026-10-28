"""Fixed, pre-2026-only challenger development. Never writes production artifacts."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
import joblib,numpy as np,pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit,logit

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=module('cfb_20261028_base',ROOT/'research/cfb/backtest_baseline.py')
pri=module('cfb_20261028_priors',ROOT/'research/cfb/experiment_priors.py')
NAMES=['control','calibration','recent3_blend50']
def guarded_data(path):
    d=base.load_data(Path(path))
    if d.empty or d.season.max()>2025 or d.season.min()<2015:raise ValueError('CFB development must contain 2015–2025 only; never load live 2026 labels')
    if d.duplicated('game_id').any():raise ValueError('Duplicate historical CFB game IDs')
    return d.reset_index(drop=True)
def matrices(d):
    x=base.build_matrix(d);cf=base.feature_sets(x)['cfb_context'];px=pri.matrix(d,7.)
    rem={f'{f}_diff' for f in pri.BLEND_BASES}|{f'prev_{f}_diff' for f in pri.BLEND_BASES}
    pf=[f for f in cf if f not in rem]+[f'blend_{f}_diff' for f in pri.BLEND_BASES]
    if set(cf+pf)&(base.RETROSPECTIVE_BLOCKLIST|base.MARKET_BLOCKLIST):raise ValueError('Forbidden feature')
    return x,px,cf,pf
def training_index(d,target,recent=False):
    earlier=sorted(d.loc[d.season<target,'season'].unique())
    if recent:earlier=earlier[-3:]
    ix=d.index[d.season.isin(earlier)]
    if not len(ix) or not d.loc[ix,'season'].lt(target).all():raise ValueError('Invalid training boundary')
    return ix
def fit_parts(d,x,px,cf,pf,ix):
    a=base.model(cf);b=base.model(pf)
    a.fit(x.loc[ix,cf],d.loc[ix,'home_win']);b.fit(px.loc[ix,pf],d.loc[ix,'home_win'])
    return a,b
def ensemble(models,x,px,cf,pf,ix,weight=.25):
    return weight*models[0].predict_proba(x.loc[ix,cf])[:,1]+(1-weight)*models[1].predict_proba(px.loc[ix,pf])[:,1]
def calibrate(p,y):
    z=logit(np.clip(np.asarray(p,float),1e-6,1-1e-6));y=np.asarray(y,float)
    if not len(y) or len(set(y))<2:raise ValueError('Insufficient earlier calibration labels')
    result=minimize_scalar(lambda slope:float(np.mean(np.logaddexp(0,slope*z)-y*slope*z)),bounds=(.25,2.),method='bounded')
    if not result.success:raise ValueError('Calibration optimization failed')
    return float(result.x)
def apply_calibration(p,slope):return expit(slope*logit(np.clip(np.asarray(p,float),1e-6,1-1e-6)))
def summarize(predictions):
    return {name:{'overall':base.score(g.home_win.to_numpy(),g.probability.to_numpy()),'by_season':[{**base.score(s.home_win.to_numpy(),s.probability.to_numpy()),'season':int(year)} for year,s in g.groupby('season')],'recent_2023_2025':base.score(g[g.season.ge(2023)].home_win.to_numpy(),g[g.season.ge(2023)].probability.to_numpy())} for name,g in predictions.groupby('candidate')}
def eligibility(scores):
    c=scores['control'];decisions={}
    for name in NAMES[1:]:
        s=scores[name];a=s['overall'];b=c['overall'];better=sum(x['brier']<y['brier'] for x,y in zip(s['by_season'],c['by_season']))
        ok=a['brier']<b['brier'] and a['log_loss']<b['log_loss'] and better>=5
        if name=='calibration':ok=ok and a['accuracy']==b['accuracy']
        else:ok=ok and a['accuracy']>=b['accuracy']+.005 and s['recent_2023_2025']['accuracy']>=c['recent_2023_2025']['accuracy']
        decisions[name]={'research_eligible':bool(ok),'brier_improved_seasons':better,'production_promoted':False}
    return decisions
def run(data_dir,out_dir):
    d=guarded_data(data_dir);x,px,cf,pf=matrices(d);raw_oof={};rows=[];boundaries=[]
    for season in range(2016,2026):
        te=d.index[d.season.eq(season)];tr=training_index(d,season)
        control=fit_parts(d,x,px,cf,pf,tr);p=ensemble(control,x,px,cf,pf,te);y=d.loc[te,'home_win'].to_numpy()
        raw_oof[season]=(p,y)
        if season<2018:continue
        calibration_years=sorted(s for s in raw_oof if s<season)[-3:]
        cp=np.concatenate([raw_oof[s][0] for s in calibration_years]);cy=np.concatenate([raw_oof[s][1] for s in calibration_years]);slope=calibrate(cp,cy)
        recent=training_index(d,season,True);winner=fit_parts(d,x,px,cf,pf,recent)
        probabilities={'control':p,'calibration':apply_calibration(p,slope),'recent3_blend50':ensemble(winner,x,px,cf,pf,te,.5)}
        if np.any((probabilities['calibration']>=.5)!=(p>=.5)):raise ValueError('Calibration changed selected winners')
        boundaries.append({'test_season':season,'control_training_max':int(d.loc[tr,'season'].max()),'recent_training_seasons':sorted(map(int,d.loc[recent,'season'].unique())),'calibration_oof_seasons':calibration_years,'calibration_slope':slope})
        for name,prob in probabilities.items():
            for i,v in zip(te,prob):rows.append({'game_id':int(d.at[i,'game_id']),'season':season,'candidate':name,'home_win':int(d.at[i,'home_win']),'probability':float(v),'training_max_season':int(d.loc[tr,'season'].max())})
        print('CFB fold',season,'done',flush=True)
    pred=pd.DataFrame(rows);scores=summarize(pred);decisions=eligibility(scores)
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True);pred.to_csv(out/'development_predictions.csv',index=False)
    diagnostics={'rows':len(d),'duplicate_game_ids':int(d.game_id.duplicated().sum()),'context_features':cf,'prior_features':pf,'missingness':{f:{'missing_fraction':float(x[f].isna().mean()),'nonfinite_nonmissing':int((~np.isfinite(pd.to_numeric(x[f],errors='coerce'))&x[f].notna()).sum())} for f in cf}}
    result={'status':'reused_historical_development_only','live_2026_used_for_training_or_selection':False,'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),'scores':scores,'decisions':decisions,'fold_boundaries':boundaries,'input_diagnostics':diagnostics}
    (out/'development_results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'scores':{k:v['overall'] for k,v in scores.items()},'decisions':decisions},indent=2),flush=True)
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',default='runtime/challengers_20261028/cfb/matchup_line');ap.add_argument('--out-dir',default='runtime/challengers_20261028/results/cfb');a=ap.parse_args();run(a.data_dir,a.out_dir)
if __name__=='__main__':main()
