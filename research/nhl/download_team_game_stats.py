"""Download NHL Stats REST per-game team reports for leakage-safe rolling features."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd,requests

BASE="https://api.nhle.com/stats/rest/en/team"
REPORTS=["summary","powerplay","penaltykill"]

def fetch(report,season):
 params={"isAggregate":"false","isGame":"true","start":0,"limit":-1,"factCayenneExp":"gamesPlayed>=1","cayenneExp":f"seasonId={season} and gameTypeId=2"}
 r=requests.get(f"{BASE}/{report}",params=params,timeout=60,headers={"User-Agent":"BP-Sports-Research/1.0"});r.raise_for_status();return r.json().get("data",[])

def main():
 ap=argparse.ArgumentParser();ap.add_argument("seasons",nargs="+");ap.add_argument("--out-dir",default="runtime/nhl/team_game_stats");ap.add_argument("--schema-out",default="research/nhl/results/team_stats_schema.json");a=ap.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);schemas={}
 for s in a.seasons:
  for report in REPORTS:
   rows=fetch(report,s);df=pd.DataFrame(rows);dest=out/f"{report}_{s}.csv";df.to_csv(dest,index=False);schemas[f"{report}_{s}"]={"rows":int(len(df)),"columns":list(df.columns)};print(s,report,len(df),list(df.columns))
 Path(a.schema_out).parent.mkdir(parents=True,exist_ok=True);Path(a.schema_out).write_text(json.dumps(schemas,indent=2)+"\n")
if __name__=="__main__":main()
