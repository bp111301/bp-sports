"""Evaluate locked NHL weights on the excluded season, without any tuning."""
import hashlib,json
from pathlib import Path
import joblib
import pandas as pd
from experiment_goalies import base,adv
from calibrate_leader import apply_calibrator,metrics,bucket_table
from freeze_leader import checksum

def main():
    root=Path('model/nhl/v1');out=Path('research/nhl/results')
    if (out/'excluded_season_evaluation.json').exists():raise ValueError('Excluded-season evaluation is already recorded; do not rerun or tune')
    manifest=json.loads((root/'bundle_manifest.json').read_text());payload=joblib.load(root/'frozen_bundle.joblib');config=payload['config']
    if checksum(root/'frozen_bundle.joblib')!=manifest['bundle_sha256'] or checksum(root/'config.json')!=manifest['config_sha256']:raise ValueError('Frozen checksum mismatch')
    train=base.load('runtime/nhl/freeze_training_games');test=base.load('runtime/nhl/excluded_evaluation_games')
    if set(train.season)!=set(config['training_seasons']) or set(test.season)!={config['excluded_evaluation_season']}:raise ValueError('Unexpected evaluation seasons')
    d=pd.concat([train,test],ignore_index=True).sort_values(['season','game_date','game_id']).reset_index(drop=True)
    teams=pd.concat([adv.load_team_stats('runtime/nhl/freeze_training_team_stats'),adv.load_team_stats('runtime/nhl/excluded_evaluation_team_stats')],ignore_index=True)
    bx=base.build_features(d);x,features=adv.attach(d,bx,teams,20)
    te=d.index[d.season==config['excluded_evaluation_season']];tr=d.index[d.season<config['excluded_evaluation_season']]
    baseline=base.model();baseline.fit(bx.loc[tr,base.FEATURES],d.loc[tr,'home_win'])
    z=d.loc[te,['game_id','season','game_date','home_team','away_team','home_win']].copy()
    z['calibrated_prob']=apply_calibrator(config['calibrator'],payload['model'].predict_proba(x.loc[te,config['features']])[:,1]);z['baseline_prob']=baseline.predict_proba(bx.loc[te,base.FEATURES])[:,1]
    leader=metrics(z);reference=metrics(z,'baseline_prob');eligible=leader['brier']<reference['brier'] and leader['log_loss']<reference['log_loss'] and leader['accuracy']>=reference['accuracy']
    buckets=bucket_table(z)
    result={'version':config['version'],'evaluation_season':config['excluded_evaluation_season'],'leader':leader,'baseline':reference,'eligible_for_prospective_shadow':bool(eligible),'by_month':[{'month':str(month),**metrics(q)} for month,q in z.groupby(z.game_date.dt.to_period('M'))],'confidence_buckets':buckets,'frozen_bundle_sha256':manifest['bundle_sha256'],'config_sha256':manifest['config_sha256'],'evaluation_source_sha256':{str(p):checksum(p) for folder in ['runtime/nhl/excluded_evaluation_games','runtime/nhl/excluded_evaluation_team_stats'] for p in sorted(Path(folder).glob('*.csv'))},'interpretation':'Excluded from candidate selection; baseline-only results were previously viewed. No tuning, calibration refit or classifier refit on excluded-season labels. Prior completed evaluation games update rolling features only.'}
    (out/'excluded_season_evaluation.json').write_text(json.dumps(result,indent=2)+'\n');z.to_csv(out/'excluded_season_predictions.csv',index=False)
    lines=['# NHL V1 Excluded-Season Evaluation','','2025–26; specification committed before evaluation. Model weights fit only on 2018–19 through 2024–25.','','| Model | Games | Accuracy | Brier | Log loss |','|---|---:|---:|---:|---:|']
    for name,r in [('Frozen NHL V1',leader),('Fixed baseline',reference)]:lines.append(f"| {name} | {r['games']} | {r['accuracy']:.2%} | {r['brier']:.6f} | {r['log_loss']:.6f} |")
    lines+=['',f'Eligible for prospective shadow: **{eligible}**. This does not activate production predictions.','',result['interpretation'],'','## Confidence buckets','','| Confidence | Games | Mean predicted | Actual win rate |','|---|---:|---:|---:|']
    for r in buckets:
        if r['games']:lines.append(f"| {r['bucket']} | {r['games']} | {r['mean_predicted']:.2%} | {r['actual_win_rate']:.2%} |")
    (out/'EXCLUDED_SEASON_EVALUATION.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
