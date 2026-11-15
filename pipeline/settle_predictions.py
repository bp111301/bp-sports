"""Settle immutable B.P. Sports prediction snapshots and write tracking metrics."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd

def prob_home(row,pick_col,conf_col): return float(row[conf_col]) if row[pick_col]==row.home_team else 1-float(row[conf_col])
def metrics(frame,pick_col,conf_col):
    if frame.empty: return {'games':0,'correct':0,'accuracy':None,'brier':None,'log_loss':None}
    y=(frame.actual_home_score>frame.actual_away_score).astype(int).to_numpy(); p=np.array([prob_home(r,pick_col,conf_col) for _,r in frame.iterrows()]); pred=np.where(p>=.5,frame.home_team,frame.away_team); actual=np.where(y==1,frame.home_team,frame.away_team)
    p=np.clip(p,.001,.999); return {'games':len(frame),'correct':int(np.sum(pred==actual)),'accuracy':float(np.mean(pred==actual)),'brier':float(np.mean((p-y)**2)),'log_loss':float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p)))}
def main():
    p=argparse.ArgumentParser();p.add_argument('--ledger',default='data/ledger/prediction_ledger.csv')
    p.add_argument('--schedules',help='Deprecated: scores alone are not evidence of a confirmed final')
    a=p.parse_args()
    # Both entry points use official completed/post status and the same guards.
    import check_finals
    check_finals.REQUEST_ERRORS.clear()
    check_finals.nfl(pd.Timestamp.now(tz='UTC'),ledger_path=a.ledger)
    if check_finals.REQUEST_ERRORS:raise SystemExit('Some final checks failed; verified results were preserved')
if __name__=='__main__': main()
