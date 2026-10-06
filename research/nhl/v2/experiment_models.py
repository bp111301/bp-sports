"""Bounded V2 model-structure comparison, reusing development only.

V1 and its failed evaluation remain immutable. 2025-26 labels never enter this
script. Results are exploratory because the development seasons were reused.
"""
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline

HERE=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(HERE))
from experiment_goalies import base,adv,model,met,DEV

CANDIDATES=['v1_reference','recent3_logistic','decay2_logistic','small_boosted_tree','linear_tree_blend']

def recent_weights(seasons):
    years=pd.Series(seasons).astype(str).str[:4].astype(int).to_numpy()
    weights=.5**((years.max()-years)/2.)
    return weights/weights.mean()

def training_indices(d,season,name):
    earlier=sorted(d.loc[d.season<season,'season'].unique())
    if name=='recent3_logistic':earlier=earlier[-3:]
    tr=d.index[d.season.isin(earlier)]
    if len(tr)==0:raise ValueError('No prior training seasons')
    return tr

def learner(name,features):
    linear=model(features)
    if name in ['v1_reference','recent3_logistic','decay2_logistic']:
        return linear
    tree=Pipeline([('prep',linear.named_steps['prep']),('model',HistGradientBoostingClassifier(max_iter=150,learning_rate=.05,max_leaf_nodes=7,max_depth=3,min_samples_leaf=100,l2_regularization=10.,early_stopping=False,random_state=17))])
    return tree

def fit_predict(d,x,features,season,name):
    tr=training_indices(d,season,name);te=d.index[d.season==season]
    if len(te)==0:raise ValueError('Missing test season')
    if not (d.loc[tr,'season']<season).all():raise ValueError('Future training labels')
    m=learner(name,features)
    kwargs={'model__sample_weight':recent_weights(d.loc[tr,'season'])} if name=='decay2_logistic' else {}
    m.fit(x.loc[tr,features],d.loc[tr,'home_win'],**kwargs)
    p=m.predict_proba(x.loc[te,features])[:,1]
    if name=='linear_tree_blend':
        linear=model(features);linear.fit(x.loc[tr,features],d.loc[tr,'home_win'])
        p=.75*linear.predict_proba(x.loc[te,features])[:,1]+.25*p
    return p,{'test_season':season,'training_seasons':sorted(d.loc[tr,'season'].unique().tolist()),'training_games':len(tr),'test_games':len(te)}

def feature_audit(d,x,t,features):
    rows=[]
    for s in sorted(d.season.unique()):
        z=x.loc[d.season==s];stats=t[t.season.astype(str)==s]
        rows.append({'season':s,'games':int((d.season==s).sum()),'team_stat_rows':len(stats),'duplicate_team_game_keys':int(stats.duplicated(['gameId','teamId']).sum()),'features':{c:{'missing_rate':float(z[c].isna().mean()),'mean':float(z[c].mean()) if z[c].notna().any() else None,'std':float(z[c].std()) if z[c].notna().sum()>1 else None,'min':float(z[c].min()) if z[c].notna().any() else None,'max':float(z[c].max()) if z[c].notna().any() else None} for c in features}})
    keys=pd.concat([d[['game_id','home_id']].rename(columns={'home_id':'teamId'}),d[['game_id','away_id']].rename(columns={'away_id':'teamId'})]).rename(columns={'game_id':'gameId'})
    q=keys.merge(t[['gameId','teamId']],on=['gameId','teamId'],how='left',indicator=True,validate='one_to_one')
    return {'team_game_join_coverage':float(q._merge.eq('both').mean()),'by_season':rows,'label_source':'NHL schedule; previously audited excluded-season winners agree with NHL stats summary','excluded_season_not_loaded':True}

def main():
    d=base.load('runtime/nhl/v2/games')
    if (d.season>DEV[-1]).any():raise ValueError('V2 tournament cannot load 2025-26 or later')
    bx=base.build_features(d);t=adv.load_team_stats('runtime/nhl/v2/team_stats');x,af=adv.attach(d,bx,t,20);features=base.FEATURES+af
    audit=feature_audit(d,x,t,features)
    if audit['team_game_join_coverage']!=1.:raise ValueError('Incomplete team-stat joins')
    ranking=[];parts=[];folds={}
    for name in CANDIDATES:
        seasons=[];all_y=[];all_p=[];folds[name]=[]
        for s in DEV:
            p,fold=fit_predict(d,x,features,s,name);folds[name].append(fold)
            q=d[d.season==s][['game_id','season','game_date','home_team','away_team','home_win']].copy();q['candidate']=name;q['home_win_prob']=p;parts.append(q)
            y=q.home_win.to_numpy();all_y.extend(y);all_p.extend(p);seasons.append({'season':s,**met(y,p)})
        ranking.append({'candidate':name,**met(np.asarray(all_y),np.asarray(all_p)),'by_season':seasons})
    reference=ranking[0]
    for r in ranking:
        r['seasons_with_brier_improvement']=sum(a['brier']<b['brier'] for a,b in zip(r['by_season'],reference['by_season']))
        r['eligible_as_research_candidate']=r['candidate']!='v1_reference' and r['brier']<reference['brier'] and r['log_loss']<reference['log_loss'] and r['accuracy']>=reference['accuracy'] and r['seasons_with_brier_improvement']>=3
    ranking.sort(key=lambda r:(r['brier'],r['log_loss'],-r['accuracy']))
    eligible=[r for r in ranking if r['eligible_as_research_candidate']]
    selected=eligible[0]['candidate'] if eligible else 'v1_reference'
    result={'selection_seasons':DEV,'excluded_from_selection':['20252026','20262027'],'ranking':ranking,'selected_research_candidate':selected,'features':features,'fold_audit':folds,'status':'research only; not an independently validated replacement','validation_boundary':'2025-26 already viewed and cannot be reused as fresh confirmation. Later predictions must be timestamped before game starts.','decision_rule':'Improve aggregate Brier/log loss, preserve accuracy and improve Brier in >=3/4 development seasons.'}
    out=Path('research/nhl/v2/results');out.mkdir(parents=True,exist_ok=True)
    (out/'model_tournament.json').write_text(json.dumps(result,indent=2)+'\n');(out/'feature_audit.json').write_text(json.dumps(audit,indent=2)+'\n');pd.concat(parts,ignore_index=True).to_csv(out/'model_oof_predictions.csv',index=False)
    lines=['# NHL V2 Model-Structure Tournament','','Fixed five-candidate development comparison; 2021–22 through 2024–25 only. V1 frozen artifacts and excluded-season results are unchanged.','','| Candidate | Accuracy | Brier | Log loss | Seasons improved | Research eligible |','|---|---:|---:|---:|---:|---|']
    for r in ranking:lines.append(f"| {r['candidate']} | {r['accuracy']:.2%} | {r['brier']:.6f} | {r['log_loss']:.6f} | {r['seasons_with_brier_improvement']} | {r['eligible_as_research_candidate']} |")
    lines+=['',f'Selected research candidate: **{selected}**.',f'Team-game join coverage: {audit["team_game_join_coverage"]:.2%}.','',result['validation_boundary'],'No prospective performance is claimed. Development seasons have already been reused for earlier experiments.'];(out/'MODEL_TOURNAMENT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
