"""Grade identity-verified Candidate B snapshots using completed schedule finals."""
import argparse
from pathlib import Path
import pandas as pd
from settlement_guard import verify_bundle,schedule_index,result_for,checked_schedule_fields,flag

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ledger',default='data/cfb/v2_shadow/verified_prediction_ledger.csv');ap.add_argument('--schedule',default='runtime/cfb/schedules/cfb_schedules_2026.csv.gz');a=ap.parse_args();path=Path(a.ledger)
    if not path.exists():print('No identity-verified shadow snapshots yet');return
    manifest=verify_bundle('model/cfb/v2/candidate_b_bundle.joblib','model/cfb/v2/candidate_b_manifest.json')
    index=schedule_index(pd.read_csv(a.schedule,low_memory=False));d=checked_schedule_fields(pd.read_csv(path),index);now=pd.Timestamp.now(tz='UTC')
    for c in ['actual_winner','correct','settled','home_points_final','away_points_final','brier','settled_at_utc']:
        if c not in d:d[c]=pd.Series([False if c=='settled' else None]*len(d),dtype='object')
    for c in ['actual_winner','settled_at_utc']:d[c]=d[c].astype('object')
    for i,r in d.iterrows():
        if flag(r.get('settled',False)):continue
        if r.get('bundle_sha256')!=manifest['sha256']:continue
        result=result_for(r,index.get(int(r.game_id)),now,manifest['created_utc'])
        if result:
            for c,value in result.items():d.at[i,c]=value
            d.at[i,'settled']=True;d.at[i,'status']='SETTLED'
    d.to_csv(path,index=False);print(f'Verified Candidate B settled={sum(flag(v) for v in d.settled)} total={len(d)}')
if __name__=='__main__':main()
