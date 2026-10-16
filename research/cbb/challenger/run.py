"""Isolated CBB challenger: development seasons only; never changes V1 outputs."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import sys
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import develop as v1

ADJUSTED = ['adjusted_off_diff', 'adjusted_def_diff']
ROTATION = ['returning_share_diff', 'transfer_share_diff',
            'prior_minutes_experience_diff', 'rotation_known_diff']
VARIANTS = {'v1_replay': v1.FEATURES,
            'opponent_adjusted': v1.FEATURES + ADJUSTED,
            'observed_continuity': v1.FEATURES + ROTATION,
            'combined': v1.FEATURES + ADJUSTED + ROTATION}


def development_only(games):
    if not games or any(int(g['season']) not in range(2020, 2026) for g in games):
        raise ValueError('Only locked development seasons 2020–2025 are permitted')


def player_games(season, cache, games):
    """Join only accepted regular-season team games; audit missing player coverage."""
    path = cache / f'player_box_{season}.parquet'
    url = v1.ROOT + f'espn_mens_college_basketball_player_boxscores/player_box_{season}.parquet'
    if not path.exists():
        with urlopen(Request(url, headers={'User-Agent':'BP-Sports-CBB-Challenger/1.0'}), timeout=60) as response:
            raw = response.read(40*1024*1024+1)
        if len(raw) > 40*1024*1024:
            raise ValueError('Oversized player source')
        path.write_bytes(raw)
    raw = path.read_bytes()
    frame = pd.read_parquet(path)
    allowed = {g['game_id']: g for g in games}
    frame = frame[(frame.season == season) & (frame.season_type == 2)].copy()
    frame['gid'] = frame.game_id.map(v1.ident)
    frame = frame[frame.gid.isin(allowed)]
    rows, coverage = {}, defaultdict(int)
    for (gid, tid), group in frame.groupby(['gid', 'team_id']):
        team = v1.ident(tid)
        g = allowed[gid]
        if team not in (g['home_id'], g['away_id']):
            raise ValueError('Unexpected player team identity')
        opponent = g['away_id'] if team == g['home_id'] else g['home_id']
        expected_score = g['home_score'] if team == g['home_id'] else g['away_score']
        opponent_score = g['away_score'] if team == g['home_id'] else g['home_score']
        if any(v1.ident(x) != opponent for x in group.opponent_team_id):
            raise ValueError('Player opponent identity mismatch')
        if not group.team_score.eq(expected_score).all() or not group.opponent_team_score.eq(opponent_score).all():
            raise ValueError('Player score identity mismatch')
        active = group[pd.to_numeric(group.minutes, errors='coerce') > 0]
        if active.athlete_id.isna().any() or active.athlete_id.duplicated().any():
            raise ValueError('Missing or duplicated active athlete identity')
        minutes = {v1.ident(r.athlete_id): float(r.minutes) for r in active.itertuples()}
        # Partial rotation boxes must not silently stand in for a complete team.
        if not 190 <= sum(minutes.values()) <= 400:
            coverage['invalid_minute_total'] += 1
            continue
        if any(m > 80 or not math.isfinite(m) for m in minutes.values()):
            raise ValueError('Invalid player minutes')
        rows[(gid, team)] = minutes
    audit = dict(season=season, source_url=url,
                 sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                 eligible_team_games=2*len(games), complete_player_team_games=len(rows),
                 exclusions=dict(coverage))
    return rows, audit


def extra_features(games, players):
    """Opponent ratings and observed rotations obey V1's full UTC-day embargo."""
    development_only(games)
    prior_ratings, previous_players, previous_totals = {}, {}, {}
    rows = []
    frame = pd.DataFrame(games).sort_values(['start', 'game_id'])
    for season, season_frame in frame.groupby('season', sort=True):
        sums = defaultdict(lambda: defaultdict(float))
        count = defaultdict(int)
        rotation = defaultdict(lambda: defaultdict(float))
        pending = []

        def rating(team, kind):
            return (sums[team][kind] + 8*prior_ratings.get(team, {}).get(kind, 103.)) / (count[team]+8)

        def continuity(team):
            current = rotation[team]
            total = sum(current.values())
            if not total or not previous_totals:
                return dict(returning_share=.5, transfer_share=0., prior_minutes_experience=0., rotation_known=0.)
            old_team = previous_players.get(team, {})
            returning = sum(m for player, m in current.items() if player in old_team) / total
            transfers = sum(m for player, m in current.items()
                            if player not in old_team and player in previous_totals) / total
            experience = sum(m*math.log1p(previous_totals.get(player, 0.))
                             for player, m in current.items()) / total
            return dict(returning_share=returning, transfer_share=transfers,
                        prior_minutes_experience=experience, rotation_known=1.)

        def update(batch):
            # Evaluate opponent strengths before applying any results in this day.
            additions = []
            for g in batch:
                h, a = g['home_id'], g['away_id']
                for team, opponent in [(h, a), (a, h)]:
                    values = g['values'][team]
                    additions.append((team, values['off_eff'] - rating(opponent, 'def') + 103.,
                                      values['def_eff'] - rating(opponent, 'off') + 103.))
                    for player, minutes in players.get((g['game_id'], team), {}).items():
                        rotation[team][player] += minutes
            for team, off, defense in additions:
                sums[team]['off'] += off
                sums[team]['def'] += defense
                count[team] += 1

        for day, day_frame in season_frame.groupby('day', sort=True):
            while pending and pending[0][0] < day-pd.Timedelta(days=1):
                update(pending.pop(0)[1])
            batch = day_frame.to_dict('records')
            for g in batch:
                h, a = g['home_id'], g['away_id']
                rh, ra = continuity(h), continuity(a)
                item = dict(game_id=g['game_id'], adjusted_off_diff=rating(h, 'off')-rating(a, 'off'),
                            adjusted_def_diff=rating(h, 'def')-rating(a, 'def'))
                item.update({k+'_diff': rh[k]-ra[k] for k in rh})
                rows.append(item)
            pending.append((day, batch))
        for _, batch in pending:
            update(batch)
        prior_ratings = {t: {kind: sums[t][kind]/count[t] for kind in ['off', 'def']}
                         for t in count if count[t]}
        previous_players = {t: dict(minutes) for t, minutes in rotation.items() if minutes}
        previous_totals = defaultdict(float)
        for minutes in previous_players.values():
            for player, value in minutes.items():
                previous_totals[player] += value
    return pd.DataFrame(rows)


