"""Fixed strength experiments. Writes only new runtime research outputs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


cfb = module('strength_cfb', HERE.parent/'challengers_20261028/cfb.py')
nhl = module('strength_nhl', HERE.parent/'challengers_20261028/nhl.py')


def strength_features(games, sport):
    """All coefficients are refit from dates <= target date minus two days."""
    d = games.copy()
    d['date'] = pd.to_datetime(d['date'], utc=True).dt.normalize()
    if d.date.isna().any() or d.duplicated('game_id').any():
        raise ValueError('Invalid date or duplicate game')
    for c in ['home_id', 'away_id']:
        if d[c].isna().any():
            raise ValueError('Missing stable team identity')
        d[c] = d[c].astype(int)
    if (d.home_id == d.away_id).any():
        raise ValueError('Team cannot play itself')
    if not np.isfinite(d[['home_score', 'away_score', 'home_field']].to_numpy(float)).all():
        raise ValueError('Nonfinite completed-game inputs')
    clip, hfa, half, penalty = (42., 3., 180., 10.) if sport == 'cfb' else (5., .2, 90., 20.)
    ids = sorted(set(d.home_id) | set(d.away_id))
    lookup = {t: i for i, t in enumerate(ids)}
    design = np.zeros((len(d), len(ids)))
    design[np.arange(len(d)), d.home_id.map(lookup)] = 1
    design[np.arange(len(d)), d.away_id.map(lookup)] = -1
    y = np.clip(d.home_score.to_numpy()-d.away_score.to_numpy(), -clip, clip)-hfa*d.home_field.to_numpy()
    result = pd.DataFrame(index=d.index, columns=['strength_diff'], dtype=float)
    audit = []
    for date in sorted(d.date.unique()):
        age = (date-d.date).dt.days.to_numpy()
        tr = (age >= 2) & (age <= 365)
        te = np.flatnonzero(d.date.eq(date).to_numpy())
        coef = np.zeros(len(ids))
        if tr.any():
            w = np.exp2(-age[tr]/half)
            a = design[tr]
            coef = np.linalg.solve(a.T@(w[:, None]*a)+penalty*np.eye(len(ids)), a.T@(w*y[tr]))
        result.loc[d.index[te], 'strength_diff'] = design[te]@coef
        audit.append({'target_date':str(date), 'training_games':int(tr.sum()),
                      'training_max_date':str(d.loc[tr, 'date'].max()) if tr.any() else None})
    return result, audit


def nonlinear():
    return HistGradientBoostingClassifier(learning_rate=.05, max_iter=150,
        max_leaf_nodes=7, max_depth=3, min_samples_leaf=50, l2_regularization=10,
        max_bins=255, early_stopping=False, random_state=20261028)


def paired_interval(g):
    pivot = g.pivot(index='game_id', columns='candidate', values='probability')
    meta = g[g.candidate.eq('control')].set_index('game_id').loc[pivot.index]
    y = meta.home_win.to_numpy()
    correct = (pivot.to_numpy() >= .5) == y[:, None]
    blocks = pd.DataFrame(correct.astype(int), index=pivot.index, columns=pivot.columns)
    blocks['block'] = meta.block
    counts = blocks.groupby('block').size().to_numpy()
    totals = blocks.groupby('block')[list(pivot.columns)].sum().to_numpy()
    rng = np.random.default_rng(20261028)
    selected = rng.integers(0, len(counts), size=(2000, len(counts)))
    rates = totals[selected].sum(axis=1)/counts[selected].sum(axis=1)[:, None]
    control = list(pivot.columns).index('control')
    return {name: {'accuracy_difference':float(correct[:, j].mean()-correct[:, control].mean()),
            'paired_block_bootstrap_95pct':np.quantile(rates[:, j]-rates[:, control], [.025, .975]).tolist()}
            for j, name in enumerate(pivot.columns) if name != 'control'}


def evaluate(sport, data_dir, out_dir):
    if sport == 'cfb':
        d = cfb.guarded_data(data_dir)
        x, px, cf, pf = cfb.matrices(d)
        games = d.rename(columns={'start_date':'date', 'home_team_id':'home_id', 'away_team_id':'away_id',
                                  'home_points':'home_score', 'away_points':'away_score'}).copy()
        games['home_field'] = x.home_field
        seasons = list(range(2018, 2026))
        metric = cfb.base.score
    else:
        d, t = nhl.selection_data(data_dir)
        x, af = nhl.adv.attach(d, nhl.base.build_features(d), t, 20)
        cf = nhl.base.FEATURES+af
        pf = cf.copy()
        px = x.copy()
        games = d.rename(columns={'game_date':'date'}).copy()
        games['home_field'] = 1.
        seasons = nhl.DEV
        metric = nhl.adv.metrics
    strength, audit = strength_features(games, sport)
    x['strength_diff'] = strength.strength_diff
    px['strength_diff'] = strength.strength_diff
    sf, sp = cf+['strength_diff'], pf+['strength_diff']
    rows = []
    for season in seasons:
        tr = d.index[d.season.lt(season)]
        te = d.index[d.season.eq(season)]
        if not len(tr) or not len(te) or not d.loc[tr, 'season'].lt(season).all():
            raise ValueError('Invalid chronological training boundary')
        if sport == 'cfb':
            control = cfb.fit_parts(d, x, px, cf, pf, tr)
            linear = cfb.fit_parts(d, x, px, sf, sp, tr)
            p = cfb.ensemble(control, x, px, cf, pf, te)
            pl = cfb.ensemble(linear, x, px, sf, sp, te)
        else:
            control = nhl.learner(cf, True)
            linear = nhl.learner(sf, False)
            control.fit(x.loc[tr, cf], d.loc[tr, 'home_win'])
            linear.fit(x.loc[tr, sf], d.loc[tr, 'home_win'])
            p = control.predict_proba(x.loc[te, cf])[:, 1]
            pl = linear.predict_proba(x.loc[te, sf])[:, 1]
        tree = nonlinear()
        tree.fit(px.loc[tr, sp], d.loc[tr, 'home_win'])
        pb = .5*p+.5*tree.predict_proba(px.loc[te, sp])[:, 1]
        for name, prob in [('control', p), ('strength_linear', pl), ('strength_nonlinear50', pb)]:
            for i, v in zip(te, prob):
                rows.append({'game_id':int(d.at[i, 'game_id']), 'season':str(season),
                    'date':str(games.at[i, 'date']), 'candidate':name,
                    'block':f'{season}:{d.at[i, "week"]}' if sport == 'cfb' else str(games.at[i, 'date']),
                    'home_win':int(d.at[i, 'home_win']), 'probability':float(v),
                    'strength_diff':float(x.at[i, 'strength_diff']), 'training_max_season':str(d.loc[tr, 'season'].max())})
        print(sport, season, 'complete', flush=True)
    pred = pd.DataFrame(rows)
    scores = {}
    for name, g in pred.groupby('candidate'):
        scores[name] = {'overall':metric(g.home_win.to_numpy(), g.probability.to_numpy()),
            'by_season':[{'season':str(s), **metric(q.home_win.to_numpy(), q.probability.to_numpy())}
                         for s, q in g.groupby('season')]}
        recent = g[g.season.ge('2023' if sport == 'cfb' else '20232024')]
        scores[name]['recent'] = metric(recent.home_win.to_numpy(), recent.probability.to_numpy())
    intervals = paired_interval(pred)
    decisions = {}
    control = scores['control']
    for name in ['strength_linear', 'strength_nonlinear50']:
        candidate = scores[name]
        a, b = candidate['overall'], control['overall']
        checks = {'accuracy_gain_threshold':a['accuracy'] >= b['accuracy']+(.005 if sport == 'cfb' else .003),
            'brier_improved':a['brier'] < b['brier'], 'log_loss_improved':a['log_loss'] < b['log_loss'],
            'season_consistency':sum(s['brier'] < c['brier'] for s, c in zip(candidate['by_season'], control['by_season'])) >= (5 if sport == 'cfb' else 3),
            'recent_accuracy_preserved':candidate['recent']['accuracy'] >= control['recent']['accuracy']}
        decisions[name] = {'research_eligible':bool(all(checks.values())), 'checks':{k:bool(v) for k,v in checks.items()},
                           'production_promoted':False, **intervals[name]}
    # Exact same source/control must reproduce the previous bounded experiment.
    previous = json.loads((HERE.parent/f'challengers_20261028/results/{sport}/development_results.json').read_text())
    for k, v in previous['scores']['control']['overall'].items():
        if k in scores['control']['overall'] and not np.isclose(v, scores['control']['overall'][k], rtol=0, atol=1e-12):
            raise ValueError('Control no longer reproduces prior development: '+k)
    result = {'status':'reused_historical_development_only', 'sport':sport,
        'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),
        'scores':scores, 'decisions':decisions, 'new_features':['strength_diff'],
        'linear_features':sf, 'nonlinear_features':sp, 'control_reproduction_tolerance':1e-12,
        'live_labels_used':False, 'source_manifest_reference':'research/challengers_20261028/source_manifest.json'}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pred.to_csv(out/'development_predictions.csv', index=False)
    (out/'strength_boundaries.json').write_text(json.dumps(audit, indent=2)+'\n')
    (out/'development_results.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'sport':sport, 'scores':{k:v['overall'] for k,v in scores.items()}, 'decisions':decisions}, indent=2), flush=True)
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sport', required=True, choices=['cfb','nhl'])
    ap.add_argument('--data-dir')
    ap.add_argument('--out-dir')
    a = ap.parse_args()
    evaluate(a.sport, a.data_dir or f'runtime/challengers_20261028/{a.sport}/'+('matchup_line' if a.sport == 'cfb' else 'team_game_stats'),
             a.out_dir or f'runtime/strength_challengers_20261028/{a.sport}')
