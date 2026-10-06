"""Score Candidate B against embedded frozen V1 on identical prospective shadow games."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import brier_score_loss,log_loss
def metrics(y,p):
 if len(y)==0:return {"games":0}
 pred=(p>=.5).astype(int);return {"games":int(len(y)),"accuracy":float((pred==y).mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--ledger",default="data/cfb/v2_shadow/verified_prediction_ledger.csv");ap.add_argument("--out",default="data/cfb/v2_shadow/summary.json");a=ap.parse_args();p=Path(a.ledger)
 if not p.exists():
  Path(a.out).write_text(json.dumps({"model_version":"CFB_V2_CANDIDATE_B","status":"PROSPECTIVE_SHADOW_ONLY","settled_games":0,"promotion_status":"AWAITING_IDENTITY_VERIFIED_PREGAME_SNAPSHOTS"},indent=2)+"\n");return
 d=pd.read_csv(p);settled=d.get("settled",pd.Series(False,index=d.index)).astype(str).str.lower().isin(["true","1","yes"]);d=d[settled&d.get("actual_winner",pd.Series(None,index=d.index)).notna()].copy()
 if d.empty:payload={"model_version":"CFB_V2_CANDIDATE_B","status":"PROSPECTIVE_SHADOW_ONLY","settled_games":0,"promotion_status":"INSUFFICIENT_PROSPECTIVE_EVIDENCE"}
 else:
  y=(d.actual_winner.astype(str)==d.home_team.astype(str)).astype(int).to_numpy();pb=pd.to_numeric(d.home_win_prob).to_numpy();pv=pd.to_numeric(d.v1_home_win_prob).to_numpy();mb=metrics(y,pb);mv=metrics(y,pv);dis=((pb>=.5)!=(pv>=.5));payload={"model_version":"CFB_V2_CANDIDATE_B","status":"PROSPECTIVE_SHADOW_ONLY","settled_games":int(len(d)),"candidate_b":mb,"frozen_v1":mv,"delta_accuracy":mb["accuracy"]-mv["accuracy"],"delta_brier":mb["brier"]-mv["brier"],"delta_log_loss":mb["log_loss"]-mv["log_loss"],"winner_disagreements":int(dis.sum()),"promotion_status":"SHADOW_TEST_CONTINUES"}
 Path(a.out).write_text(json.dumps(payload,indent=2)+"\n");print(json.dumps(payload,indent=2))
if __name__=="__main__":main()
