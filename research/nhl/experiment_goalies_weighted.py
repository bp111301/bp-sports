"""Bounded follow-up to the failed first goalie layer; development seasons only."""
from collections import Counter, defaultdict, deque
import json
from pathlib import Path
import numpy as np
import pandas as pd
from experiment_goalies import base, adv, load_goalies, eval_model, DEV

PRIOR_SV = .905
PRIOR_SHOTS = 300

def weighted_features(d, g):
    # Player identity survives trades/seasons; team starter usage resets each season.
    bygame = {int(k): v for k, v in g.groupby('gameId')}
    starts = defaultdict(lambda: deque(maxlen=10))
    history = defaultdict(lambda: deque(maxlen=20))
    last = {}
    previous_season = None
    rows = []
    def info(team, date):
        counts = Counter(starts[team])
        if not counts:
            return np.array([PRIOR_SV, PRIOR_SV, 0., 0., 0.])
        # Mixture weights reflect prior starts, never the realized current starter.
        probable = next(p for p in reversed(starts[team]) if counts[p] == max(counts.values()))
        def quality(pid):
            samples = [q for q in history[pid] if (date - q[0]).days <= 365]
            saves = sum(q[1] for q in samples)
            shots = sum(q[2] for q in samples)
            return (saves + PRIOR_SHOTS * PRIOR_SV) / (shots + PRIOR_SHOTS)
        mixture = sum(counts[p] * quality(p) for p in counts) / sum(counts.values())
        rest = min((date - last[probable]).days, 14) if probable in last else 14
        workload = sum(q[2] for q in history[probable] if 0 < (date-q[0]).days <= 7)
        return np.array([quality(probable), mixture, rest, workload, counts[probable]/sum(counts.values())])
    # Batch by day: no same-date outcome can enter another game's prediction.
    for (season, date), daily in d.sort_values(['season','game_date','game_id']).groupby(['season','game_date'], sort=False):
        if season != previous_season:
            starts = defaultdict(lambda: deque(maxlen=10))
        previous_season = season
        for idx, r in daily.iterrows():
            values = info(str(r.home_team), date) - info(str(r.away_team), date)
            rows.append((idx, values))
        for _, r in daily.iterrows():
            z = bygame.get(int(r.game_id))
            if z is None:
                continue
            for _, q in z.iterrows():
                pid = int(q.playerId)
                shots = pd.to_numeric(q.shotsAgainst, errors='coerce')
                saves = pd.to_numeric(q.saves, errors='coerce')
                if pd.notna(shots) and pd.notna(saves) and shots > 0 and 0 <= saves <= shots:
                    history[pid].append((date, float(saves), float(shots)))
                    last[pid] = date
                if pd.to_numeric(q.gamesStarted, errors='coerce') > 0:
                    starts[str(q.teamAbbrev)].append(pid)
    names = ['weighted_goalie_probable_diff','weighted_goalie_mixture_diff','weighted_goalie_rest_diff','weighted_goalie_workload_diff','weighted_goalie_share_diff']
    return pd.DataFrame([v for _,v in rows], index=[i for i,_ in rows], columns=names).reindex(d.index)

def main():
    d = base.load('runtime/nhl/games')
    d = d[d.season <= DEV[-1]].reset_index(drop=True)
    bx = base.build_features(d)
    ax, af = adv.attach(d, bx, adv.load_team_stats(), 20)
    gx = weighted_features(d, load_goalies())
    ax = ax.join(gx)
    leader = base.FEATURES + af
    variants = [ ('advanced_all_w20', []),
        ('advanced_weighted_probable', ['weighted_goalie_probable_diff']),
        ('advanced_weighted_mixture', ['weighted_goalie_mixture_diff']),
        ('advanced_weighted_workload', list(gx.columns)) ]
    ranking = [{ 'candidate':name, 'features':leader+extra, **eval_model(d, ax, leader+extra)} for name,extra in variants]
    ranking.sort(key=lambda r:(r['brier'],r['log_loss'],-r['accuracy']))
    baseline = next(r for r in ranking if r['candidate']=='advanced_all_w20')
    for r in ranking:
        r['seasons_with_brier_improvement'] = sum(a['brier'] < b['brier'] for a,b in zip(r['by_season'],baseline['by_season']))
        r['eligible_for_promotion'] = r['candidate'] != 'advanced_all_w20' and r['brier'] < baseline['brier'] and r['log_loss'] < baseline['log_loss'] and r['accuracy'] >= baseline['accuracy'] and r['seasons_with_brier_improvement'] >= 3
    payload = {'selection_seasons':DEV,'excluded_from_selection':['20252026'],'prior_save_pct':PRIOR_SV,'prior_shots':PRIOR_SHOTS,'ranking':ranking,'decision':'keep team-stat leader unless a goalie candidate improves aggregate Brier/log loss, does not reduce accuracy, and improves Brier in at least 3 of 4 seasons'}
    out = Path('research/nhl/results')
    (out/'goalie_weighted_tournament.json').write_text(json.dumps(payload,indent=2)+'\n')
    lines = ['# NHL Weighted Goalie Follow-up','','Development results only; 2025–26 excluded. Fixed .905 / 300-shot prior; no prior tuning. Starter usage uses prior team starts; player shot-weighted history follows identity across teams/seasons and expires after 365 days. All outcomes update after the entire date is predicted.','','| Candidate | Accuracy | Brier | Log loss | Seasons improving Brier | Eligible |','|---|---:|---:|---:|---:|---|']
    for r in ranking:
        lines.append(f"| {r['candidate']} | {r['accuracy']:.2%} | {r['brier']:.6f} | {r['log_loss']:.6f} | {r['seasons_with_brier_improvement']} | {r['eligible_for_promotion']} |")
    lines += ['',payload['decision']]
    (out/'GOALIE_WEIGHTED_TOURNAMENT.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
