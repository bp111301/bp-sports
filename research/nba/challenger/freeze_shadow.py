"""Freeze the strongest shortlisted variant for separate prospective observation."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import study
from prepare import history


def main():
    root=study.v1.ROOT;research=root/'research/nba/challenger'
    result=json.loads((research/'results/comparison.json').read_text())
    eligible=[n for n,d in result['decisions'].items() if d['development_shortlist']]
    selected=min(eligible,key=lambda n:(result['pooled'][n]['brier'],n))
    if selected!='minutes_weighted':raise ValueError('Selection differs from reviewed minutes-weighted result')
    games=history();players,audits=study.player_records(games,root/'runtime/nba')
    contexts=json.loads((root/'runtime/nba/availability_contexts.json').read_text())
    features=study.availability_features(games,contexts,players)
    original=pd.read_csv(root/'research/nba/results/baseline_oof_predictions.csv',dtype={'game_id':str})
    frame=original.merge(features,on='game_id',validate='one_to_one')
    train=frame[(frame.season>=2021)&(frame.season<=2025)&frame.both_known]
    _,fit=study.fit_offset(train,train.iloc[:1].assign(season=2027),study.VARIANTS[selected])
    manifest_path=root/'model/nba/v1/manifest.json'
    if not manifest_path.exists():manifest_path=root/'runtime/nba/v1_manifest.json'
    v1=json.loads(manifest_path.read_text())
    frozen=dict(status='frozen_prospective_shadow_only',created_at_utc=datetime.now(timezone.utc).isoformat(),
                selected=selected,fit=fit,training_seasons=[2021,2022,2023,2024,2025],training_last_date=train.date.max(),
                v1_bundle_sha256=v1['bundle_sha256'],experiment_lock_sha256=result['experiment_lock_sha256'],
                comparison_sha256=hashlib.sha256((research/'results/comparison.json').read_bytes()).hexdigest(),
                prospective_protocol_sha256=hashlib.sha256((research/'shadow/PROTOCOL.md').read_bytes()).hexdigest(),
                season=2027,weights_retrained_automatically=False,
                reserved_season_2026_used_for_fit_or_selection=False)
    out=root/'model/nba/availability-shadow/frozen.json';out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists() and json.loads(out.read_text())!=frozen:raise ValueError('Existing frozen artifact cannot be overwritten')
    out.write_text(json.dumps(frozen,indent=2,allow_nan=False)+'\n')
    sha=hashlib.sha256(out.read_bytes()).hexdigest()
    (out.parent/'manifest.json').write_text(json.dumps(dict(bundle_sha256=sha,status=frozen['status'],selected=selected,
        v1_bundle_sha256=v1['bundle_sha256']),indent=2)+'\n')
    print(json.dumps(dict(selected=selected,training_rows=len(train),bundle_sha256=sha),indent=2))


if __name__=='__main__':main()
