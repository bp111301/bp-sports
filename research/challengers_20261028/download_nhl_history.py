"""Download official per-game reports; keep all raw source receipts."""
import concurrent.futures,json,hashlib,io
from pathlib import Path
from urllib.parse import urlencode
import pandas as pd
from download_history import fetch,ROOT

def download(item):
    season,report=item
    url='https://api.nhle.com/stats/rest/en/team/'+report+'?'+urlencode({'isAggregate':'false','isGame':'true','start':0,'limit':-1,'factCayenneExp':'gamesPlayed>=1','cayenneExp':f'seasonId={season} and gameTypeId=2'})
    raw=fetch(url);j=json.loads(raw);rows=j.get('data',[])
    if not rows:raise ValueError('Empty official team report '+str(item))
    d=pd.DataFrame(rows)
    if d.duplicated(['gameId','teamId']).any():raise ValueError('Duplicate team-game rows')
    p=ROOT/'runtime/challengers_20261028/nhl/team_game_stats'/f'{report}_{season}.csv';p.parent.mkdir(parents=True,exist_ok=True);d.to_csv(p,index=False)
    return dict(path=str(p.relative_to(ROOT)),url=url,sha256=hashlib.sha256(raw).hexdigest(),rows=len(d))
def main():
    seasons=[str(y)+str(y+1) for y in range(2018,2026)]
    receipts=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for r in pool.map(download,[(s,r) for s in seasons for r in ['summary','powerplay','penaltykill']]):receipts.append(r);print(r['path'],r['rows'],flush=True)
    (ROOT/'runtime/challengers_20261028/nhl/source_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    s=pd.read_csv(ROOT/'runtime/challengers_20261028/nhl/team_game_stats/summary_20182019.csv');print('SUMMARY SAMPLE',s.iloc[0].to_json(),flush=True)
if __name__=='__main__':main()
