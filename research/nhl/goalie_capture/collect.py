"""Append point-in-time goalie observations; never infer confirmation from results."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo
from probe_source import page_data

OUT = Path('data/nhl/goalie_capture')
SEASON = 20262027
TEAM_SLUGS = dict(zip(
    ['anaheim-ducks','boston-bruins','buffalo-sabres','calgary-flames','carolina-hurricanes','chicago-blackhawks','colorado-avalanche','columbus-blue-jackets','dallas-stars','detroit-red-wings','edmonton-oilers','florida-panthers','los-angeles-kings','minnesota-wild','montreal-canadiens','nashville-predators','new-jersey-devils','new-york-islanders','new-york-rangers','ottawa-senators','philadelphia-flyers','pittsburgh-penguins','san-jose-sharks','seattle-kraken','st-louis-blues','tampa-bay-lightning','toronto-maple-leafs','utah-mammoth','vancouver-canucks','vegas-golden-knights','washington-capitals','winnipeg-jets'],
    ['ANA','BOS','BUF','CGY','CAR','CHI','COL','CBJ','DAL','DET','EDM','FLA','LAK','MIN','MTL','NSH','NJD','NYI','NYR','OTT','PHI','PIT','SJS','SEA','STL','TBL','TOR','UTA','VAN','VGK','WSH','WPG']))

def timestamp(value):
    dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('Timezone missing')
    return dt.astimezone(timezone.utc)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def normalize(name):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode().lower())

def goalie_id(name, roster):
    ids={int(g['id']) for g in roster if normalize(g['name'])==normalize(name)}
    return next(iter(ids)) if len(ids)==1 else None

def schedule_games(payload,now):
    result=[]
    for day in payload['gameWeek']:
        for g in day['games']:
            start=timestamp(g['startTimeUTC'])
            if g['gameType']!=2 or int(g['season'])!=SEASON or g['gameState'] not in ['FUT','PRE'] or not now<start<=now+timedelta(hours=36):continue
            result.append({'game_id':int(g['id']),'season':SEASON,'game_date':g.get('gameDate',day['date']),'start_time_utc':start.isoformat(),
                'home_team':g['homeTeam']['abbrev'],'away_team':g['awayTeam']['abbrev'],'home_id':int(g['homeTeam']['id']),'away_id':int(g['awayTeam']['id'])})
    if len({g['game_id'] for g in result})!=len(result):raise ValueError('Duplicate NHL game ID')
    return result

def source_rows(props,day):
    if props.get('date')!=day or not isinstance(props.get('data'),list):raise ValueError('Wrong source date or unsupported schema')
    result=[]
    for g in props['data']:
        row={'game_date':g['date'],'start_time_utc':g['dateGmt'],'home_team':TEAM_SLUGS.get(g['homeTeamSlug']),'away_team':TEAM_SLUGS.get(g['awayTeamSlug'])}
        for side in ['home','away']:
            row[side]={key:g.get(side+field) for key,field in [('goalie_name','GoalieName'),('source_goalie_id','GoalieId'),('status','NewsStrengthName'),('source_reported_at_utc','NewsCreatedAt'),('report_source_name','NewsSourceName'),('report_source_url','NewsSourceUrl')]}
        result.append(row)
    return result

def observation(game,source,side,roster,captured,url,response_hash,snapshot_hash):
    if timestamp(game['start_time_utc'])<=captured:raise ValueError('Post-start capture rejected')
    if source['game_date']!=game['game_date'] or any(source[k]!=game[k] for k in ['home_team','away_team']) or timestamp(source['start_time_utc'])!=timestamp(game['start_time_utc']):raise ValueError('Source/schedule mismatch')
    s=source[side];name=s['goalie_name'];reported=s['source_reported_at_utc'];status=s['status'] or 'Unknown'
    report_valid=False
    if reported:
        try:report_valid=timestamp(reported)<=captured and timestamp(reported)<timestamp(game['start_time_utc'])
        except ValueError:pass
    player_id=goalie_id(name,roster) if name else None
    eligible=status=='Confirmed' and report_valid and player_id is not None and bool(s['report_source_url'])
    event={'game_id':game['game_id'],'team':game[side+'_team'],'side':side,'goalie_name':name,'nhl_goalie_id':player_id,'source_goalie_id':s['source_goalie_id'],'status':status,'source_reported_at_utc':reported,'report_source_url':s['report_source_url']}
    return {**event,'event_id':digest(event),'observation_id':digest({'event':event,'captured_at_utc':captured.isoformat()}),'season':SEASON,'start_time_utc':game['start_time_utc'],'captured_at_utc':captured.isoformat(),'report_source_name':s['report_source_name'],'page_url':url,'source_response_sha256':response_hash,'snapshot_sha256':snapshot_hash,'report_timestamp_valid':report_valid,'confirmed_eligible':eligible,'roster_mapping':'unique_exact_normalized_name' if player_id else 'unresolved'}

def append_observation(rows,new):
    if timestamp(new['captured_at_utc'])>=timestamp(new['start_time_utc']):return False
    previous=[r for r in rows if r['game_id']==new['game_id'] and r['side']==new['side']]
    if previous and previous[-1]['event_id']==new['event_id']:return False
    rows.append(new);return True

def available_at(rows,game_id,side,cutoff):
    # Most recent observed state wins, including a downgrade or starter change.
    valid=[r for r in rows if r['game_id']==game_id and r['side']==side and timestamp(r['captured_at_utc'])<=cutoff and cutoff<timestamp(r['start_time_utc'])]
    latest=max(valid,key=lambda r:timestamp(r['captured_at_utc'])) if valid else None
    return latest if latest and latest['confirmed_eligible'] else None

def request(url):
    import requests
    response=requests.get(url,timeout=45,headers={'User-Agent':'BP-Sports-Research/1.0'});response.raise_for_status();return response

def roster_goalies(payload):
    return [{'id':int(g['id']),'name':g['firstName']['default']+' '+g['lastName']['default']} for g in payload['goalies']]

def main():
    OUT.mkdir(parents=True,exist_ok=True);now=datetime.now(timezone.utc);day=now.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    schedule_url=f'https://api-web.nhle.com/v1/schedule/{day}'
    schedule_response=request(schedule_url);games=schedule_games(schedule_response.json(),datetime.now(timezone.utc))
    path=OUT/'observations.jsonl';rows=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else [];added=0;errors=[];coverage=[];rosters={}
    for date in sorted({g['game_date'] for g in games}):
        url=f'https://www.dailyfaceoff.com/starting-goalies/{date}'
        try:
            response=request(url);parsed=source_rows(page_data(response.text),date)
        except Exception as e:
            errors.append({'source_url':url,'error':str(e)});continue
        response_hash=hashlib.sha256(response.content).hexdigest()
        date_games=[g for g in games if g['game_date']==date];matches=[]
        for game in date_games:
            found=[s for s in parsed if all(s[k]==game[k] for k in ['game_date','home_team','away_team'])]
            if len(found)!=1:
                errors.append({'game_id':game['game_id'],'error':'Missing/ambiguous source matchup'});continue
            matches.append((game,found[0]))
        for game,_ in matches:
            for side in ['home','away']:
                team=game[side+'_team']
                if team not in rosters:
                    try:rosters[team]=roster_goalies(request(f'https://api-web.nhle.com/v1/roster/{team}/{SEASON}').json())
                    except Exception as e:rosters[team]=[];errors.append({'team':team,'error':'Roster mapping failed: '+str(e)})
        captured=datetime.now(timezone.utc)
        snapshot={'captured_at_utc':captured.isoformat(),'source_url':url,'source_response_sha256':response_hash,'schedule_url':schedule_url,'schedule_response_sha256':hashlib.sha256(schedule_response.content).hexdigest(),'matchups':[{'schedule':g,'source':s} for g,s in matches],'roster_goalies':rosters.copy()}
        snapshot_hash=digest(snapshot);new=[]
        for game,source in matches:
            for side in ['home','away']:
                try:
                    r=observation(game,source,side,rosters[game[side+'_team']],captured,url,response_hash,snapshot_hash)
                    if append_observation(rows,r):new.append(r);added+=1
                    coverage.append({'game_id':game['game_id'],'side':side,'status':r['status'],'confirmed_eligible':r['confirmed_eligible'],'roster_mapping':r['roster_mapping']})
                except ValueError as e:errors.append({'game_id':game['game_id'],'side':side,'error':str(e)})
        if new:
            snapshots=OUT/'snapshots';snapshots.mkdir(exist_ok=True);(snapshots/f'{snapshot_hash}.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    summary={'as_of_utc':datetime.now(timezone.utc).isoformat(),'status':'collection_only_no_model_changes','new_observations':added,'total_observations':len(rows),'upcoming_schedule_games':len(games),'captured_sides':len(coverage),'eligible_confirmed_sides':sum(r['confirmed_eligible'] for r in coverage),'coverage':coverage,'errors':errors,'schedule_delay_caveat':'Polling can miss late confirmations; availability begins at our capture time, not publication time.'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    if errors:raise SystemExit('Source/mapping/coverage errors recorded; inspect summary before using data')

if __name__=='__main__':main()