def fit_predict(frame, season, features):
    train = frame[frame.season <= season-2]
    cal = frame[frame.season == season-1]
    test = frame[frame.season == season]
    model = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(),
                          LogisticRegression(C=1., max_iter=2000, random_state=0))
    model.fit(train[features], train.y)

    def logits(values):
        p = np.clip(model.predict_proba(values)[:, 1], 1e-8, 1-1e-8)
        return np.log(p/(1-p)).reshape(-1, 1)

    calibrator = LogisticRegression(C=100., max_iter=1000, random_state=0)
    calibrator.fit(logits(cal[features]), cal.y)
    return calibrator.predict_proba(logits(test[features]))[:, 1]


def evaluate(frame):
    folds, all_predictions = {}, []
    for season in [2023, 2024, 2025]:
        test = frame[frame.season == season]
        predictions = test[['game_id', 'season', 'start', 'neutral', 'y']].copy()
        predictions['month'] = test.start.dt.month
        models = {}
        for name, features in VARIANTS.items():
            p = fit_predict(frame, season, features)
            predictions[name] = p
            models[name] = v1.score(test.y.to_numpy(), p)
            for label, mask in [('november', test.start.dt.month == 11), ('neutral', test.neutral)]:
                models[name][label] = v1.score(test.y.to_numpy()[mask], p[mask])
        # Assert exact recipe parity against the unchanged V1 development path.
        _, original = v1.develop(frame[frame.season <= season], season)
        if not np.allclose(original.team_stats, predictions.v1_replay, rtol=0, atol=1e-12):
            raise ValueError('V1 recipe replay mismatch')
        folds[str(season)] = models
        all_predictions.append(predictions)
    predictions = pd.concat(all_predictions, ignore_index=True)
    pooled = {name: v1.score(predictions.y.to_numpy(), predictions[name].to_numpy()) for name in VARIANTS}
    decisions = {}
    baseline = pooled['v1_replay']
    for name in list(VARIANTS)[1:]:
        candidate = pooled[name]
        better_folds = sum(folds[str(s)][name]['brier'] < folds[str(s)]['v1_replay']['brier'] for s in [2023, 2024, 2025])
        qualifies = (candidate['brier'] < baseline['brier'] and candidate['log_loss'] < baseline['log_loss']
                     and better_folds >= 2 and candidate['accuracy'] >= baseline['accuracy']-.002)
        decisions[name] = dict(development_shortlist=qualifies, brier_folds_improved=better_folds,
                               additional_correct=candidate['correct']-baseline['correct'],
                               accuracy_delta=candidate['accuracy']-baseline['accuracy'],
                               brier_delta=candidate['brier']-baseline['brier'],
                               log_loss_delta=candidate['log_loss']-baseline['log_loss'])
    return dict(folds=folds, pooled=pooled, decisions=decisions), predictions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', default='runtime/cbb')
    parser.add_argument('--output', default='research/cbb/challenger/results')
    args = parser.parse_args()
    cache, output = Path(args.cache), Path(args.output)
    cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        seasons = list(pool.map(lambda y: v1.season_games(y, cache), range(2020, 2026)))
    games = [g for batch, _ in seasons for g in batch]
    development_only(games)
    players, player_audits = {}, []
    for season, (batch, _) in zip(range(2020, 2026), seasons):
        records, audit = player_games(season, cache, batch)
        players.update(records)
        player_audits.append(audit)
    base = v1.build_features(games)
    extras = extra_features(games, players)
    frame = base.merge(extras, on='game_id', validate='one_to_one')
    result, predictions = evaluate(frame)
    result.update(status='development_only_not_promoted', seasons_loaded=list(range(2020, 2026)),
                  evaluated_seasons=[2023, 2024, 2025], excluded_seasons=[2026, 2027],
                  features=VARIANTS, team_source_audit=[audit for _, audit in seasons],
                  player_source_audit=player_audits,
                  runtime={name:version(name) for name in ['pandas','numpy','scikit-learn','pyarrow']},
                  v1_source_sha256=hashlib.sha256(Path(v1.__file__).read_bytes()).hexdigest(),
                  safety='Full intervening UTC-day embargo; no forecast-game player appearances; no 2026 input.',
                  limitations=['Development seasons previously inspected; these are exploratory comparisons, not new untouched tests.',
                               'Continuity is observed rotation only; unavailable before first eligible current-season boxes.',
                               'No injuries, preseason transfers or full roster adjustment; inherited DI and overtime limits.'])
    output.mkdir(parents=True, exist_ok=True)
    prediction_path = output/'predictions.csv'
    predictions.to_csv(prediction_path, index=False)
    result['predictions_sha256'] = hashlib.sha256(prediction_path.read_bytes()).hexdigest()
    (output/'comparison.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['pooled', 'decisions', 'player_source_audit']}, indent=2))


if __name__ == '__main__':
    main()
