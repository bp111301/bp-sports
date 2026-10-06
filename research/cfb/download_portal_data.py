"""Download SportsDataverse season-level transfer/roster-diff features."""
from __future__ import annotations
import argparse
from pathlib import Path
from urllib.request import urlretrieve
BASE="https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_team_portal"
def main():
 p=argparse.ArgumentParser();p.add_argument("seasons",nargs="*",type=int,default=list(range(2015,2026)));p.add_argument("--out-dir",default="runtime/cfb/team_portal");a=p.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 for s in a.seasons:
  dest=out/f"cfb_team_portal_{s}.parquet"
  if dest.exists():continue
  print(f"downloading portal {s}");urlretrieve(f"{BASE}/cfb_team_portal_{s}.parquet",dest)
if __name__=="__main__":main()
