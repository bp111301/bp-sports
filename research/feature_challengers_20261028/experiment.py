"""Registered feature ablation. Never trains on live labels or writes live feeds."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


cfb = module('feature_cfb', HERE.parent/'challengers_20261028/cfb.py')
nhl = module('feature_nhl', HERE.parent/'challengers_20261028/nhl.py')
audit = module('feature_confidence', ROOT/'confidence_audit.py')
strength = module('feature_intervals', HERE.parent/'strength_challengers_20261028/experiment.py')

EXTRA_BASES = [f'{side}_{name}' for name in ['wepa','3rd_down_pct','scoring_opp_rate_oe','starting_fp','rroe','plays_per_game'] for side in ['off','def']]


def expanded_cfb(d):
    x, px, cf, pf = cfb.matrices(d)
    extra = pd.DataFrame(index=d.index)
    for f in EXTRA_BASES:
        required = [f'{side}_{f}' for side in ['home','away']]+[f'prev_{side}_{f}' for side in ['home','away']]
        if not set(required).issubset(d.columns):
            raise ValueError('Missing registered pregame feature '+f)
        extra[f'blend_{f}_diff'] = cfb.pri.blend_side(d, 'home', f, 7.)-cfb.pri.blend_side(d, 'away', f, 7.)
    for kind in ['pass_epa','rush_epa','success_rate']:
        vals = {(side, unit):cfb.pri.blend_side(d, side, f'{unit}_{kind}', 7.) for side in ['home','away'] for unit in ['off','def']}
        extra[f'matchup_{kind}_interaction'] = vals['home','off']*vals['away','def']-vals['away','off']*vals['home','def']
    # Only explicitly constructed whitelisted values enter either learner.
    if len(extra.columns) != 15 or len(set(cf+pf)&(cfb.base.RETROSPECTIVE_BLOCKLIST|cfb.base.MARKET_BLOCKLIST)):
        raise ValueError('Feature allowlist violated')
    extra = extra.replace([np.inf,-np.inf], np.nan)
    return x, px, cf, pf, extra


RATE_SPECS = [
    ('shoot', 'goalsFor', 'shotsForPerGame', False, 100., .1),
    ('save', 'goalsAgainst', 'shotsAgainstPerGame', True, 100., .9),
    ('pp', 'powerPlayGoalsFor', 'ppOpportunities', False, 20., .2),
    ('pk', 'ppGoalsAgainst', 'timesShorthanded', True, 20., .8),
]


def pooled_rates(d, t):
    """Ratio of summed opportunities, not an average of game percentages."""
    t = t.copy()
    t['date'] = pd.to_datetime(t.gameDate, utc=True).dt.normalize()
    t['season'] = t.season.astype(str)
    if t.date.isna().any() or t.duplicated(['season','gameId','teamId']).any():
        raise ValueError('Invalid team game identity or source date')
    t = t.sort_values(['date','gameId','teamId']).reset_index(drop=True)
    date_ns = t.date.astype('int64').to_numpy()
    # Date cutoffs are determined from official game identities, never vendor xG dates.
    dates = pd.to_datetime(d.game_date, utc=True).dt.normalize()
    count_arrays = {}
    for name, numerator, denominator, invert, _, _ in RATE_SPECS:
        num = pd.to_numeric(t[numerator], errors='coerce').to_numpy(float)
        den = pd.to_numeric(t[denominator], errors='coerce').to_numpy(float)
        valid = np.isfinite(num)&np.isfinite(den)&(num>=0)&(den>=0)
        count_arrays[name] = (num, den, valid, np.r_[0.,np.cumsum(np.where(valid,num,0.))], np.r_[0.,np.cumsum(np.where(valid,den,0.))])
    team_groups = {(str(s),int(team)):g.index.to_numpy() for (s,team),g in t.groupby(['season','teamId'])}
    columns = [f'pooled_{s[0]}20_diff' for s in RATE_SPECS]
    out = pd.DataFrame(index=d.index, columns=columns, dtype=float)
    boundaries = []
    for date in sorted(dates.unique()):
        cutoff = pd.Timestamp(date)-pd.Timedelta(days=2)
        cutoff_ns = cutoff.value
        stop = int(np.searchsorted(date_ns, cutoff_ns, side='right'))
        priors = {}
        for name, _, _, invert, _, default in RATE_SPECS:
            num, den, valid, cumulative_num, cumulative_den = count_arrays[name]
            rate = cumulative_num[stop]/cumulative_den[stop] if cumulative_den[stop]>0 else (1-default if invert else default)
            priors[name] = float(np.clip(1-rate if invert else rate, 0, 1))
        test = d.index[dates.eq(date)]
        needed = {(str(d.at[i,'season']),int(d.at[i,side])) for i in test for side in ['home_id','away_id']}
        team_rates = {}
        for key in needed:
            ix = team_groups.get(key, np.array([],dtype=int))
            end = np.searchsorted(date_ns[ix], cutoff_ns, side='right')
            ix = ix[max(0,end-20):end]
            values = []
            for name, _, _, invert, pseudo, _ in RATE_SPECS:
                num, den, valid, _, _ = count_arrays[name]
                use = ix[valid[ix]]
                if len(use)<3:
                    values.append(np.nan)
                    continue
                numerator = float(num[use].sum())
                denominator = float(den[use].sum())
                if invert:
                    numerator = denominator-numerator
                values.append(float(np.clip((numerator+pseudo*priors[name])/(denominator+pseudo),0,1)))
            team_rates[key] = np.array(values)
        for i in test:
            season = str(d.at[i,'season'])
            out.loc[i] = team_rates[season,int(d.at[i,'home_id'])]-team_rates[season,int(d.at[i,'away_id'])]
        boundaries.append({'target_date':str(date),'source_max_date':str(t.iloc[stop-1].date) if stop else None,
                           'source_team_games':stop,'league_prior_rates':priors})
    return out, boundaries


def score_predictions(pred, sport):
    scores = {}
    for name, g in pred.groupby('candidate'):
        recent = g[g.season.ge('2023' if sport=='cfb' else '20232024')]
        scores[name] = {'overall':audit.summarize(g.probability,g.home_win),
            'by_season':[{'season':s,**audit.summarize(q.probability,q.home_win)} for s,q in g.groupby('season')],
            'recent':audit.summarize(recent.probability,recent.home_win)}
    intervals = strength.paired_interval(pred)
    control = scores['control']
    decisions = {}
    for name, candidate in scores.items():
        if name == 'control':continue
        a,b = candidate['overall'],control['overall']
        am,bm = a['overall'],b['overall']
        improved = sum(q['overall']['brier']<c['overall']['brier'] for q,c in zip(candidate['by_season'],control['by_season']))
        ar,br = candidate['recent']['overall'],control['recent']['overall']
        checks = {'accuracy_gain':am['accuracy']>=bm['accuracy']+(.005 if sport=='cfb' else .003),
            'brier':am['brier']<bm['brier'],'log_loss':am['log_loss']<bm['log_loss'], 'ece':a['ece']<=b['ece'],
            'season_consistency':improved>=(5 if sport=='cfb' else 3),
            'recent_accuracy':ar['accuracy']>=br['accuracy'],'recent_brier':ar['brier']<=br['brier'],'recent_log_loss':ar['log_loss']<=br['log_loss']}
        decisions[name] = {'research_eligible':bool(all(checks.values())), 'checks':{k:bool(v) for k,v in checks.items()},
                           'seasons_brier_improved':improved,'production_promoted':False,**intervals[name]}
    return scores,decisions


def run(sport):
    boundaries = []
    if sport == 'cfb':
        d = cfb.guarded_data(ROOT/'runtime/challengers_20261028/cfb/matchup_line')
        x,px,cf,pf,extra = expanded_cfb(d)
        z = x.join(extra);pz = px.join(extra);features=cf+list(extra);pfeatures=pf+list(extra)
        seasons = list(range(2018,2026))
        names = ['expanded_linear','expanded_halfblend']
    else:
        d,t = nhl.selection_data(ROOT/'runtime/challengers_20261028/nhl/team_game_stats')
        x,af = nhl.adv.attach(d,nhl.base.build_features(d),t,20)
        cf = nhl.base.FEATURES+af
        extra,boundaries = pooled_rates(d,t)
        retain = [f for f in af if not any(k in f for k in ['shoot_pct','save_pct','pp_rate','pk_rate'])]
        z = x.join(extra);features=nhl.base.FEATURES+retain+list(extra)
        seasons = nhl.DEV;names=['pooled_rates','pooled_rates_halfblend']
    rows = []
    for season in seasons:
        tr,te = d.index[d.season.lt(season)], d.index[d.season.eq(season)]
        if not len(tr) or not len(te) or not d.loc[tr,'season'].lt(season).all():raise ValueError('Invalid fold')
        if sport == 'cfb':
            control = cfb.fit_parts(d,x,px,cf,pf,tr);candidate=cfb.fit_parts(d,z,pz,features,pfeatures,tr)
            p = cfb.ensemble(control,x,px,cf,pf,te);q=cfb.ensemble(candidate,z,pz,features,pfeatures,te)
        else:
            control=nhl.learner(cf,True);candidate=nhl.learner(features,False)
            control.fit(x.loc[tr,cf],d.loc[tr,'home_win']);candidate.fit(z.loc[tr,features],d.loc[tr,'home_win'])
            p=control.predict_proba(x.loc[te,cf])[:,1];q=candidate.predict_proba(z.loc[te,features])[:,1]
        for name,prob in [('control',p),(names[0],q),(names[1],.5*p+.5*q)]:
            for i,v in zip(te,prob):
                rows.append({'game_id':int(d.at[i,'game_id']),'season':str(season),'candidate':name,
                    'block':f'{season}:{d.at[i,"week"]}' if sport=='cfb' else str(d.at[i,'game_date']),
                    'home_win':int(d.at[i,'home_win']),'probability':float(v),'training_max_season':str(d.loc[tr,'season'].max())})
        print(sport,season,'complete',flush=True)
    pred=pd.DataFrame(rows);scores,decisions=score_predictions(pred,sport)
    previous=json.loads((HERE.parent/f'challengers_20261028/results/{sport}/development_results.json').read_text())
    control=scores['control']['overall']['overall']
    for k in ['games','accuracy','brier','log_loss']:
        if not np.isclose(control[k],previous['scores']['control']['overall'][k],rtol=0,atol=1e-12):raise ValueError('Control parity failed '+k)
    result={'sport':sport,'status':'reused_historical_development_only','live_labels_used':False,
        'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),
        'scores':scores,'decisions':decisions,'features':features,'new_features':list(extra),
        'missingness':{c:float(extra.loc[d.season.isin(seasons),c].isna().mean()) for c in extra},
        'control_reproduction_tolerance':1e-12}
    out=ROOT/'runtime/feature_challengers_20261028'/sport;out.mkdir(parents=True,exist_ok=True)
    pred.to_csv(out/'predictions.csv',index=False)
    extra.join(d[['game_id','season']]).to_csv(out/'new_features.csv',index=False)
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    if boundaries:(out/'temporal_boundaries.json').write_text(json.dumps(boundaries,indent=2)+'\n')
    print(json.dumps({'sport':sport,'scores':{k:v['overall'] for k,v in scores.items()},'decisions':decisions},indent=2),flush=True)
    return result


if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--sport',required=True,choices=['cfb','nhl']);a=ap.parse_args();run(a.sport)
