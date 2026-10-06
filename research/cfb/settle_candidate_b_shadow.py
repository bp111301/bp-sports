"""Settle Candidate B shadow snapshots without changing their pregame probabilities."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--ledger",default="data/cfb/v2_shadow/prediction_ledger.csv");ap.add_argument("--data",default="runtime/cfb/matchup_line/cfb_matchup_line_2026.csv");a=ap.parse_args();p=Path(a.ledger)
 if not p.exists():print("No shadow ledger yet");return
 led=pd.read_csv(p);g=pd.read_csv(a.data,low_memory=False);g["game_id"]=pd.to_numeric(g.game_id,errors="coerce");g["home_points"]=pd.to_numeric(g.home_points,errors="coerce");g["away_points"]=pd.to_numeric(g.away_points,errors="coerce");done=g[g.home_points.notna()&g.away_points.notna()&g.game_id.notna()].copy();done["actual_winner"]=done.apply(lambda r:r.home_team if r.home_points>r.away_points else r.away_team,axis=1);m=done.set_index("game_id")["actual_winner"].to_dict()
 if "actual_winner" not in led:led["actual_winner"]=pd.NA
 if "correct" not in led:led["correct"]=pd.NA
 if "settled" not in led:led["settled"]=False
 for i,r in led.iterrows():
  gid=pd.to_numeric(pd.Series([r.game_id]),errors="coerce").iloc[0]
  if pd.notna(gid) and gid in m and not bool(r.get("settled",False)):
   led.at[i,"actual_winner"]=m[gid];led.at[i,"correct"]=bool(r.predicted_winner==m[gid]);led.at[i,"settled"]=True
 led.to_csv(p,index=False);print(f"settled={int(led.settled.fillna(False).astype(bool).sum())} total={len(led)}")
if __name__=="__main__":main()
