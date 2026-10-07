"""Build presentation-only pregame context without loading or changing any model."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import io,json,sys
from pathlib import Path
import pandas as pd
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from preview_data import football_games,nhl_games,nba_games,profile,game_id,stamp,team,flag

ROOT=Path(__file__).resolve().parents[1]
RAW='https://raw.githubusercontent.com/bp111301/bp-sports/'
CFB='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_schedules/cfb_schedules_2026.csv.gz'
NFL='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'

def get(url):
    r=requests.get(url,timeout=20,headers={'User-Agent':'BP-Sports-Matchup-Preview/1.0'});r.raise_for_status();return r

def target(sport,r):
    capture=r.get('snapshot_created_utc',r.get('created_at_utc',r.get('captured_at_utc')))
    return dict(sport=sport,game_id=game_id(r['game_id']),home_team=str(r['home_team']),away_team=str(r['away_team']),cutoff_utc=stamp(capture).isoformat(),start_time_utc=r.get('kickoff_utc',r.get('start_time_utc')))

def collect_targets():
    rows=[];errors=[]
    for sport,path in [('NFL','data/current/website_feed.csv'),('CFB','data/cfb/current/predictions.csv')]:
        rows.extend(target(sport,r) for r in pd.read_csv(ROOT/path).to_dict('records'))
    for sport,branch,path in [('NHL','nhl-v1-research','data/nhl/v2_research/prediction_ledger.csv'),('NBA','nba-v1-research','data/nba/prospective/dashboard.json')]:
        try:
            response=get(RAW+branch+'/'+path)
            if sport=='NHL':data=pd.read_csv(io.StringIO(response.text)).query("candidate == 'reference_control'").to_dict('records')
            else:
                feed=response.json();data=[r for r in feed.get('predictions',[]) if r.get('season_type')==2] if feed.get('feed_status')=='enabled' else []
            rows.extend(target(sport,r) for r in data)
        except Exception as e:errors.append(f'{sport} prediction context unavailable: {type(e).__name__}')
    return rows,errors

def build():
    path=ROOT/'data/matchup_previews.json';old=json.loads(path.read_text()) if path.exists() else {};saved=old.get('games',{});targets,errors=collect_targets();hist={};meta={};sources={};counts={}
    try:
        frame=pd.read_csv(io.StringIO(get(NFL).text));frame=frame[frame.season.eq(2026)];hist['NFL']=football_games(frame,'NFL');sources['NFL']=[dict(name='nflverse schedule',url=NFL)]
        for r in frame.to_dict('records'):
            if pd.isna(r.get('gametime')):continue
            start=pd.Timestamp(str(r['gameday'])+' '+str(r['gametime'])).tz_localize('America/New_York').tz_convert('UTC')
            meta['NFL:'+str(r['game_id'])]=dict(home_team=r['home_team'],away_team=r['away_team'],start_time_utc=start.isoformat(),venue=None if pd.isna(r.get('stadium')) else r['stadium'],neutral_site=r.get('location')!='Home')
    except Exception as e:errors.append('NFL recent results unavailable: '+type(e).__name__)
    try:
        frame=pd.read_csv(io.BytesIO(get(CFB).content),compression='gzip');hist['CFB']=football_games(frame,'CFB');sources['CFB']=[dict(name='SportsDataverse schedule',url=CFB)]
        for r in frame.to_dict('records'):meta['CFB:'+game_id(r['game_id'])]=dict(home_team=r['home_team'],away_team=r['away_team'],start_time_utc=r['start_date'],venue=None if pd.isna(r.get('venue')) else r['venue'],neutral_site=flag(r.get('neutral_site')))
    except Exception as e:errors.append('CFB recent results unavailable: '+type(e).__name__)
    clubs=sorted({name for r in targets if r['sport']=='NHL' for name in [r['home_team'],r['away_team']]})
    def club(name):
        url=f'https://api-web.nhle.com/v1/club-schedule-season/{name}/20262027'
        try:return name,nhl_games(get(url).json()),url,None
        except Exception as e:return name,[],url,type(e).__name__
    nhl={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name,games,url,error in pool.map(club,clubs):
            if error:errors.append(f'NHL {name} recent results unavailable: {error}')
            else:nhl[name]=(games,url)
    nba={};nba_targets=[r for r in targets if r['sport']=='NBA']
    if nba_targets:
        try:
            payload=get('https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=100').json();lookup={team('NBA',v['team']['abbreviation']):v['team']['id'] for v in payload['sports'][0]['leagues'][0]['teams']}
            for name in sorted({team('NBA',n) for r in nba_targets for n in [r['home_team'],r['away_team']]}):
                url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{lookup[name]}/schedule?season=2027&seasontype=2'
                nba[name]=(nba_games(get(url).json()),url)
        except Exception as e:errors.append('NBA recent results unavailable: '+type(e).__name__)
    for r in targets:
        key=r['sport']+':'+r['game_id'];sport=r['sport'];old_record=saved.get(key)
        if old_record and old_record['cutoff_utc']==r['cutoff_utc']:continue
        details=meta.get(key,{})
        if details and any(team(sport,details[side])!=team(sport,r[side]) for side in ['home_team','away_team']):errors.append(key+' team identity mismatch');continue
        if sport=='NFL':r['start_time_utc']=details.get('start_time_utc')
        start=stamp(r['start_time_utc']);cutoff=stamp(r['cutoff_utc'])
        if pd.isna(start) or pd.isna(cutoff) or cutoff>=start:continue
        try:
            if sport in ('NFL','CFB'):games=hist[sport];refs=sources[sport]
            else:
                lookup=nhl if sport=='NHL' else nba
                home=lookup[team(sport,r['home_team'])];away=lookup[team(sport,r['away_team'])];games=home[0]+away[0];refs=[dict(name=r[side]+' schedule',url=lookup[team(sport,r[side])][1]) for side in ['home_team','away_team']]
            saved[key]={**r,'start_time_utc':start.isoformat(),'venue':details.get('venue'),'neutral_site':details.get('neutral_site',False),'home_form':profile(games,sport,r['home_team'],cutoff,start),'away_form':profile(games,sport,r['away_team'],cutoff,start),'sources':refs}
            counts[sport]=counts.get(sport,0)+1
        except (KeyError,ValueError,TypeError) as e:errors.append(key+' preview unavailable: '+type(e).__name__)
    result=dict(updated_at_utc=datetime.now(timezone.utc).isoformat(),purpose='Presentation-only recent results; forecasts and weights unchanged',games=saved,errors=errors)
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(new_previews=counts,total_previews=len(saved),errors=errors),indent=2))
if __name__=='__main__':build()
