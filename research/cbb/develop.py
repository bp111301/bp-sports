"""Chronological CBB research. The 2026 holdout is deliberately not loaded."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/'
BASE = ['elo_diff', 'home_advantage']
STATS = ['off_eff', 'def_eff', 'efg', 'tov_rate', 'orb_rate', 'ft_rate', 'pace']
FEATURES = BASE + [x+'_diff' for x in STATS] + ['rest_diff', 'experience_diff']
PRIOR = dict(off_eff=103., def_eff=103., efg=.5, tov_rate=.18, orb_rate=.28, ft_rate=.30, pace=69.)


def fetch(season, kind, cache, refresh=False):
    family, prefix = ('schedules', 'mbb_schedule') if kind == 'schedule' else ('team_boxscores', 'team_box')
    url = ROOT+'espn_mens_college_basketball_'+family+'/'+prefix+f'_{season}.parquet'
    path = cache/f'{kind}_{season}.parquet'
    if refresh or not path.exists():
        with urlopen(Request(url, headers={'User-Agent':'BP-Sports-CBB-Research/1.0'}), timeout=60) as response:
            raw = response.read(30*1024*1024+1)
        if len(raw)>30*1024*1024:raise ValueError('Source too large')
        path.write_bytes(raw)
    raw = path.read_bytes()
    return pd.read_parquet(io.BytesIO(raw)), {'url':url, 'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw)}


def ident(value):
    return str(int(value)) if pd.notna(value) else ''


def season_games(season, cache):
    schedule, sm = fetch(season, 'schedule', cache)
    boxes, bm = fetch(season, 'box', cache)
    audit = {'season':season, 'schedule_rows':len(schedule), 'box_rows':len(boxes), 'sources':[sm,bm], 'exclusions':defaultdict(int)}
    if schedule.game_id.duplicated().any():raise ValueError('Duplicate schedule game IDs')
    if boxes.duplicated(['game_id','team_id']).any():raise ValueError('Duplicate team-game box rows')
    box_groups = {ident(k):v for k,v in boxes.groupby('game_id')}
    games = []
    for s in schedule.to_dict('records'):
        reason = None
        if s['season_type'] != 2:reason = 'not_regular_season'
        elif not s['status_type_completed'] or s['status_type_name'] != 'STATUS_FINAL':reason = 'not_confirmed_final'
        elif pd.isna(s['neutral_site']):reason = 'venue_unknown'
        elif s.get('away_non_div1_team') is True or str(s.get('away_non_div1_team')).lower()=='true':reason = 'non_division_i'
        elif pd.isna(s['home_conference_id']) or pd.isna(s['away_conference_id']):reason = 'division_or_conference_unknown'
        if reason:audit['exclusions'][reason]+=1;continue
        gid, home, away = ident(s['game_id']), ident(s['home_id']), ident(s['away_id'])
        pair = box_groups.get(gid)
        if pair is None or len(pair)!=2 or {ident(x) for x in pair.team_id}!={home,away}:
            audit['exclusions']['missing_or_unpaired_box']+=1;continue
        b = {ident(x['team_id']):x for x in pair.to_dict('records')}
        h,a = b[home],b[away]
        if ident(h['opponent_team_id'])!=away or ident(a['opponent_team_id'])!=home:raise ValueError('Nonreciprocal opponents')
        if h['team_score']!=s['home_score'] or a['team_score']!=s['away_score']:raise ValueError('Schedule/box score mismatch')
        if h['team_score']==a['team_score']:raise ValueError('Final basketball tie')
        needed = ['team_score','field_goals_made','field_goals_attempted','three_point_field_goals_made',
                  'free_throws_attempted','offensive_rebounds','defensive_rebounds','turnovers']
        if any(pd.isna(x.get(k)) for x in (h,a) for k in needed):
            audit['exclusions']['missing_stats']+=1;continue
        start = pd.to_datetime(s['date'], utc=True, errors='coerce')
        if pd.isna(start):audit['exclusions']['invalid_start']+=1;continue
        values = {}
        for team, own, opp in [(home,h,a),(away,a,h)]:
            own_poss = own['field_goals_attempted']-own['offensive_rebounds']+own['turnovers']+.475*own['free_throws_attempted']
            opp_poss = opp['field_goals_attempted']-opp['offensive_rebounds']+opp['turnovers']+.475*opp['free_throws_attempted']
            poss = (own_poss+opp_poss)/2
            if poss<=0 or own['field_goals_attempted']<=0:raise ValueError('Invalid possession denominator')
            rebounds = own['offensive_rebounds']+opp['defensive_rebounds']
            values[team] = dict(off_eff=100*own['team_score']/poss, def_eff=100*opp['team_score']/poss,
                                efg=(own['field_goals_made']+.5*own['three_point_field_goals_made'])/own['field_goals_attempted'],
                                tov_rate=own['turnovers']/poss, orb_rate=own['offensive_rebounds']/rebounds if rebounds else np.nan,
                                ft_rate=own['free_throws_attempted']/own['field_goals_attempted'], pace=poss)
        games.append(dict(game_id=gid,season=season,start=start,day=start.floor('D'),home_id=home,away_id=away,
                          home=s['home_display_name'],away=s['away_display_name'],neutral=bool(s['neutral_site']),
                          home_score=int(s['home_score']),away_score=int(s['away_score']),y=int(s['home_score']>s['away_score']),values=values))
    audit['eligible_games'] = len(games)
    audit['neutral_games'] = sum(x['neutral'] for x in games)
    audit['exclusions'] = dict(audit['exclusions'])
    return games, audit


def build_features(games):
    """Use a full intervening UTC day as an embargo for unknown final timestamps."""
    elo = defaultdict(lambda:1500.)
    prior = {}
    last = {}
    rows = []
    frame = pd.DataFrame(games).sort_values(['start','game_id'])
    for season, season_frame in frame.groupby('season', sort=True):
        elo = defaultdict(lambda:1500., {k:1500.+.65*(v-1500.) for k,v in elo.items()})
        sums = defaultdict(lambda:defaultdict(float)); counts = defaultdict(int)
        pending = []
        def update(batch):
            changes = defaultdict(float)
            for g in batch:
                h,a=g['home_id'],g['away_id']
                p=1/(1+10**(-((elo[h]-elo[a])+(0 if g['neutral'] else 65))/400))
                changes[h]+=24*(g['y']-p);changes[a]-=24*(g['y']-p)
                for team in [h,a]:
                    for name,value in g['values'][team].items():sums[team][name]+=value if math.isfinite(value) else PRIOR[name]
                    counts[team]+=1;last[team]=g['day']
            for team,change in changes.items():elo[team]+=change
        for day, day_frame in season_frame.groupby('day', sort=True):
            while pending and pending[0][0] < day-pd.Timedelta(days=1):
                _, batch = pending.pop(0)
                update(batch)
            for g in day_frame.to_dict('records'):
                h,a = g['home_id'],g['away_id']
                item = {k:g[k] for k in ['game_id','season','start','home','away','home_id','away_id','neutral','y','home_score','away_score']}
                item.update(elo_diff=elo[h]-elo[a],home_advantage=0. if g['neutral'] else 1.)
                for name in STATS:
                    def average(team):return (sums[team][name]+8*prior.get(team,PRIOR)[name])/(counts[team]+8)
                    item[name+'_diff'] = average(h)-average(a)
                def rest(team):return min(14,(day-last[team]).days) if team in last else 7
                item['rest_diff'] = rest(h)-rest(a)
                item['experience_diff'] = math.log1p(counts[h])-math.log1p(counts[a])
                item['elo_probability'] = 1/(1+10**(-(item['elo_diff']+65*item['home_advantage'])/400))
                rows.append(item)
            pending.append((day,[g for g in day_frame.to_dict('records') if g.get('forecast',False)!=True]))
        # The season has ended before any following season's forecasts are built.
        for _,batch in pending:update(batch)
        prior = {team:{k:sums[team][k]/counts[team] for k in STATS} for team in counts if counts[team]>0}
    return pd.DataFrame(rows)


def score(y,p):
    return dict(games=len(y),correct=int(((p>=.5)==y).sum()),accuracy=float(accuracy_score(y,p>=.5)),
                brier=float(brier_score_loss(y,p)),log_loss=float(log_loss(y,p,labels=[0,1])))


def develop(frame, development_season=2025):
    training=frame[frame.season<=development_season-2];cal=frame[frame.season==development_season-1];dev=frame[frame.season==development_season]
    if any(x.empty for x in [training,cal,dev]):raise ValueError('Missing chronological split')
    result={'status':'development_only_not_frozen','train_seasons':sorted(training.season.unique().tolist()),
            'calibration_season':development_season-1,'development_season':development_season,'untouched_holdout_season':2026,
            'scope':'regular season; both teams have conference identifiers; explicit non-DI excluded',
            'safety':'full intervening UTC-day embargo; previous-season priors; no market or final-season ratings', 'models':{}}
    predictions=dev[['game_id','season','start','home','away','neutral','y','home_score','away_score']].copy()
    predictions['elo']=dev.elo_probability
    result['models']['elo']=score(dev.y.to_numpy(),dev.elo_probability.to_numpy())
    for name,features in [('elo_logistic',BASE),('team_stats',FEATURES)]:
        model=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=1.,max_iter=2000,random_state=0))
        model.fit(training[features],training.y)
        pcal=model.predict_proba(cal[features])[:,1]
        calibrator=LogisticRegression(C=100.,max_iter=1000,random_state=0)
        calibrator.fit(np.log(np.clip(pcal,1e-8,1-1e-8)/(1-np.clip(pcal,1e-8,1-1e-8))).reshape(-1,1),cal.y)
        p=model.predict_proba(dev[features])[:,1]
        p=calibrator.predict_proba(np.log(np.clip(p,1e-8,1-1e-8)/(1-np.clip(p,1e-8,1-1e-8))).reshape(-1,1))[:,1]
        predictions[name]=p;result['models'][name]=score(dev.y.to_numpy(),p)
        result['models'][name]['features']=features
        result['models'][name]['neutral']=score(dev[dev.neutral].y.to_numpy(),p[dev.neutral.to_numpy()])
        result['models'][name]['non_neutral']=score(dev[~dev.neutral].y.to_numpy(),p[~dev.neutral.to_numpy()])
        result['models'][name]['confidence_bands']=[]
        confidence=np.maximum(p,1-p)
        for lo,hi in [(.5,.6),(.6,.7),(.7,.8),(.8,.9),(.9,1.01)]:
            mask=(confidence>=lo)&(confidence<hi)
            result['models'][name]['confidence_bands'].append({'lower':lo,'upper':hi,**score(dev.y.to_numpy()[mask],p[mask])})
    result['home_pick_baseline_accuracy']=float(dev.y.mean())
    return result,predictions


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',default='runtime/cbb');parser.add_argument('--output',default='research/cbb/results')
    args=parser.parse_args();cache=Path(args.cache);cache.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:seasons=list(pool.map(lambda y:season_games(y,cache),range(2020,2026)))
    games=[g for season,_ in seasons for g in season]
    features=build_features(games)
    result,predictions=develop(features)
    result['chronological_development_folds']={}
    for season in [2023,2024,2025]:
        fold,_=develop(features[features.season<=season],season)
        result['chronological_development_folds'][str(season)]={k:fold[k] for k in ['train_seasons','calibration_season','development_season','models']}
    result['data_audit']=[audit for _,audit in seasons]
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    (output/'development.json').write_text(json.dumps(result,indent=2)+'\n')
    predictions.to_csv(output/'development_predictions.csv',index=False)
    print(json.dumps({k:v for k,v in result.items() if k!='data_audit'},indent=2))


if __name__=='__main__':main()
