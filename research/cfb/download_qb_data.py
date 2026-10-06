"""Download compact game-level CFB advanced passing data."""
from __future__ import annotations
import argparse
from pathlib import Path
from urllib.request import urlretrieve
BASE="https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_adv_passing"
def download(season:int,out_dir:Path,force:bool=False):
    out_dir.mkdir(parents=True,exist_ok=True); dest=out_dir/f"adv_passing_{season}.csv"
    if dest.exists() and not force: print(f"exists: {dest}"); return dest
    url=f"{BASE}/adv_passing_{season}.csv"; print(f"downloading QB data {season}"); urlretrieve(url,dest); return dest
def main():
    p=argparse.ArgumentParser(); p.add_argument("seasons",nargs="*",type=int,default=list(range(2015,2027))); p.add_argument("--out-dir",default="runtime/cfb/adv_passing"); p.add_argument("--force",action="store_true"); a=p.parse_args()
    for s in a.seasons: download(s,Path(a.out_dir),a.force)
if __name__=="__main__": main()
