"""Build sourced pregame stories; never load a model or write a forecast."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import argparse,io,json,sys,time
from pathlib import Path
import pandas as pd
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from preview_data import football_games,nhl_games,basketball_schedule_games,profile,previous_meetings,game_id,stamp,team,flag

ROOT=Path(__file__).resolve().parents[1]
RAW='https://raw.githubusercontent.com/bp111301/bp-sports/'
CFB='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_schedules/cfb_schedules_2026.csv.gz'
NFL='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
BASKETBALL='https://github.com/sportsdataverse/sportsdataverse-data/releases/download'


def get(url):
    for attempt in range(3):
        try:
            r=requests.get(url,timeout=20,headers={'User-Agent':'BP-Sports-Matchup-Preview/2.0'});r.raise_for_status();return r
        except requests.RequestException as error:
            code=getattr(getattr(error,'response',None),'status_code',None)
            if attempt==2 or (code is not None and code not in (408,429) and code<500):raise
            time.sleep(2**attempt)


def target(sport,r):
    capture=r.get('snapshot_created_utc',r.get('created_at_utc',r.get('captured_at_utc')))
    return dict(sport=sport,game_id=game_id(r['game_id']),home_team=str(r['home_team']),away_team=str(r['away_team']),
                cutoff_utc=stamp(capture).isoformat(),start_time_utc=r.get('kickoff_utc',r.get('start_time_utc')),
                neutral_site=flag(r.get('neutral_site')))


def collect_targets():
    rows=[];errors=[]
    for sport,path in [('NFL','data/current/website_feed.csv'),('CFB','data/cfb/current/predictions.csv')]:
        rows.extend(target(sport,r) for r in pd.read_csv(ROOT/path).to_dict('records'))
    for sport,branch,path in [('NHL','nhl-v1-research','data/nhl/v2_research/prediction_ledger.csv'),
                              ('NBA','nba-v1-research','data/nba/prospective/dashboard.json'),
                              ('CBB','cbb-v1-research','data/cbb/prospective/dashboard.json')]:
        try:
            response=get(RAW+branch+'/'+path)
            if sport=='NHL':data=pd.read_csv(io.StringIO(response.text)).query("candidate == 'reference_control'").to_dict('records')
            else:
                feed=response.json();data=[r for r in feed.get('predictions',[]) if r.get('season_type')==2] if feed.get('feed_status') in ('enabled','research_preview') else []
            # CBB publishes a long horizon; prepare stories for games within 3 days.
            if sport=='CBB':
                now=pd.Timestamp.now(tz='UTC')
                data=[r for r in data if now-pd.Timedelta(days=1)<=stamp(r.get('start_time_utc'))<=now+pd.Timedelta(days=3)]
            rows.extend(target(sport,r) for r in data)
        except Exception as error:errors.append(f'{sport} prediction context unavailable: {type(error).__name__}')
    return rows,errors


def build(output=None):
    path=Path(output) if output else ROOT/'data/matchup_previews.json'
    old=json.loads(path.read_text()) if path.exists() else {};saved=old.get('games',{});targets,errors=collect_targets()
    hist={};meetings={};meta={};sources={};counts={}
    try:
        all_seasons=pd.read_csv(io.StringIO(get(NFL).text));frame=all_seasons[all_seasons.season.eq(2026)]
        hist['NFL']=football_games(frame,'NFL');meetings['NFL']=football_games(all_seasons[all_seasons.season.isin([2025,2026])],'NFL')
        sources['NFL']=[dict(name='nflverse regular-season schedules',url=NFL)]
        for r in frame.to_dict('records'):
            if pd.isna(r.get('gametime')):continue
            start=pd.Timestamp(str(r['gameday'])+' '+str(r['gametime'])).tz_localize('America/New_York').tz_convert('UTC')
            meta['NFL:'+str(r['game_id'])]=dict(home_team=r['home_team'],away_team=r['away_team'],start_time_utc=start.isoformat(),venue=None if pd.isna(r.get('stadium')) else r['stadium'],neutral_site=r.get('location')!='Home')
    except Exception as error:errors.append('NFL recent results unavailable: '+type(error).__name__)
    try:
        frame=pd.read_csv(io.BytesIO(get(CFB).content),compression='gzip');frame=frame[pd.to_numeric(frame.season,errors='coerce').eq(2026)]
        hist['CFB']=football_games(frame,'CFB');meetings['CFB']=list(hist['CFB'])
        sources['CFB']=[dict(name='CFB regular-season schedule',url=CFB)]
        for r in frame.to_dict('records'):
            meta['CFB:'+game_id(r['game_id'])]=dict(home_team=r['home_team'],away_team=r['away_team'],start_time_utc=r['start_date'],venue=None if pd.isna(r.get('venue')) else r['venue'],neutral_site=flag(r.get('neutral_site')))
        try:
            prior=CFB.replace('2026','2025');previous=pd.read_csv(io.BytesIO(get(prior).content),compression='gzip')
            meetings['CFB']+=football_games(previous[pd.to_numeric(previous.season,errors='coerce').eq(2025)],'CFB')
            sources['CFB'].append(dict(name='Previous-season meetings',url=prior))
        except requests.RequestException as error:errors.append('CFB previous-season meetings unavailable: '+type(error).__name__)
    except Exception as error:errors.append('CFB recent results unavailable: '+type(error).__name__)
    for sport,family,prefix in [('NBA','nba','nba'),('CBB','mens_college_basketball','mbb')]:
        if not any(r['sport']==sport for r in targets):continue
        url=f'{BASKETBALL}/espn_{family}_schedules/{prefix}_schedule_2027.parquet'
        try:
            frame=pd.read_parquet(io.BytesIO(get(url).content));hist[sport]=basketball_schedule_games(frame,sport,2027);meetings[sport]=list(hist[sport])
            sources[sport]=[dict(name=sport+' regular-season schedule',url=url)]
            try:
                prior=url.replace('_2027.','_2026.');meetings[sport]+=basketball_schedule_games(pd.read_parquet(io.BytesIO(get(prior).content)),sport,2026)
                sources[sport].append(dict(name='Previous-season meetings',url=prior))
            except requests.RequestException as error:errors.append(sport+' previous-season meetings unavailable: '+type(error).__name__)
        except Exception as error:errors.append(sport+' recent results unavailable: '+type(error).__name__)
    clubs=sorted({name for r in targets if r['sport']=='NHL' for name in [r['home_team'],r['away_team']]})
    def club(name):
        url=f'https://api-web.nhle.com/v1/club-schedule-season/{name}/20262027'
        try:return name,nhl_games(get(url).json()),url,None
        except Exception as error:return name,[],url,type(error).__name__
    nhl={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name,games,url,error in pool.map(club,clubs):
            if error:errors.append(f'NHL {name} recent results unavailable: {error}')
            else:nhl[name]=(games,url)
    now=pd.Timestamp.now(tz='UTC')
    for r in targets:
        key=r['sport']+':'+r['game_id'];sport=r['sport'];old_record=saved.get(key)
        existing=old_record if old_record and old_record['cutoff_utc']==r['cutoff_utc'] else None
        details=meta.get(key,{})
        if details and any(team(sport,details[side])!=team(sport,r[side]) for side in ['home_team','away_team']):errors.append(key+' team identity mismatch');continue
        if details:r['start_time_utc']=details.get('start_time_utc',r['start_time_utc'])
        start,cutoff=stamp(r['start_time_utc']),stamp(r['cutoff_utc'])
        if pd.isna(start) or pd.isna(cutoff) or cutoff>=start:continue
        if old_record and start<=now:continue  # Never refresh pregame context with hindsight.
        try:
            if sport=='NHL':
                home=nhl[team(sport,r['home_team'])];away=nhl[team(sport,r['away_team'])];games=home[0]+away[0];meeting_games=games
                refs=[dict(name=r[side]+' schedule',url=nhl[team(sport,r[side])][1]) for side in ['home_team','away_team']]
            else:games=hist[sport];meeting_games=meetings.get(sport,games);refs=sources[sport]
            def context(at):
                return {**r,'schema_version':2,'cutoff_utc':at.isoformat(),'observed_at_utc':now.isoformat(),'start_time_utc':start.isoformat(),
                        'venue':details.get('venue'),'neutral_site':details.get('neutral_site',r.get('neutral_site',False)),
                        'home_form':profile(games,sport,r['home_team'],at,start),'away_form':profile(games,sport,r['away_team'],at,start),
                        'previous_meetings':previous_meetings(meeting_games,sport,r['home_team'],r['away_team'],at,start),'sources':refs}
            original=existing or context(cutoff)
            if now<start:original={**original,'latest_context':context(now)}
            saved[key]=original;counts[sport]=counts.get(sport,0)+1
        except (KeyError,ValueError,TypeError) as error:errors.append(key+' preview unavailable: '+type(error).__name__)
    result=dict(updated_at_utc=datetime.now(timezone.utc).isoformat(),purpose='Presentation-only team form and story context; forecasts and weights unchanged',games=saved,errors=errors)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(new_previews=counts,total_previews=len(saved),errors=errors[:12],error_count=len(errors)),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output');build(parser.parse_args().output)
