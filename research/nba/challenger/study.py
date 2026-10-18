"""Chronological NBA availability residuals. V1 and 2026 evaluation are untouched."""
from collections import defaultdict,deque,Counter
from importlib.metadata import version
from pathlib import Path
import gzip
import hashlib
import json
import sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit,logit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import baseline as v1
from injuries import player_key
from prepare import history

STATUS=['Out','Doubtful','Questionable','Probable']
COUNTS=['count_'+s+'_diff' for s in STATUS]
LOADS=['minutes_'+s+'_diff' for s in STATUS]+['out_points_diff']
VARIANTS={'v1_replay':[],'coverage_control':[],'status_counts':COUNTS,'minutes_weighted':LOADS,'combined':COUNTS+LOADS}


def player_records(games,cache):
    accepted={str(r['game_id']):r for r in games.to_dict('records')};result=defaultdict(list);audits=[]
    for season in range(2020,2026):
        path=cache/f'player_box_{season}.parquet';frame=pd.read_parquet(path)
        frame=frame[(frame.season==season)&(frame.season_type==2)]
        if frame.duplicated(['game_id','athlete_id']).any():raise ValueError('Duplicate player-game identity')
        count=0
        for row in frame.itertuples():
            gid=str(int(row.game_id));g=accepted.get(gid)
            if g is None:continue
            side='home' if str(int(row.team_id))==g['home_id'] else 'away'
            other='away' if side=='home' else 'home'
            if str(int(row.team_id))!=g[side+'_id'] or str(int(row.opponent_team_id))!=g[other+'_id']:
                raise ValueError('Player team/opponent identity mismatch')
            if row.team_score!=g[side+'_score'] or row.opponent_team_score!=g[other+'_score']:
                raise ValueError('Player score identity mismatch')
            if not np.isfinite(row.minutes) or row.minutes<=0:continue
            if not np.isfinite(row.points) or not 0<=row.minutes<=80:raise ValueError('Invalid past player stats')
            result[gid].append(dict(athlete_id=str(int(row.athlete_id)),name=player_key(row.athlete_display_name),
                                    minutes=float(row.minutes),points=float(row.points)))
            count+=1
        audits.append(dict(season=season,rows=count,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_{season}.parquet'))
    return result,audits


def availability_features(games,contexts,players):
    if not set(games.season.unique())<=set(range(2016,2026)):raise ValueError('2026/future input rejected')
    names=defaultdict(set);past=defaultdict(lambda:deque(maxlen=20));rows=[]
    for day,batch in games.sort_values(['date','game_id']).groupby('date',sort=True):
        for g in batch.to_dict('records'):
            context=contexts.get(g['game_id'],{});sides=[];listed=matched=0
            known=all(context.get(side,{}).get('known',False) for side in ['home','away'])
            for side in ['home','away']:
                values={k:0. for k in COUNTS+LOADS}
                for player in context.get(side,{}).get('players',[]):
                    status=player['status']
                    if status not in STATUS:continue
                    listed+=1;values['count_'+status+'_diff']+=1
                    ids=names.get(player['key'],set())
                    if len(ids)!=1:continue
                    records=past[next(iter(ids))]
                    if not records:continue
                    matched+=1;mean=np.mean(records,axis=0)
                    values['minutes_'+status+'_diff']+=float(mean[0])
                    if status=='Out':values['out_points_diff']+=float(mean[1])
                sides.append(values)
            row=dict(game_id=g['game_id'],both_known=bool(known),listed_impact_players=listed,matched_impact_players=matched)
            row.update({k:sides[0][k]-sides[1][k] for k in COUNTS+LOADS});rows.append(row)
        # No game-day player participation, identity or points enter that day's forecasts.
        for g in batch.to_dict('records'):
            for p in players.get(g['game_id'],[]):
                names[p['name']].add(p['athlete_id']);past[p['athlete_id']].append([p['minutes'],p['points']])
    return pd.DataFrame(rows)


def fit_offset(train,test,columns):
    if train.season.max()>=test.season.min():raise ValueError('Nonchronological residual fit')
    if len(train)<500:raise ValueError('Insufficient earlier known-report training rows')
    x=train[columns].to_numpy(float);z=test[columns].to_numpy(float)
    mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale==0,1.,scale)
    a=np.column_stack([np.ones(len(train)),(x-mean)/scale]);b=np.column_stack([np.ones(len(test)),(z-mean)/scale])
    offset=logit(np.clip(train.baseline_probability.to_numpy(),1e-8,1-1e-8));y=train.y.to_numpy()
    def objective(beta):
        eta=offset+a@beta
        value=np.sum(np.logaddexp(0,eta)-y*eta)+.5*np.sum(beta[1:]**2)
        gradient=a.T@(expit(eta)-y);gradient[1:]+=beta[1:]
        return value,gradient
    solution=minimize(objective,np.zeros(a.shape[1]),jac=True,method='L-BFGS-B',options={'maxiter':1000,'ftol':1e-12,'gtol':1e-7})
    if not solution.success:raise ValueError('Residual optimization failed: '+solution.message)
    p=expit(logit(np.clip(test.baseline_probability.to_numpy(),1e-8,1-1e-8))+b@solution.x)
    return p,dict(training_rows=len(train),last_training_season=int(train.season.max()),features=columns,
                  mean=mean.tolist(),scale=scale.tolist(),coefficients=solution.x.tolist())


def evaluate(frame):
    if frame.season.max()>2025:raise ValueError('2026 evaluation prohibited')
    predictions=[];fits={}
    for season in [2023,2024,2025]:
        test=frame[frame.season==season].copy()
        train=frame[(frame.season<season)&(frame.season>=2021)&frame.both_known]
        known=test.both_known.to_numpy(bool)
        for name,columns in VARIANTS.items():
            p=test.baseline_probability.to_numpy().copy()
            if name!='v1_replay' and known.any():
                p[known],fit=fit_offset(train,test[known],columns);fits[f'{season}:{name}']=fit
            test[name]=p
        predictions.append(test)
    predicted=pd.concat(predictions,ignore_index=True)
    pooled={name:v1.metrics(predicted.y,predicted[name]) for name in VARIANTS}
    folds={str(s):{name:v1.metrics(g.y,g[name]) for name in VARIANTS} for s,g in predicted.groupby('season')}
    matched=predicted[predicted.both_known]
    secondary={name:v1.metrics(matched.y,matched[name]) for name in VARIANTS}
    decisions={}
    for name in ['status_counts','minutes_weighted','combined']:
        a,b,c=pooled[name],pooled['v1_replay'],pooled['coverage_control']
        improvements=sum(folds[str(s)][name]['brier']<folds[str(s)]['v1_replay']['brier'] for s in [2023,2024,2025])
        checks=dict(brier_gain=b['brier']-a['brier']>=.0005,log_loss=a['log_loss']<b['log_loss'],
                    accuracy=a['correct']>=b['correct'],two_seasons=improvements>=2,
                    latest_two=all(folds[str(s)][name]['brier']<folds[str(s)]['v1_replay']['brier'] for s in [2024,2025]),
                    beats_coverage_control=a['brier']<c['brier'] and a['log_loss']<c['log_loss'])
        paired=predicted[['date','y']].copy();paired['baseline_probability']=predicted[name];paired['elo_probability']=predicted.v1_replay
        decisions[name]=dict(development_shortlist=all(checks.values()),checks=checks,
                             additional_correct=a['correct']-b['correct'],date_bootstrap=v1.bootstrap(paired))
    return dict(pooled=pooled,folds=folds,both_submitted_secondary=secondary,decisions=decisions,fold_parameters=fits),predicted


def main():
    games=history();root=v1.ROOT/'research/nba/challenger';output=root/'results';output.mkdir(parents=True,exist_ok=True)
    contexts=json.loads((v1.ROOT/'runtime/nba/availability_contexts.json').read_text())
    coverage=json.loads((v1.ROOT/'runtime/nba/availability_coverage.json').read_text())
    receipts=json.loads((v1.ROOT/'runtime/nba/report_receipts.json').read_text())
    # Preserve the audit even if source quality prevents outcome evaluation.
    (output/'report_receipts.json.gz').write_bytes(gzip.compress(json.dumps(receipts,indent=2).encode(),mtime=0))
    (output/'availability_inputs.json.gz').write_bytes(gzip.compress(json.dumps(contexts).encode(),mtime=0))
    source_gate=all(coverage[str(s)]['both_known']/coverage[str(s)]['games']>=.7 for s in [2023,2024,2025])
    audit=dict(status='source_passed_pending_evaluation' if source_gate else 'blocked_source_coverage',
               candidate_outcomes_evaluated=False,source_quality_gate=source_gate,
               report_receipts=len(receipts),report_status_counts=dict(Counter(r['status'] for r in receipts)),
               reports_with_parse_issues=sum(bool(r.get('parse_issues')) for r in receipts),
               coverage=coverage,verified_team_files=20,verified_player_files=6,eligible_games=len(games),
               runtime={n:version(n) for n in ['pandas','numpy','scikit-learn','scipy','pyarrow','requests','pypdf','pytest']})
    def save_audit():
        audit['artifact_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()
                                 if p.is_file() and p.name!='source_audit.json'}
        (output/'source_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    save_audit()
    if not source_gate:
        (output/'comparison.json').write_text(json.dumps(dict(status='blocked_source_coverage',coverage=coverage,
            source_quality_gate=False,evaluated_seasons=[],excluded_season=2026,
            experiment_lock_sha256=hashlib.sha256((root/'EXPERIMENT_LOCK.json').read_bytes()).hexdigest()),indent=2)+'\n')
        raise SystemExit('Source quality gate failed; no candidate outcomes evaluated')
    players,player_audits=player_records(games,v1.ROOT/'runtime/nba')
    expected=json.loads((root/'PLAYER_SOURCES.json').read_text())
    if {r['season']:r['sha256'] for r in player_audits}!={r['season']:r['sha256'] for r in expected}:
        raise ValueError('Player-source hashes changed')
    (output/'player_audit.json').write_text(json.dumps(dict(accepted_positive_minute_player_rows=sum(r['rows'] for r in player_audits),
                                                          sources=player_audits),indent=2)+'\n')
    added=availability_features(games,contexts,players)
    # Verify the exact original baseline recipe on all archived OOF games first.
    replay=v1.evaluate(v1.build_features(games))
    original=pd.read_csv(v1.ROOT/'research/nba/results/baseline_oof_predictions.csv',dtype={'game_id':str})
    if replay.game_id.tolist()!=original.game_id.tolist():raise ValueError('V1 OOF identity/order mismatch')
    np.testing.assert_allclose(replay.baseline_probability,original.baseline_probability,rtol=0,atol=1e-12)
    frame=original.merge(added,on='game_id',validate='one_to_one')
    result,predictions=evaluate(frame)
    result.update(status='development_only_not_promoted',evaluated_seasons=[2023,2024,2025],excluded_season=2026,
                  coverage=coverage,source_quality_gate=source_gate,player_audits=player_audits,
                  v1_replay_verified_games=len(replay),v1_replay_max_error=float(np.max(np.abs(replay.baseline_probability-original.baseline_probability))),
                  impact_name_match=dict(listed=int(predictions.listed_impact_players.sum()),matched=int(predictions.matched_impact_players.sum())),
                  experiment_lock_sha256=hashlib.sha256((root/'EXPERIMENT_LOCK.json').read_bytes()).hexdigest(),
                  runtime={n:version(n) for n in ['pandas','numpy','scikit-learn','scipy','pyarrow','pypdf']},
                  limitations=['Previously inspected development seasons are exploratory, not a fresh holdout',
                               'Reports are afternoon snapshots, not guaranteed final active lists',
                               'Prior minutes/points are a simple importance proxy, not player impact ratings',
                               'Archived PDFs may have source corrections; hashes and embedded timestamps are retained'])
    prediction_bytes=predictions[['game_id','season','date','y','both_known',*VARIANTS]].to_csv(index=False).encode()
    result['predictions_sha256']=hashlib.sha256(prediction_bytes).hexdigest()
    (output/'predictions.csv.gz').write_bytes(gzip.compress(prediction_bytes,mtime=0))
    (output/'comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    audit.update(status='comparison_completed',candidate_outcomes_evaluated=True,v1_replay_verified_games=len(replay))
    save_audit()
    print(json.dumps({k:result[k] for k in ['pooled','coverage','impact_name_match','decisions']},indent=2))


if __name__=='__main__':main()
