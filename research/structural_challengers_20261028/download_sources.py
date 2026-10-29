"""Acquire only registered structural development seasons and retain receipts."""
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research/challengers_20261028'))
import download_history as cfb
import download_nhl_history as nhl

def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        cfb_receipts=list(pool.map(cfb.cfb,range(2015,2026)))
        nhl_receipts=list(pool.map(nhl.download,[(str(y)+str(y+1),report) for y in range(2018,2025) for report in ['summary','powerplay','penaltykill']]))
    out=ROOT/'runtime/structural_challengers_20261028';out.mkdir(parents=True,exist_ok=True)
    (out/'source_receipts.json').write_text(json.dumps({'cfb':cfb_receipts,'nhl':nhl_receipts},indent=2)+'\n')
    print('Downloaded CFB2015–2025 and NHL2018–19–2024–25 only; live labels excluded.')
if __name__=='__main__':main()
