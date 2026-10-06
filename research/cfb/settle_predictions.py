"""Grade frozen CFB V1 snapshots only from completed, timing-valid schedule results."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from settlement_guard import schedule_index,result_for,checked_schedule_fields
FIELDS=['home_points_final','away_points_final','actual_winner','correct','brier','settled_at_utc']
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ledger',default='data/cfb/ledger/prediction_ledger.csv');ap.add_argument('--schedule',default='runtime/cfb/schedules/cfb_schedules_2026.csv.gz');ap.add_argument('--summary',default='data/cfb/ledger/summary.json');a=ap.parse_args()
    index=schedule_index(pd.read_csv(a.schedule,low_memory=False));d=checked_schedule_fields(pd.read_csv(a.ledger),index);now=pd.Timestamp.now(tz='UTC');count=0
    for c in FIELDS:
        if c not in d:d[c]=pd.Series([None]*len(d),dtype='object')
    for c in ['actual_winner','settled_at_utc']:d[c]=d[c].astype('object')
    for i,r in d.iterrows():
        if pd.notna(r.get('correct')):continue
        result=result_for(r,index.get(int(r.game_id)),now)
        if result:
            for c,value in result.items():d.at[i,c]=value
            d.at[i,'status']='SETTLED';count+=1
    d.to_csv(a.ledger,index=False);scored=d[d.correct.notna()];summary=dict(model_version='CFB_V1',ledger_games=len(d),settled_games=len(scored),pending_games=len(d)-len(scored),updated_at_utc=now.isoformat(),grading_rule='Completed final, matched teams, verified actual kickoff after capture; immutable first snapshot')
    if len(scored):summary.update(wins=int(scored.correct.sum()),losses=int(len(scored)-scored.correct.sum()),accuracy=float(scored.correct.mean()),brier=float(scored.brier.mean()))
    Path(a.summary).write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(dict(settled_now=count,**summary),indent=2))
if __name__=='__main__':main()
