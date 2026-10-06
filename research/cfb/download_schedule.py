"""Download unified ESPN CFB schedule with exact kickoff instants."""
from pathlib import Path
from urllib.request import urlretrieve
import argparse
BASE="https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_schedules"
def main():
    p=argparse.ArgumentParser();p.add_argument("season",type=int,default=2026,nargs="?");p.add_argument("--out-dir",default="runtime/cfb/schedules");a=p.parse_args()
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);dest=out/f"cfb_schedules_{a.season}.csv.gz"
    url=f"{BASE}/cfb_schedules_{a.season}.csv.gz";print(f"downloading exact schedule {a.season}");urlretrieve(url,dest);print(dest)
if __name__=="__main__":main()
