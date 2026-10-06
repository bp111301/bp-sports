"""Download per-game NHL goalie summaries for leakage-safe goalie research."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd,requests

URL="https://api.nhle.com/stats/rest/en/goalie/summary"

def fetch(season):
 params={
  "isAggregate":"false","isGame":"true","start":0,"limit":-1,
  "factCayenneExp":"gamesPlayed>=1",
  "cayenneExp":f"seasonId={season} and gameTypeId=2",
 }
 r=requests.get(URL,params=params,timeout=90,headers={"User-Agent":"BP-Sports-Research/1.0"});r.raise_for_status()
 return r.json().get("data",[])

def main():
 ap=argparse.ArgumentParser();ap.add_argument("seasons",nargs="+");ap.add_argument("--out-dir",default="runtime/nhl/goalie_game_stats");ap.add_argument("--schema-out",default="research/nhl/results/goalie_stats_schema.json");a=ap.parse_args()
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);schema={}
 for s in a.seasons:
  rows=fetch(s);df=pd.DataFrame(rows);df.to_csv(out/f"goalie_summary_{s}.csv",index=False);schema[str(s)]={"rows":int(len(df)),"columns":list(df.columns)};print(s,len(df),list(df.columns))
 Path(a.schema_out).parent.mkdir(parents=True,exist_ok=True);Path(a.schema_out).write_text(json.dumps(schema,indent=2)+"\n")
if __name__=="__main__":main()
