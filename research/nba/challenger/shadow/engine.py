"""Pure availability features and append-only paired forecast validation."""
from collections import defaultdict,deque
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.special import expit,logit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from injuries import player_key,report_files,cutoff_for
from study import LOADS,STATUS


def report_candidates(cutoff):
    # Both names represent the same intended historical publication instant.
    result=[]
    for old in report_files(cutoff):
        result.extend([old,old[:-6]+'_30'+old[-6:]])
    return result


def impact_features(home,away,player_rows,day):
    names=defaultdict(set);past=defaultdict(lambda:deque(maxlen=20))
    for p in sorted(player_rows,key=lambda p:(p['date'],p['game_id'],p['athlete_id'])):
        if p['date']>=day:continue
        names[player_key(p['name'])].add(p['athlete_id'])
        past[p['athlete_id']].append([p['minutes'],p['points']])
    sides=[];listed=matched=0
    for context in [home,away]:
        values={c:0. for c in LOADS}
        for p in context.get('players',[]):
            if p['status'] not in STATUS:continue
            listed+=1;ids=names.get(p['key'],set())
            if len(ids)!=1:continue
            records=past[next(iter(ids))]
            if not records:continue
            matched+=1;mean=np.mean(records,axis=0)
            values['minutes_'+p['status']+'_diff']+=float(mean[0])
            if p['status']=='Out':values['out_points_diff']+=float(mean[1])
        sides.append(values)
    return {c:sides[0][c]-sides[1][c] for c in LOADS},listed,matched


def adjusted_probability(control,features,frozen):
    fit=frozen['fit'];columns=fit['features']
    x=np.array([features[c] for c in columns],float)
    z=(x-np.array(fit['mean']))/np.array(fit['scale'])
    b=np.array(fit['coefficients'])
    if not np.isfinite(z).all() or not np.isfinite(b).all():raise ValueError('Nonfinite residual inputs')
    return float(expit(logit(np.clip(control,1e-8,1-1e-8))+b[0]+z@b[1:]))


def validate(predictions,results,shadow_sha,v1_sha):
    ids=set()
    for p in predictions:
        if p['game_id'] in ids:raise ValueError('Duplicate shadow forecast')
        ids.add(p['game_id'])
        if p['season']!=2027 or p['season_type']!=2:raise ValueError('Nonregular-season shadow forecast')
        start=pd.Timestamp(p['start_time_utc']);created=pd.Timestamp(p['created_at_utc']);cutoff=cutoff_for(start)
        if not cutoff<=created<start:raise ValueError('Capture outside fixed pregame interval')
        if pd.Timestamp(p['availability_cutoff_utc'])!=cutoff:raise ValueError('Wrong availability cutoff')
        if p['history_cutoff']>=start.tz_convert('America/New_York').date().isoformat():raise ValueError('Current-date state leaked')
        if p['shadow_sha256']!=shadow_sha or p['v1_bundle_sha256']!=v1_sha:raise ValueError('Frozen hash mismatch')
        for name in ['control_probability','candidate_probability']:
            if not np.isfinite(p[name]) or not 0<=p[name]<=1:raise ValueError('Invalid probability')
        if p['fallback'] and p['candidate_probability']!=p['control_probability']:raise ValueError('Fallback changed V1')
        if not p['fallback']:
            report=p['injury_report']
            if not report['both_known'] or report['parse_issues']:raise ValueError('Unknown report adjusted')
            for key in ['published_at','created_at']:
                if pd.Timestamp(report[key])>cutoff or pd.Timestamp(report[key])>created:raise ValueError('Postcutoff report')
            if p['listed_players'] and p['matched_players']/p['listed_players']<.8:raise ValueError('Low identity coverage adjusted')
    settled=set();by_id={p['game_id']:p for p in predictions}
    for r in results:
        gid=r['game_id']
        if gid not in ids or gid in settled:raise ValueError('Invalid or duplicate grade')
        settled.add(gid);p=by_id[gid]
        if r['source_state']!='post_completed' or pd.Timestamp(r['settled_at_utc'])<=pd.Timestamp(r['actual_start_time_utc']):raise ValueError('Unconfirmed final')
        if pd.Timestamp(p['created_at_utc'])>=pd.Timestamp(r['actual_start_time_utc']):raise ValueError('Changed start invalidated forecast')
        if not all(np.isfinite(r[k]) and r[k]>=0 for k in ['home_score','away_score']):raise ValueError('Invalid final score')
        if r['home_score']==r['away_score'] or r['actual_home_win']!=int(r['home_score']>r['away_score']):raise ValueError('Invalid winner')
