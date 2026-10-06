"""Shared final-result checks; original forecast fields are never rewritten."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ALIASES={'Southern Mississippi':'Southern Miss','UT San Antonio':'UTSA','Sam Houston State':'Sam Houston','Connecticut':'UConn','UMass':'Massachusetts'}
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
    if not (np.isfinite(h) and np.isfinite(a) and min(h,a)>=0 and h!=a):return None
    p=float(prediction['home_win_prob'])
    if not np.isfinite(p) or not 0<=p<=1:return None
    winner=prediction['home_team'] if h>a else prediction['away_team']
    return dict(home_points_final=float(h),away_points_final=float(a),actual_winner=winner,correct=float(prediction['predicted_winner']==winner),brier=(p-int(h>a))**2,settled_at_utc=now.isoformat())

def checked_schedule_fields(ledger,index):
    d=ledger.copy()
    if d.prediction_id.duplicated().any():raise ValueError('Duplicate CFB snapshot IDs')
    d['schedule_kickoff_utc']=[index.get(int(g),{}).get('start_date') for g in d.game_id]
    return d
