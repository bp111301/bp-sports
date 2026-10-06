"""Refresh current-season nflverse schedule and play-by-play snapshots atomically."""
from __future__ import annotations
import argparse, hashlib, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"

def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent":"bp-sports/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--season',type=int,required=True); p.add_argument('--data-dir',default='data/current')
    a=p.parse_args(); root=Path(a.data_dir); root.mkdir(parents=True,exist_ok=True)
    records=[]
    for name,url in [("schedules.csv",SCHEDULE_URL),(f"play_by_play_{a.season}.csv.gz",PBP_URL.format(season=a.season))]:
        content=download(url); tmp=root/(name+'.partial'); tmp.write_bytes(content); tmp.replace(root/name)
        records.append({'file':name,'source_url':url,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
        print(f"Ready: {name} ({len(content):,} bytes)")
    tmp=root/'manifest.json.partial'; tmp.write_text(json.dumps(records,indent=2)+'\n'); tmp.replace(root/'manifest.json')
if __name__=='__main__': main()
