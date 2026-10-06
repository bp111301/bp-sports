"""Fixed regulation-strength experiments; no excluded-season model selection.

Extra-time game results update team strength as a regulation tie. Future game
period types never enter prediction features. Fit only prior-season labels.
"""
import json,sys
from collections import defaultdict,deque
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import skellam
from sklearn.linear_model import LogisticRegression,PoissonRegressor
from sklearn.pipeline import Pipeline
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from experiment_goalies import base,adv,model,met,DEV
from experiment_models import fit_predict

CANDIDATES=['v1_reference','regulation_form_logistic','regulation_threeway','regulation_poisson','linear_regulation_blend']

def regulation_labels(d):
    extra=d.last_period_type.isin(['OT','SO'])
    win=d.home_score>d.away_score
    hg=d.home_score-extra.astype(int)*win.astype(int)
    ag=d.away_score-extra.astype(int)*(~win).astype(int)
    if (extra & (hg!=ag)).any():raise ValueError('Extra-time final score cannot reconstruct regulation tie')
    target=np.where(extra,1,np.where(win,2,0))
    return pd.DataFrame({'reg_home_goals':hg,'reg_away_goals':ag,'reg_outcome':target},index=d.index)

def strength_features(d):
    labels=regulation_labels(d);elo=defaultdict(lambda:1500.);hist=defaultdict(lambda:deque(maxlen=10));last={};gp=defaultdict(int);previous=None;rows=[]
    def avg(team,pos):return float(np.mean([x[pos] for x in hist[team]])) if hist[team] else np.nan
    for (season,date),day in d.sort_values(['season','game_date','game_id']).groupby(['season','game_date'],sort=False):
        if previous is not None and season!=previous:
            for t in list(elo):elo[t]=1500+.75*(elo[t]-1500)
            hist.clear();last.clear();gp.clear()
        previous=season;updates=[]
        for idx,r in day.iterrows():
            h,a=str(r.home_team),str(r.away_team);hr=(date-last[h]).days if h in last else np.nan;ar=(date-last[a]).days if a in last else np.nan
            rows.append({'index':idx,'elo_diff':elo[h]-elo[a],'home_field':1.,'win10_diff':avg(h,0)-avg(a,0),'gd10_diff':avg(h,1)-avg(a,1),'gf10_diff':avg(h,2)-avg(a,2),'ga10_diff':avg(h,3)-avg(a,3),'rest_diff':hr-ar if pd.notna(hr) and pd.notna(ar) else np.nan,'home_b2b':float(hr==1) if pd.notna(hr) else 0.,'away_b2b':float(ar==1) if pd.notna(ar) else 0.,'games_played_diff':gp[h]-gp[a]})
            updates.append((idx,r,elo[h],elo[a]))
        for idx,r,eh,ea in updates:
            h,a=str(r.home_team),str(r.away_team);q=labels.loc[idx];y=q.reg_outcome/2.;hg=float(q.reg_home_goals);ag=float(q.reg_away_goals);margin=hg-ag
            expected=1/(1+10**(-(eh+35-ea)/400));delta=20*(y-expected);elo[h]+=delta;elo[a]-=delta
            hist[h].append((y,margin,hg,ag));hist[a].append((1-y,-margin,ag,hg));last[h]=date;last[a]=date;gp[h]+=1;gp[a]+=1
    return pd.DataFrame(rows).set_index('index').reindex(d.index)

