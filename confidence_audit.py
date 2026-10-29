"""Read-only reliability summaries; never fits or changes forecast probabilities."""
import math
import numpy as np
import pandas as pd

BINS = [.5, .6, .7, .8, .9, 1.00000001]


def wilson(wins, games):
    if not games:
        return [None, None]
    z = 1.959963984540054
    p = wins/games
    den = 1+z*z/games
    center = (p+z*z/(2*games))/den
    half = z*math.sqrt(p*(1-p)/games+z*z/(4*games*games))/den
    return [max(0., center-half), min(1., center+half)]


def metric(p, y):
    p, y = np.asarray(p, float), np.asarray(y, float)
    if not len(p):
        return {'games':0}
    c = np.maximum(p, 1-p)
    wins = int(((p >= .5) == y).sum())
    q = np.clip(p, 1e-12, 1-1e-12)
    return {'games':len(p), 'wins':wins, 'losses':len(p)-wins,
        'accuracy':wins/len(p), 'mean_confidence':float(c.mean()),
        'confidence_minus_accuracy':float(c.mean()-wins/len(p)),
        'accuracy_ci95':wilson(wins, len(p)),
        'brier':float(np.mean((p-y)**2)),
        'log_loss':float(np.mean(-y*np.log(q)-(1-y)*np.log(1-q)))}


def summarize(p, y):
    p, y = np.asarray(p, float), np.asarray(y, float)
    if len(p) != len(y) or not np.isfinite(p).all() or not np.isfinite(y).all() or not np.isin(y,[0,1]).all() or ((p<0)|(p>1)).any():
        raise ValueError('Invalid probability or outcome')
    c = np.maximum(p, 1-p)
    out = {'overall':metric(p, y), 'buckets':[], 'ece':0.}
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        mask = (c >= lo)&(c < hi)
        m = metric(p[mask], y[mask])
        m.update(bucket=f'{lo:.0%}–{min(hi,1):.0%}', lower=lo, upper=min(hi,1), limited_sample=int(mask.sum())<100)
        out['buckets'].append(m)
        if mask.any():
            out['ece'] += abs(m['confidence_minus_accuracy'])*m['games']/len(p)
    return out


def audit_ledger(frame, sport, candidate=None, now=None):
    """Validate saved first forecasts before selecting settled rows at a cutoff."""
    d = frame.copy(deep=True)
    now = pd.Timestamp.now(tz='UTC') if now is None else pd.to_datetime(now, utc=True)
    if sport == 'NHL':
        required = {'candidate','game_id','home_win_prob','created_at_utc','start_time_utc','status','actual_home_win','settled_at_utc'}
    elif sport == 'CFB':
        required = {'game_id','model_version','home_win_prob','snapshot_created_utc','kickoff_utc','status','actual_winner','home_team','away_team','correct','settled_at_utc'}
    else:
        raise ValueError('Unsupported sport')
    if not required.issubset(d.columns):
        raise ValueError('Incomplete confidence ledger')
    if sport == 'NHL':
        if not candidate:
            raise ValueError('Select one NHL candidate')
        d = d[d.candidate.eq(candidate)].copy()
        created, start = d.created_at_utc, d.start_time_utc
        settled = d.status.eq('settled')
        y = pd.to_numeric(d.actual_home_win, errors='coerce')
    else:
        d = d[d.model_version.eq('CFB_V1')].copy()
        created = d.snapshot_created_utc
        start = d.schedule_kickoff_utc.fillna(d.kickoff_utc) if 'schedule_kickoff_utc' in d else d.kickoff_utc
        settled = d.status.eq('SETTLED')
        y = pd.Series(np.where(d.actual_winner.eq(d.home_team), 1., np.where(d.actual_winner.eq(d.away_team), 0., np.nan)),index=d.index)
    allowed_status = ['pending','settled'] if sport == 'NHL' else ['PREGAME_SNAPSHOT','SETTLED']
    if not d.status.isin(allowed_status).all():
        raise ValueError('Unknown forecast status')
    if d.game_id.isna().any() or d.duplicated('game_id').any():
        raise ValueError('Missing or duplicate model/game identity')
    p = pd.to_numeric(d.home_win_prob, errors='coerce')
    created = pd.to_datetime(created, utc=True, format='mixed', errors='coerce')
    start = pd.to_datetime(start, utc=True, format='mixed', errors='coerce')
    ended = pd.to_datetime(d.settled_at_utc, utc=True, format='mixed', errors='coerce')
    if (created.isna()|start.isna()|created.ge(start)|created.gt(now)|~p.between(0,1)).any():
        raise ValueError('Invalid pregame capture, timing, or probability')
    if (settled & (~y.isin([0,1])|ended.isna()|ended.gt(now)|ended.lt(start)|start.gt(now))).any():
        raise ValueError('Invalid settled outcome or settlement time')
    if sport == 'CFB':
        correct = pd.to_numeric(d.correct, errors='coerce')
        if (settled & (correct.ne(((p>=.5)==y).astype(int))|~correct.isin([0,1]))).any():
            raise ValueError('CFB grade disagrees with saved probability/outcome')
    report = summarize(p[settled], y[settled])
    report.update(sport=sport, candidate=candidate or 'CFB_V1', as_of_utc=now.isoformat(),
                  tracked_games=len(d), pending_games=int((~settled).sum()))
    return report
