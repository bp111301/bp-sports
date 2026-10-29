"""Fixed structural research tournament; no production outputs or live labels."""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm, skellam
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
# Append, never override the core environment's pinned numpy/pandas/scipy.
sys.path.append(str(ROOT/'runtime/catboost_dependencies'))
from catboost import CatBoostClassifier, CatBoostRegressor
import catboost

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

e=module('struct_features',HERE.parent/'feature_challengers_20261028/experiment.py')
post=module('struct_postseason',HERE.parent/'feature_challengers_20261028/postseason.py')


def cfb_features(d):
    corrected=post.prior_input(d)
    x,px,cf,pf,extra=e.expanded_cfb(corrected)
    out=x.copy()
    for c in pf:
        if c.startswith('blend_'):out[c]=px[c]
    out=out.join(extra)
    bases=sorted(set(e.cfb.base.PAIR_BASES+e.cfb.pri.BLEND_BASES+e.EXTRA_BASES))
    for side in ['home','away']:
        for f in bases:
            for prefix in ['', 'prev_']:
                name=f'{prefix}{side}_{f}'
                if name not in d:raise ValueError('Missing registered CFB profile '+name)
                out[name]=pd.to_numeric(d[name],errors='coerce')
        for f in ['pregame_elo','opp_elo_roll_avg','talent','team_talent_weighted','ovr_rtprod','hc_tenure']:
            out[f'{side}_{f}']=pd.to_numeric(d[f'{side}_{f}'],errors='coerce')
    out['source_week']=pd.to_numeric(d.week,errors='coerce')
    out['effective_week']=pd.to_numeric(corrected.week,errors='coerce')
    dates=pd.to_datetime(d.start_date,utc=True)
    origin=pd.to_datetime(d.season.astype(str)+'-07-01',utc=True)
    out['days_since_july1']=(dates.dt.normalize()-origin).dt.days
    cats=['home_team_id','away_team_id','home_conference','away_conference','season_type']
    for c in cats:out[c]=d[c].fillna('__missing__').astype(str)
    return out.replace([np.inf,-np.inf],np.nan),cats,[]


def nhl_features(d,t):
    dates=pd.to_datetime(t.gameDate,utc=True).dt.normalize()
    if pd.DataFrame({'season':t.season,'team':t.teamId,'date':dates}).duplicated().any():
        raise ValueError('Duplicate NHL season/team/date')
    x,_=e.nhl.adv.attach(d,e.nhl.base.build_features(d),t,20)
    t=t.sort_values(['season','teamId','gameDate','gameId']).copy()
    raw=e.nhl.adv.RAW+['goals_for','goals_against']
    for c in raw:
        t[f'profile_{c}']=t.groupby(['season','teamId'],sort=False)[c].transform(lambda a:a.shift(1).rolling(20,min_periods=3).mean())
    z=d[['game_id','home_id','away_id']].copy()
    for side in ['home','away']:
        table=t[['gameId','teamId']+[f'profile_{c}' for c in raw]].rename(columns={'gameId':'game_id','teamId':f'{side}_id',**{f'profile_{c}':f'{side}_{c}20' for c in raw}})
        z=z.merge(table,on=['game_id',f'{side}_id'],how='left',validate='one_to_one')
    for c in z:
        if c not in ['game_id','home_id','away_id']:x[c]=pd.to_numeric(z[c],errors='coerce').to_numpy()
    pooled,boundaries=e.pooled_rates(d,t);x=x.join(pooled)
    cats=['home_id','away_id']
    for c in cats:x[c]=d[c].astype(str)
    return x.replace([np.inf,-np.inf],np.nan),cats,boundaries


def params(depth,penalty,regression=False):
    return dict(iterations=400,learning_rate=.03,depth=depth,l2_leaf_reg=penalty,
        loss_function='RMSE' if regression else 'Logloss',boosting_type='Ordered',has_time=True,
        bootstrap_type='No',random_strength=0,one_hot_max_size=2,max_ctr_complexity=1,
        use_best_model=False,thread_count=1,random_seed=20261028,allow_writing_files=False,verbose=False)


def prepare(x,tr,te,cats):
    numeric=[c for c in x if c not in cats]
    imp=SimpleImputer(strategy='median',keep_empty_features=True)
    train=pd.DataFrame(imp.fit_transform(x.loc[tr,numeric]),index=tr,columns=numeric)
    test=pd.DataFrame(imp.transform(x.loc[te,numeric]),index=te,columns=numeric)
    for c in cats:
        train[c]=x.loc[tr,c].fillna('__missing__').astype(str)
        test[c]=x.loc[te,c].fillna('__missing__').astype(str)
    return train,test,imp,numeric


def fold(d,season,sport):
    date='start_date' if sport=='cfb' else 'game_date'
    tr=d.loc[d.season.lt(season)].sort_values([date,'game_id']).index
    te=d.index[d.season.eq(season)]
    if not len(tr) or not len(te) or not d.loc[tr,'season'].lt(season).all():raise ValueError('Invalid season fold')
    if pd.to_datetime(d.loc[tr,date],utc=True).max()>=pd.to_datetime(d.loc[te,date],utc=True).min():raise ValueError('Training time overlaps target season')
    return tr,te


def margin_sigma(history,season):
    years=sorted(y for y in history if y<season)[-3:]
    residual=np.concatenate([history[y] for y in years]) if years else np.array([])
    if len(residual)<200:raise ValueError('Insufficient prior OOF margin residuals')
    return max(5.,float(np.sqrt(np.mean(residual**2)))),years,len(residual)


def poisson_probability(home,away):
    home=np.asarray(home,float);away=np.asarray(away,float)
    if not np.isfinite(home).all() or not np.isfinite(away).all() or (home<=0).any() or (away<=0).any():raise ValueError('Invalid predicted scoring rates')
    p=skellam.sf(0,home,away)+.5*skellam.pmf(0,home,away)
    if not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid scoring probability')
    return p


