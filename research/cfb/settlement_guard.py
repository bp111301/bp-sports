"""Shared final-result checks; original forecast fields are never rewritten."""
import csv,hashlib,io
import json
from pathlib import Path
import numpy as np
import pandas as pd

def eligible_snapshots(frame, now):
    """Reject unknown kickoffs and games that crossed kickoff during inference."""
    start=pd.to_datetime(frame.kickoff_utc,utc=True,errors='coerce')
    captured=pd.to_datetime(frame.snapshot_created_utc,utc=True,errors='coerce')
    confirmed=frame.kickoff_time_tbd.map(lambda value:str(value).lower() in ('false','0','0.0'))
    return frame.loc[confirmed & start.gt(now) & captured.le(now) & captured.lt(start)].copy()

def write_results(path,before,after):
    """Only result fields and separately verified schedule metadata may change."""
    mutable={'status','settled','home_points_final','away_points_final','actual_winner',
             'correct','brier','settled_at_utc','schedule_kickoff_utc'}
    locked=[c for c in before if c not in mutable]
    pd.testing.assert_frame_equal(before[locked],after[locked],check_dtype=False)
    with Path(path).open(newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    if len(rows)!=len(after):raise ValueError('CFB saved forecast count changed')
    extra=[c for c in after if c not in fields]
    if set(extra)-mutable:raise ValueError('Unexpected CFB forecast schema change')
    fields+=extra;changed=bool(extra)
    for row,old,new in zip(rows,before.to_dict('records'),after.to_dict('records')):
        for field in mutable & set(after.columns):
            a,b=old.get(field),new[field]
            if (pd.isna(a) and pd.isna(b)) or a==b:continue
            row[field]='' if pd.isna(b) else str(b);changed=True
    if not changed:return
    output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=fields)
    writer.writeheader();writer.writerows(rows)
    path=Path(path);temporary=path.with_suffix('.csv.partial')
    temporary.write_text(output.getvalue());temporary.replace(path)

ALIASES={'Louisiana Monroe':'UL Monroe','Southern Mississippi':'Southern Miss','UT San Antonio':'UTSA','Sam Houston State':'Sam Houston','Connecticut':'UConn','UMass':'Massachusetts'}
def team(name):return ALIASES.get(str(name),str(name))
def flag(value):return str(value).lower() in ('true','1','1.0','yes')
def verify_bundle(path,manifest):
    m=json.loads(Path(manifest).read_text())
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=m['sha256']:raise ValueError('Frozen CFB bundle hash mismatch')
    return m

def schedule_index(schedule):
    s=schedule.copy();s['game_id']=pd.to_numeric(s.game_id,errors='raise')
    if s.game_id.duplicated().any():raise ValueError('Duplicate schedule game IDs')
    return {int(r['game_id']):r for r in s.to_dict('records')}

def result_for(prediction,actual,now,freeze=None):
    if not actual or not flag(actual.get('completed',False)):return None
    if team(prediction['home_team'])!=team(actual['home_team']) or team(prediction['away_team'])!=team(actual['away_team']):return None
    captured=pd.to_datetime(prediction['snapshot_created_utc'],utc=True,errors='coerce')
    kickoff=pd.to_datetime(actual['start_date'],utc=True,errors='coerce')
    if pd.isna(captured) or pd.isna(kickoff) or not captured<kickoff<now:return None
    if flag(actual.get('start_time_tbd',False)):return None
    if freeze is not None and captured<pd.Timestamp(freeze):return None
    h=pd.to_numeric(actual.get('home_points'),errors='coerce');a=pd.to_numeric(actual.get('away_points'),errors='coerce')
    if not (np.isfinite(h) and np.isfinite(a) and min(h,a)>=0 and h!=a and float(h).is_integer() and float(a).is_integer()):return None
    p=float(prediction['home_win_prob'])
    if not np.isfinite(p) or not 0<=p<=1:return None
    winner=prediction['home_team'] if h>a else prediction['away_team']
    return dict(home_points_final=float(h),away_points_final=float(a),actual_winner=winner,correct=float(prediction['predicted_winner']==winner),brier=(p-int(h>a))**2,settled_at_utc=now.isoformat())

def checked_schedule_fields(ledger,index):
    d=ledger.copy()
    if d.prediction_id.duplicated().any():raise ValueError('Duplicate CFB snapshot IDs')
    d['schedule_kickoff_utc']=[index.get(int(g),{}).get('start_date') for g in d.game_id]
    return d

