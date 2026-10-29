"""Final-fit acquisition;2025–26 is fit-only, never selection/evaluation."""
import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research/challengers_20261028'))
from download_history import fetch
import pandas as pd

def main():
    out=ROOT/'runtime/confidence_projection_20261028/final_nhl_sources';out.mkdir(parents=True,exist_ok=True)
    def one(item):
        season,report=item;p=out/f'{report}_{season}.csv'
        url='https://api.nhle.com/stats/rest/en/team/'+report+'?'+urlencode({'isAggregate':'false','isGame':'true','start':0,'limit':-1,'factCayenneExp':'gamesPlayed>=1','cayenneExp':f'seasonId={season} and gameTypeId=2'})
        earlier=ROOT/'runtime/challengers_20261028/nhl/team_game_stats'/p.name
        receipt={'url':url,'path':str(p.relative_to(ROOT))}
        if season!='20252026':shutil.copyfile(earlier,p)
        else:
            raw=fetch(url);data=json.loads(raw)['data'];df=pd.DataFrame(data)
            if df.empty or df.duplicated(['gameId','teamId']).any():raise ValueError('Invalid final-fit report')
            df.to_csv(p,index=False);receipt['raw_response_sha256']=hashlib.sha256(raw).hexdigest()
        receipt['csv_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();return receipt
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:receipts=list(pool.map(one,[(str(y)+str(y+1),report) for y in range(2018,2026) for report in ['summary','powerplay','penaltykill']]))
    (out.parent/'final_nhl_source_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n');print('Final-fit only sources ready')
if __name__=='__main__':main()