def archive_control(d,sport):
    path=ROOT/('research/strength_challengers_20261028/results/cfb/development_predictions.csv.gz' if sport=='cfb' else 'research/feature_challengers_20261028/results/nhl/predictions.csv.gz')
    a=pd.read_csv(path,dtype={'season':str});a=a[a.candidate.eq('control')].set_index('game_id')
    if a.index.duplicated().any():raise ValueError('Duplicate archive control')
    expected=d[d.season.isin(list(range(2018,2026)) if sport=='cfb' else e.nhl.DEV)].set_index('game_id')
    if set(a.index)!=set(expected.index):raise ValueError('Control cohort mismatch')
    a=a.loc[expected.index]
    if not np.array_equal(a.home_win,expected.home_win) or not np.array_equal(a.season.astype(str),expected.season.astype(str)):raise ValueError('Control labels or seasons mismatch')
    return a


def run(sport):
    if catboost.__version__!='1.2.8':raise ValueError('CatBoost version differs from protocol')
    if sport=='cfb':
        d=e.cfb.guarded_data(ROOT/'runtime/challengers_20261028/cfb/matchup_line');x,cats,boundaries=cfb_features(d);seasons=list(range(2016,2026))
        target=np.clip(d.home_points-d.away_points,-42,42);raw_margin=d.home_points-d.away_points
    else:
        d,t=e.nhl.selection_data(ROOT/'runtime/challengers_20261028/nhl/team_game_stats');x,cats,boundaries=nhl_features(d,t);seasons=e.nhl.DEV
    control=archive_control(d,sport);rows=[];folds=[];margin_history={}
    out=ROOT/'runtime/structural_challengers_20261028'/sport;out.mkdir(parents=True,exist_ok=True)
    for season in seasons:
        tr,te=fold(d,season,sport);train,test,imp,numeric=prepare(x,tr,te,cats)
        probs={};details={'test_season':str(season),'training_max_season':str(d.loc[tr,'season'].max()),'train_only_imputation':True,'all_empty_training_columns':[c for c in numeric if x.loc[tr,c].isna().all()]}
        if sport=='cfb':
            reg=CatBoostRegressor(**params(4,10,True));reg.fit(train,target.loc[tr],cat_features=cats)
            mu=reg.predict(test)
            if season>=2018:
                sigma,years,n=margin_sigma(margin_history,season);probs['margin_normal']=norm.cdf(mu/sigma);details.update(margin_sigma=sigma,sigma_prior_oof_seasons=years,sigma_prior_rows=n)
            margin_history[season]=raw_margin.loc[te].to_numpy()-mu
            if season<2018:
                print(sport,season,'margin warmup complete',flush=True);continue
        for depth in [3,5]:
            for penalty in [5,20]:
                m=CatBoostClassifier(**params(depth,penalty));m.fit(train,d.loc[tr,'home_win'],cat_features=cats)
                probs[f'cat_d{depth}_l2_{penalty}']=m.predict_proba(test)[:,1]
        if sport=='nhl':
            for alpha in [.01,.1]:
                ms=[]
                for column in ['home_score','away_score']:
                    p=Pipeline([('scale',StandardScaler()),('model',PoissonRegressor(alpha=alpha,max_iter=1000,tol=1e-6))]);p.fit(train[numeric],d.loc[tr,column]);ms.append(p.predict(test[numeric]))
                probs[f'poisson_alpha_{alpha}']=poisson_probability(*ms)
        p=control.loc[d.loc[te,'game_id'],'probability'].to_numpy()
        for name,q in list(probs.items()):probs[name+'_halfblend']=.5*p+.5*q
        probs['control']=p
        for name,prob in probs.items():
            if not np.isfinite(prob).all() or ((prob<0)|(prob>1)).any():raise ValueError('Invalid candidate probabilities')
            for i,v in zip(te,prob):rows.append({'game_id':int(d.at[i,'game_id']),'season':str(season),'candidate':name,'home_win':int(d.at[i,'home_win']),'probability':float(v),'training_max_season':str(d.loc[tr,'season'].max()),'block':f'{season}:{d.at[i,"week"]}' if sport=='cfb' else str(d.at[i,'game_date'])})
        folds.append(details)
        # Durable local progress, complete cohort is required before scoring/qualification.
        pd.DataFrame(rows).to_csv(out/'partial_predictions.csv',index=False)
        print(sport,season,'complete',flush=True)
    pred=pd.DataFrame(rows);scores,decisions=e.score_predictions(pred,sport)
    eligible=[name for name in decisions if decisions[name]['research_eligible']]
    winner=min(eligible,key=lambda n:(scores[n]['overall']['overall']['brier'],scores[n]['overall']['overall']['log_loss'],-scores[n]['overall']['overall']['accuracy'],n)) if eligible else None
    result={'sport':sport,'status':'reused_historical_development_only','live_labels_used':False,'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),'scores':scores,'decisions':decisions,'selected_research_candidate':winner,'features':list(x),'categorical_features':cats,'fold_boundaries':folds,'production_promoted':False,'multiple_testing_warning':'Repeatedly reused development history; intervals descriptive and not selection-adjusted. No live improvement established.'}
    pred.to_csv(out/'predictions.csv',index=False)
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    if boundaries:(out/'temporal_boundaries.json').write_text(json.dumps(boundaries,indent=2)+'\n')
    print(json.dumps({'sport':sport,'selected':winner,'scores':{k:v['overall']['overall'] for k,v in scores.items()},'decisions':decisions},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sport',required=True,choices=['cfb','nhl']);a=p.parse_args();run(a.sport)
