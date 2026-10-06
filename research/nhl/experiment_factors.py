"""Bounded NHL opponent, schedule/travel and exploratory shot-quality ablation.

No 2025-26 candidate selection. Predict all games on a date before updating state.
Travel is arena-to-arena great-circle distance, not known team itineraries.
MoneyPuck retrospective xG is exploratory: model training vintage is unverified.
"""
from collections import defaultdict, deque
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from experiment_goalies import base, adv, DEV, model, met

# Approximate arena coordinates. Club identities come from NHL numeric IDs.
ARENAS = {
 1:(40.733,-74.171),2:(40.723,-73.590),3:(40.751,-73.994),4:(39.901,-75.172),
 5:(40.440,-79.989),6:(42.366,-71.062),7:(42.875,-78.876),8:(45.496,-73.569),
 9:(45.296,-75.927),10:(43.643,-79.379),12:(35.803,-78.722),13:(26.158,-80.325),
 14:(27.943,-82.452),15:(38.898,-77.021),16:(41.880,-87.674),17:(42.341,-83.055),
 18:(36.159,-86.778),19:(38.627,-90.203),20:(51.037,-114.052),21:(39.749,-105.008),
 22:(53.547,-113.497),23:(49.278,-123.109),24:(33.808,-117.877),25:(32.790,-96.810),
 26:(34.043,-118.267),28:(37.333,-121.902),29:(39.969,-83.006),30:(44.944,-93.101),
 52:(49.892,-97.144),54:(36.102,-115.178),55:(47.622,-122.354),59:(40.768,-111.901)}

def venue(team_id, season):
    if int(team_id)==53: # Coyotes moved from Glendale to Tempe for 2022-23.
        return (33.426,-111.928) if str(season)>='20222023' else (33.532,-112.261)
    return ARENAS.get(int(team_id))

def distance(a,b):
    if a is None or b is None:
        return np.nan
    lat1,lon1,lat2,lon2=map(math.radians,[*a,*b])
    v=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371*2*math.asin(math.sqrt(min(1,v)))

OPP=['opp_elo20_diff','adjusted_gf20_diff','adjusted_ga20_diff']
SCHEDULE=['travel_km_diff','games7_diff','games3_diff','away_streak_diff']

def contextual_features(d):
    elo=defaultdict(lambda:1500.)
    history=defaultdict(lambda:deque(maxlen=20))
    adjusted=defaultdict(lambda:deque(maxlen=20))
    dates=defaultdict(lambda:deque(maxlen=20))
    last_venue={}; away_streak=defaultdict(int); rows=[]; previous=None
    def mean(team,pos,store):
        values=[v[pos] for v in store[team] if pd.notna(v[pos])]
        return np.mean(values) if values else np.nan
    for (season,date),day in d.sort_values(['season','game_date','game_id']).groupby(['season','game_date'],sort=False):
        if previous is not None and season!=previous:
            for team in list(elo): elo[team]=1500+.75*(elo[team]-1500)
            history.clear();adjusted.clear();dates.clear();last_venue.clear();away_streak.clear()
        previous=season; updates=[]
        for idx,r in day.iterrows():
            h,a=str(r.home_team),str(r.away_team); loc=venue(r.home_id,season)
            row={'index':idx,'opp_elo20_diff':mean(h,0,adjusted)-mean(a,0,adjusted),'adjusted_gf20_diff':mean(h,1,adjusted)-mean(a,1,adjusted),'adjusted_ga20_diff':mean(h,2,adjusted)-mean(a,2,adjusted),
                'travel_km_diff':distance(last_venue.get(h),loc)-distance(last_venue.get(a),loc),
                'games7_diff':sum(0<(date-z).days<=7 for z in dates[h])-sum(0<(date-z).days<=7 for z in dates[a]),
                'games3_diff':sum(0<(date-z).days<=3 for z in dates[h])-sum(0<(date-z).days<=3 for z in dates[a]),
                'away_streak_diff':-away_streak[a]}
            rows.append(row)
            # Residual scoring against the opponent's PRIOR attack/defence only.
            updates.append((r,loc,elo[h],elo[a],mean(a,1,history),mean(a,0,history),mean(h,1,history),mean(h,0,history)))
        for r,loc,eh,ea,h_opp_ga,h_opp_gf,a_opp_ga,a_opp_gf in updates:
            h,a=str(r.home_team),str(r.away_team);hg,ag=float(r.home_score),float(r.away_score)
            adjusted[h].append((ea,hg-h_opp_ga,ag-h_opp_gf));adjusted[a].append((eh,ag-a_opp_ga,hg-a_opp_gf))
            history[h].append((hg,ag));history[a].append((ag,hg))
            expected=1/(1+10**(-(eh+35-ea)/400));delta=20*(int(r.home_win)-expected)
            elo[h]+=delta;elo[a]-=delta
            for team in [h,a]: dates[team].append(date);last_venue[team]=loc
            away_streak[h]=0;away_streak[a]+=1
    return pd.DataFrame(rows).set_index('index').reindex(d.index)