def predict(d,x,features,labels,season,name,reference_x):
    tr=d.index[d.season<season];te=d.index[d.season==season]
    if name=='v1_reference':return fit_predict(d,reference_x,features,season,'v1_reference')[0]
    if name=='regulation_form_logistic':
        m=model(features);m.fit(x.loc[tr,features],d.loc[tr,'home_win']);return m.predict_proba(x.loc[te,features])[:,1]
    if name in ['regulation_threeway','linear_regulation_blend']:
        m=model(features);m.fit(x.loc[tr,features],labels.loc[tr,'reg_outcome']);probs=m.predict_proba(x.loc[te,features]);classes=m.named_steps['model'].classes_;p=probs[:,list(classes).index(2)]+.5*probs[:,list(classes).index(1)]
        if name=='linear_regulation_blend':p=.5*p+.5*fit_predict(d,reference_x,features,season,'v1_reference')[0]
        return p
    if name=='regulation_poisson':
        rates=[]
        for target in ['reg_home_goals','reg_away_goals']:
            prep=model(features).named_steps['prep'];m=Pipeline([('prep',prep),('model',PoissonRegressor(alpha=1.,max_iter=1000))]);m.fit(x.loc[tr,features],labels.loc[tr,target]);rates.append(m.predict(x.loc[te,features]))
        return np.clip(skellam.sf(0,rates[0],rates[1])+.5*skellam.pmf(0,rates[0],rates[1]),1e-6,1-1e-6)
    raise ValueError(name)

def main():
    d=base.load('runtime/nhl/v2/games')
    if (d.season>DEV[-1]).any():raise ValueError('Excluded season loaded')
    t=adv.load_team_stats('runtime/nhl/v2/team_stats');ref,af=adv.attach(d,base.build_features(d),t,20);x,_=adv.attach(d,strength_features(d),t,20);features=base.FEATURES+af;labels=regulation_labels(d)
    results=[];parts=[]
    for name in CANDIDATES:
        ys=[];ps=[];seasons=[]
        for s in DEV:
            p=predict(d,x,features,labels,s,name,ref);q=d[d.season==s][['game_id','season','game_date','home_team','away_team','home_win']].copy();q['candidate']=name;q['home_win_prob']=p;parts.append(q);ys.extend(q.home_win);ps.extend(p);seasons.append({'season':s,**met(q.home_win.to_numpy(),p)})
        results.append({'candidate':name,**met(np.asarray(ys),np.asarray(ps)),'by_season':seasons})
    baseline=results[0]
    for r in results:
        r['seasons_with_brier_improvement']=sum(a['brier']<b['brier'] for a,b in zip(r['by_season'],baseline['by_season']))
        r['eligible_as_research_candidate']=r['candidate']!='v1_reference' and r['brier']<baseline['brier'] and r['log_loss']<baseline['log_loss'] and r['accuracy']>=baseline['accuracy'] and r['seasons_with_brier_improvement']>=3
    results.sort(key=lambda r:(r['brier'],r['log_loss'],-r['accuracy']));eligible=[r for r in results if r['eligible_as_research_candidate']]
    payload={'selection_seasons':DEV,'excluded_from_selection':['20252026','20262027'],'ranking':results,'selected_research_candidate':eligible[0]['candidate'] if eligible else 'v1_reference','extra_time_probability':.5,'status':'exploratory development; prospective validation required','limitations':'Regulation score reconstructed by removing one winning overtime/shootout goal. Poisson assumes independent goal counts; extra-time win chance fixed at .5, not known outcome.'}
    out=Path('research/nhl/v2/results');(out/'regulation_tournament.json').write_text(json.dumps(payload,indent=2)+'\n');pd.concat(parts,ignore_index=True).to_csv(out/'regulation_oof_predictions.csv',index=False)
    lines=['# NHL Regulation-Strength Tournament','','All model fitting/selection uses 2021–22 through 2024–25 walk-forward only.','','| Candidate | Accuracy | Brier | Log loss | Seasons improved | Research eligible |','|---|---:|---:|---:|---:|---|']
    for r in results:lines.append(f"| {r['candidate']} | {r['accuracy']:.2%} | {r['brier']:.6f} | {r['log_loss']:.6f} | {r['seasons_with_brier_improvement']} | {r['eligible_as_research_candidate']} |")
    lines+=['',f'Selected research candidate: {payload["selected_research_candidate"]}.',payload['limitations'],'No independent confirmation or live release is claimed.'];(out/'REGULATION_TOURNAMENT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
