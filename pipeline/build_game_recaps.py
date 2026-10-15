"""Cache sourced final-game facts separately from forecasts and evaluation."""
from concurrent.futures import ThreadPoolExecutor
import json,re,sys
from pathlib import Path
import pandas as pd
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recap_data import espn_recap,nhl_recap
ROOT=Path(__file__).resolve().parents[1]

def get(url):
    r=requests.get(url,timeout=20,headers={'User-Agent':'BP-Sports-Recaps/1.0'});r.raise_for_status();return r.json()

def build():
    path=ROOT/'data/game_recaps.json';old=json.loads(path.read_text()) if path.exists() else {}
    saved=old.get('games',{});scores=json.loads((ROOT/'data/game_status.json').read_text()).get('games',{})
    now=pd.Timestamp.now(tz='UTC');checked=now.isoformat();work=[]
    for key,r in scores.items():
        if r.get('state')!='final' or r.get('sport') not in ('NFL','CFB','NHL','NBA'):continue
        prior=saved.get(key)
        if prior and prior.get('version')==2 and prior.get('detailed') and all(prior.get(k)==r.get(k) for k in ('home_score','away_score','home_team','away_team','start_time_utc')):continue
        work.append((key,r))
    def fetch(item):
        key,r=item;sport=r['sport'];error=None
        try:
            if sport=='NHL':
                box=get(f'https://api-web.nhle.com/v1/gamecenter/{r["game_id"]}/boxscore')
                try:landing=get(f'https://api-web.nhle.com/v1/gamecenter/{r["game_id"]}/landing')
                except (requests.RequestException,ValueError):landing={}
                recap=nhl_recap(box,r,checked,landing)
            else:
                event=re.search(r'/gameId/(\d+)',r.get('source_url',''))
                if not event:raise ValueError('Missing source event ID')
                league={'NFL':'football/nfl','CFB':'football/college-football','NBA':'basketball/nba'}[sport]
                recap=espn_recap(sport,get(f'https://site.api.espn.com/apis/site/v2/sports/{league}/summary?event={event[1]}'),r,checked)
            if recap is None:raise ValueError('Final or team identity did not match score feed')
        except (requests.RequestException,ValueError,KeyError,TypeError,IndexError) as e:
            error=key+' detailed recap unavailable: '+type(e).__name__
            recap={**r,'checked_at_utc':checked,'facts':[],'leaders':[],'flow':None,'finish':'Final','detailed':False,
                   'sources':[{'name':'Verified score source','url':r['source_url']}]}
        return key,recap,error
    errors=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for key,r,error in pool.map(fetch,work):
            if error:errors.append(error)
            # Preserve an earlier detailed recap during a transient provider failure.
            if not saved.get(key,{}).get('detailed') or r.get('detailed'):saved[key]=r
    path.write_text(json.dumps({'updated_at_utc':checked,'purpose':'Postgame presentation only; no grading or model changes','games':saved,'errors':errors},indent=2,allow_nan=False)+'\n')
    print(json.dumps({'recaps':len(saved),'refreshed':len(work),'errors':errors}))
if __name__=='__main__':build()