QUALITY=['xg_for20_diff','xg_against20_diff','xg_share20_diff']
def quality_features(d,q):
    q=q.copy();q['gameDate']=pd.to_datetime(q.gameDate.astype(str),format='%Y%m%d')
    if q.duplicated(['gameId','team']).any():raise ValueError('Duplicate MoneyPuck team-game rows')
    history=defaultdict(lambda:deque(maxlen=20));rows=[];previous=None
    bygame={(int(r.gameId),str(r.team)):r for _,r in q.iterrows()}
    def info(team):
        vals=list(history[team])
        if len(vals)<3:return np.array([np.nan]*3)
        gf=np.mean([x[0] for x in vals]);ga=np.mean([x[1] for x in vals])
        return np.array([gf,ga,gf/(gf+ga) if gf+ga else np.nan])
    matches=0
    for (season,date),day in d.sort_values(['season','game_date','game_id']).groupby(['season','game_date'],sort=False):
        if previous!=season:history.clear()
        previous=season
        for idx,r in day.iterrows(): rows.append({'index':idx,**dict(zip(QUALITY,info(str(r.home_team))-info(str(r.away_team))))})
        for _,r in day.iterrows():
            for team in [str(r.home_team),str(r.away_team)]:
                z=bygame.get((int(r.game_id),team))
                if z is not None and z.gameDate==date:
                    vals=[float(z.xGoalsFor),float(z.xGoalsAgainst)]
                    if np.isfinite(vals).all() and min(vals)>=0:
                        matches+=1;history[team].append(vals)
    return pd.DataFrame(rows).set_index('index').reindex(d.index), matches/(2*len(d))

def evaluate(d,x,features,name):
    ys=[];ps=[];seasons=[];parts=[]
    for season in DEV:
        tr=d.index[d.season<season];te=d.index[d.season==season]
        m=model(features);m.fit(x.loc[tr,features],d.loc[tr,'home_win']);p=m.predict_proba(x.loc[te,features])[:,1];y=d.loc[te,'home_win'].to_numpy()
        ys.extend(y);ps.extend(p);seasons.append({'season':season,**met(y,p)})
        z=d.loc[te,['game_id','season','game_date','home_team','away_team','home_win']].copy();z['candidate']=name;z['home_win_prob']=p;parts.append(z)
    return {**met(np.asarray(ys),np.asarray(ps)),'by_season':seasons},pd.concat(parts,ignore_index=True)

def main():
    d=base.load('runtime/nhl/games');d=d[d.season<=DEV[-1]].reset_index(drop=True)
    bx=base.build_features(d);t=adv.load_team_stats();t=t[t.season.astype(str)<=DEV[-1]]
    x,af=adv.attach(d,bx,t,20);x=x.join(contextual_features(d));leader=base.FEATURES+af
    variants=[('advanced_all_w20',[],False),('opponent_adjusted',OPP,False),('schedule_travel',SCHEDULE,False),('opponent_plus_schedule',OPP+SCHEDULE,False)]
    source=json.loads(Path('runtime/nhl/quality_status.json').read_text());coverage=None
    if source['available']:
        q=pd.read_csv('runtime/nhl/moneypuck_team_games.csv');qx,coverage=quality_features(d,q);x=x.join(qx)
        if coverage>=.99:
            variants += [('shot_quality_exploratory',QUALITY,True),('all_factors_exploratory',OPP+SCHEDULE+QUALITY,True)]
        else: source['reason']='Insufficient team-game match coverage; shot-quality candidates not run'
    results=[];predictions=[]
    for name,extra,exploratory in variants:
        z,p=evaluate(d,x,leader+extra,name);results.append({'candidate':name,'features':leader+extra,'exploratory':exploratory,**z});predictions.append(p)
    reference=results[0]
    for r in results:
        r['seasons_with_brier_improvement']=sum(a['brier']<b['brier'] for a,b in zip(r['by_season'],reference['by_season']))
        r['eligible_for_promotion']=r['candidate']!='advanced_all_w20' and not r['exploratory'] and r['brier']<reference['brier'] and r['log_loss']<reference['log_loss'] and r['accuracy']>=reference['accuracy'] and r['seasons_with_brier_improvement']>=3
    results.sort(key=lambda r:(r['brier'],r['log_loss'],-r['accuracy']))
    out=Path('research/nhl/results');out.mkdir(parents=True,exist_ok=True)
    pd.concat(predictions,ignore_index=True).to_csv(out/'factor_oof_predictions.csv',index=False)
    payload={'selection_seasons':DEV,'excluded_from_selection':['20252026'],'ranking':results,'quality_source':source,'quality_team_game_coverage':coverage,'feature_coverage':{c:float(x.loc[d.season.isin(DEV),c].notna().mean()) for c in OPP+SCHEDULE},'arena_distance_limitation':'approximate arena-to-arena straight-line travel, no itinerary or historic neutral-site adjustment','decision_rule':'improve both Brier/log loss, preserve accuracy, improve Brier in >=3/4 seasons; unverified retrospective xG ineligible'}
    (out/'factor_tournament.json').write_text(json.dumps(payload,indent=2)+'\n')
    lines=['# NHL Additional Factor Tournament','','Development only: 2021–22 to 2024–25. 2025–26 removed before features. Same-date outcomes update state after prediction.','','| Candidate | Accuracy | Brier | Log loss | Seasons improving | Eligible |','|---|---:|---:|---:|---:|---|']
    for r in results:lines.append(f"| {r['candidate']} | {r['accuracy']:.2%} | {r['brier']:.6f} | {r['log_loss']:.6f} | {r['seasons_with_brier_improvement']} | {r['eligible_for_promotion']} |")
    lines+=['', 'MoneyPuck.com is credited for exploratory expected-goals inputs. Historical model vintage is unverified; xG candidates cannot be promoted.',f'Quality source status: {source}; matched coverage: {coverage}.','Travel uses approximate arena-to-arena distances; actual itineraries and neutral-site adjustments are unavailable.','Opponent scoring residuals compare prior results with each opponent’s scoring/conceding record available before that prior game.','',payload['decision_rule']]
    (out/'FACTOR_TOURNAMENT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
