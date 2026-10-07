"""Refresh score/status context only. No model imports, forecasts, grading or history writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import io,json,sys
from pathlib import Path
import pandas as pd
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from game_status import espn_game,nhl_game,matches
from preview_data import game_id,stamp,team
ROOT=Path(__file__).resolve().parents[1]
RAW='https://raw.githubusercontent.com/bp111301/bp-sports/'

def get(url):
    r=requests.get(url,timeout=25,headers={'User-Agent':'BP-Sports-Game-Status/1.0'});r.raise_for_status();return r

def targets():
    rows=[];errors=[]
    previews=json.loads((ROOT/'data/matchup_previews.json').read_text()).get('games',{})
    for sport,path in [('NFL','data/ledger/prediction_ledger.csv'),('CFB','data/cfb/ledger/prediction_ledger.csv')]:
        for r in pd.read_csv(ROOT/path).drop_duplicates('game_id').to_dict('records'):
            key=sport+':'+game_id(r['game_id']);start=r.get('schedule_kickoff_utc',r.get('kickoff_utc'))
            if pd.isna(start):start=r.get('kickoff_utc')
            if sport=='NFL':start=previews.get(key,{}).get('start_time_utc')
            rows.append(dict(sport=sport,game_id=game_id(r['game_id']),home_team=r['home_team'],away_team=r['away_team'],start_time_utc=start))
    for sport,branch,path in [('NHL','nhl-v1-research','data/nhl/v2_research/prediction_ledger.csv'),('NBA','nba-v1-research','data/nba/prospective/dashboard.json')]:
        try:
            response=get(RAW+branch+'/'+path)
            if sport=='NHL':data=pd.read_csv(io.StringIO(response.text)).drop_duplicates('game_id').to_dict('records')
            else:
                feed=response.json();data=[r for r in feed.get('predictions',[]) if r.get('season_type')==2] if feed.get('feed_status')=='enabled' else []
            rows.extend({**r,'sport':sport,'game_id':game_id(r['game_id'])} for r in data)
        except Exception as e:errors.append(sport+' forecast list unavailable: '+type(e).__name__)
    return rows,errors

def build():
    now=pd.Timestamp.now(tz='UTC');checked=now.isoformat();path=ROOT/'data/game_status.json';old=json.loads(path.read_text()) if path.exists() else {};saved=old.get('games',{});rows,errors=targets();work=[]
    for r in rows:
        key=r['sport']+':'+r['game_id'];cached=saved.get(key)
        if matches(cached,r['sport'],r['home_team'],r['away_team']) and cached['state']=='final':continue
        if pd.notna(stamp(r['start_time_utc'])):work.append(r)
    def fetch(item):
        sport,day=item;league={'NFL':'football/nfl','CFB':'football/college-football','NBA':'basketball/nba'}[sport]
        url=f'https://site.api.espn.com/apis/site/v2/sports/{league}/scoreboard?dates={day}&limit=1000'+('&groups=80' if sport=='CFB' else '')
        try:return sport,[g for e in get(url).json().get('events',[]) if (g:=espn_game(sport,e,checked))],None
        except Exception as e:return sport,[],sport+' '+day+' status unavailable: '+type(e).__name__
    dates=sorted({(r['sport'],stamp(r['start_time_utc']).tz_convert('America/New_York').strftime('%Y%m%d')) for r in work if r['sport']!='NHL'})
    fresh={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for sport,games,error in pool.map(fetch,dates):
            if error:errors.append(error)
            for g in games:fresh[sport+':'+g['game_id']]=g
    def hockey(r):
        try:return nhl_game(get(f'https://api-web.nhle.com/v1/gamecenter/{r["game_id"]}/boxscore').json(),checked),None
        except Exception as e:return None,'NHL '+r['game_id']+' status unavailable: '+type(e).__name__
    with ThreadPoolExecutor(max_workers=8) as pool:
        for g,error in pool.map(hockey,[r for r in work if r['sport']=='NHL']):
            if error:errors.append(error)
            if g:fresh['NHL:'+g['game_id']]=g
    # Daily scoreboards can omit unranked or distant scheduled games. Resolve missing IDs directly.
    def detail(r):
        league={'CFB':'football/college-football','NBA':'basketball/nba'}[r['sport']]
        try:
            header=get(f'https://site.api.espn.com/apis/site/v2/sports/{league}/summary?event={r["game_id"]}').json().get('header',{})
            return espn_game(r['sport'],header,checked),None
        except Exception as e:return None,r['sport']+' '+r['game_id']+' detail unavailable: '+type(e).__name__
    missing=[r for r in work if r['sport'] in ('CFB','NBA') and r['sport']+':'+r['game_id'] not in fresh]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for g,error in pool.map(detail,missing):
            if error:errors.append(error)
            if g:fresh[g['sport']+':'+g['game_id']]=g
    for r in work:
        key=r['sport']+':'+r['game_id']
        if r['sport']=='NFL':
            candidates=[g for g in fresh.values() if matches(g,'NFL',r['home_team'],r['away_team']) and stamp(g['start_time_utc']).tz_convert('America/New_York').date()==stamp(r['start_time_utc']).tz_convert('America/New_York').date()]
            g=candidates[0] if len(candidates)==1 else None
        else:g=fresh.get(key)
        if matches(g,r['sport'],r['home_team'],r['away_team']):saved[key]={**g,'game_id':r['game_id']}
        else:errors.append(key+' no verified regular-season status')
    path.write_text(json.dumps(dict(updated_at_utc=checked,purpose='Presentation-only scores; saved probabilities and grading unchanged',games=saved,errors=errors),indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(games=len(saved),errors=errors),indent=2))
if __name__=='__main__':build()
