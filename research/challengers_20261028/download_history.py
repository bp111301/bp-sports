"""Acquire history only. Training scripts enforce separate selection cutoffs."""
import concurrent.futures,hashlib,json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
def fetch(url):
    error=None
    for attempt in range(3):
        try:
            with urlopen(Request(url,headers={'User-Agent':'BP-Sports-Research/1.0'}),timeout=45) as response:return response.read()
        except Exception as e:error=e;time.sleep(attempt+1)
    raise error
def cfb(season):
    url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_matchup_line/cfb_matchup_line_{season}.csv'
    raw=fetch(url);p=ROOT/'runtime/challengers_20261028/cfb/matchup_line'/f'cfb_matchup_line_{season}.csv';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    return dict(path=str(p.relative_to(ROOT)),url=url,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
def main():
    receipts=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for receipt in pool.map(cfb,range(2015,2026)):receipts.append(receipt);print(receipt['path'],receipt['bytes'],flush=True)
    (ROOT/'runtime/challengers_20261028/cfb_source_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
if __name__=='__main__':main()
