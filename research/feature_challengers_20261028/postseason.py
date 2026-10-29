"""One separately registered CFB input-recipe correction. No production writes."""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('postseason_features',HERE/'experiment.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


def prior_input(d):
    kind=d.season_type.astype(str).str.lower()
    if not kind.isin(['regular','postseason']).all():raise ValueError('Unrecognized CFB season type')
    out=d.copy(deep=True)
    out.loc[kind.eq('postseason'),'week']=8
    return out


def run():
    d=e.cfb.guarded_data(e.ROOT/'runtime/challengers_20261028/cfb/matchup_line')
    x,oldpx,cf,pf=e.cfb.matrices(d)
    px=e.cfb.pri.matrix(prior_input(d),7.)
    old=pd.read_csv(e.ROOT/'research/challengers_20261028/results/cfb/development_predictions.csv.gz')
    old=old[old.candidate.eq('control')].set_index('game_id')
    rows=[]
    for season in range(2018,2026):
        tr=d.index[d.season.lt(season)];te=d.index[d.season.eq(season)]
        models=e.cfb.fit_parts(d,x,px,cf,pf,tr)
        q=e.cfb.ensemble(models,x,px,cf,pf,te)
        for i,v in zip(te,q):
            gid=int(d.at[i,'game_id']);original=old.loc[gid]
            if int(original.home_win)!=int(d.at[i,'home_win']):raise ValueError('Historical outcome join mismatch')
            for name,p in [('control',float(original.probability)),('postseason_aware_prior',float(v))]:
                rows.append({'game_id':gid,'season':str(season),'candidate':name,'block':f'{season}:{d.at[i,"week"]}',
                    'home_win':int(d.at[i,'home_win']),'probability':p,'season_type':d.at[i,'season_type'],
                    'training_max_season':str(d.loc[tr,'season'].max())})
    pred=pd.DataFrame(rows);scores,decisions=e.score_predictions(pred,'cfb')
    sub={}
    for kind in ['regular','postseason']:
        sub[kind]={name:e.audit.summarize(g.probability,g.home_win) for name,g in pred[pred.season_type.eq(kind)].groupby('candidate')}
    changes=pred.pivot(index='game_id',columns='candidate',values='probability')
    affected=d.loc[d.season_type.eq('postseason'),['game_id','season','week','season_type','start_date']].copy()
    result={'status':'reused_historical_development_only','live_labels_used':False,
        'protocol_sha256':hashlib.sha256((HERE/'POSTSEASON_PROTOCOL.md').read_bytes()).hexdigest(),
        'scores':scores,'decisions':decisions,'subgroups':sub,
        'winner_changes':int(((changes.control>=.5)!=(changes.postseason_aware_prior>=.5)).sum()),
        'source_postseason_rows':len(affected),'source_postseason_week1_rows':int(affected.week.eq(1).sum()),
        'original_recipe_or_source_modified':False}
    out=e.ROOT/'runtime/feature_challengers_20261028/postseason';out.mkdir(parents=True,exist_ok=True)
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    pred.to_csv(out/'predictions.csv',index=False);affected.to_csv(out/'input_anomalies.csv',index=False)
    print(json.dumps({'overall':{k:v['overall']['overall'] for k,v in scores.items()},'decisions':decisions,'postseason':{k:v['overall'] for k,v in sub['postseason'].items()}},indent=2))
    return result


if __name__=='__main__':run()
