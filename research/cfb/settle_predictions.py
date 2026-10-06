"""Settle immutable CFB V1 prediction snapshots from the unified ESPN schedule."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

SETTLEMENT_FIELDS=["home_points_final","away_points_final","actual_winner","correct","brier","settled_at_utc"]

def truthy(s):
    if s.dtype==bool:return s
    return s.astype(str).str.lower().isin(["true","1","yes"])

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--ledger",default="data/cfb/ledger/prediction_ledger.csv");ap.add_argument("--schedule",default="runtime/cfb/schedules/cfb_schedules_2026.csv.gz");ap.add_argument("--summary",default="data/cfb/ledger/summary.json");a=ap.parse_args()
    ledger=Path(a.ledger)
    if not ledger.exists(): raise SystemExit("No CFB ledger yet.")
    d=pd.read_csv(ledger);s=pd.read_csv(a.schedule,low_memory=False);s["game_id"]=pd.to_numeric(s.game_id,errors="coerce")
    finals=s[truthy(s["completed"])][["game_id","home_points","away_points"]].dropna(subset=["home_points","away_points"]).drop_duplicates("game_id")
    m=d.merge(finals,on="game_id",how="left",suffixes=("","_schedule"));now=datetime.now(timezone.utc).isoformat()
    for c in SETTLEMENT_FIELDS:
        if c not in d:d[c]=np.nan if c not in ("actual_winner","settled_at_utc") else None
    idx={str(v):i for i,v in enumerate(d.prediction_id)}
    settled_now=0
    for r in m[m.home_points.notna() & m.away_points.notna()].itertuples(index=False):
        i=idx[str(r.prediction_id)]
        if pd.notna(d.at[i,"correct"]):continue
        hp=float(r.home_points);apts=float(r.away_points);actual=r.home_team if hp>apts else r.away_team
        y=1.0 if hp>apts else 0.0;p=float(r.home_win_prob)
        d.at[i,"home_points_final"]=hp;d.at[i,"away_points_final"]=apts;d.at[i,"actual_winner"]=actual;d.at[i,"correct"]=float(str(r.predicted_winner)==str(actual));d.at[i,"brier"]=(p-y)**2;d.at[i,"settled_at_utc"]=now;d.at[i,"status"]="SETTLED";settled_now+=1
    d.to_csv(ledger,index=False)
    settled=d[d["correct"].notna()].copy();summary={"model_version":"CFB_V1","ledger_games":int(len(d)),"settled_games":int(len(settled)),"pending_games":int(len(d)-len(settled)),"updated_at_utc":now}
    if len(settled):
        summary.update({"wins":int(settled.correct.sum()),"losses":int(len(settled)-settled.correct.sum()),"accuracy":float(settled.correct.mean()),"brier":float(settled.brier.mean())})
    p=Path(a.summary);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(summary,indent=2)+"\n");print(json.dumps({"settled_now":settled_now,**summary},indent=2))
if __name__=="__main__":main()
