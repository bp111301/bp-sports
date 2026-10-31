"""Live source adapter; frozen experiment helpers remain in collect.py unchanged."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import collect as frozen
from collect import (SEASON, timestamp, digest, goalie_id, schedule_games, source_rows,
                     append_observation, available_at, roster_goalies, request)
from probe_source import page_data

OUT=Path('data/nhl/goalie_capture')

def schedule_time_reconciliation(game,source):
    if any(source[k]!=game[k] for k in ['game_date','home_team','away_team']):
        raise ValueError('Source/schedule mismatch')
    official=timestamp(game['start_time_utc']);reported=timestamp(source['start_time_utc'])
    if official==reported:return None
    # DFO's Nov 1 board is one hour late across the fall-back transition.
    # Accept only this specific clock pattern; NHL time remains the cutoff.
    eastern=ZoneInfo('America/New_York')
    midnight=datetime.fromisoformat(game['game_date']).replace(tzinfo=eastern)
    fallback=midnight.utcoffset()-(midnight+timedelta(days=1)).utcoffset()==timedelta(hours=1)
    if (fallback and official.astimezone(eastern).date()==midnight.date()
            and reported-official==timedelta(hours=1)):
        return 'source_one_hour_late_on_fall_back_day_nhl_time_used'
    raise ValueError('Source/schedule mismatch')

def observation(game,source,side,roster,captured,url,response_hash,snapshot_hash):
    if timestamp(game['start_time_utc'])<=captured:raise ValueError('Post-start capture rejected')
    reconciliation=schedule_time_reconciliation(game,source)
    normalized={**source,'start_time_utc':game['start_time_utc']}
    result=frozen.observation(game,normalized,side,roster,captured,url,response_hash,snapshot_hash)
    if reconciliation:
        result.update(source_start_time_utc=source['start_time_utc'],schedule_time_reconciliation=reconciliation)
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True);now=datetime.now(timezone.utc);day=now.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    schedule_url=f'https://api-web.nhle.com/v1/schedule/{day}'
    schedule_response=request(schedule_url);games=schedule_games(schedule_response.json(),datetime.now(timezone.utc))
    path=OUT/'observations.jsonl';rows=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else [];added=0;errors=[];coverage=[];rosters={};warnings=[]
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
                    if r.get('schedule_time_reconciliation'):
                        warnings.append({'game_id':game['game_id'],'side':side,'warning':r['schedule_time_reconciliation'],'nhl_start_time_utc':r['start_time_utc'],'source_start_time_utc':r['source_start_time_utc']})
                    if append_observation(rows,r):new.append(r);added+=1
                    coverage.append({'game_id':game['game_id'],'side':side,'status':r['status'],'confirmed_eligible':r['confirmed_eligible'],'roster_mapping':r['roster_mapping']})
                except ValueError as e:errors.append({'game_id':game['game_id'],'side':side,'error':str(e)})
        if new:
            snapshots=OUT/'snapshots';snapshots.mkdir(exist_ok=True);(snapshots/f'{snapshot_hash}.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    summary={'as_of_utc':datetime.now(timezone.utc).isoformat(),'status':'collection_only_no_model_changes','new_observations':added,'total_observations':len(rows),'upcoming_schedule_games':len(games),'captured_sides':len(coverage),'eligible_confirmed_sides':sum(r['confirmed_eligible'] for r in coverage),'coverage':coverage,'errors':errors,'schedule_delay_caveat':'Polling can miss late confirmations; availability begins at our capture time, not publication time.'}
    summary['warnings']=warnings
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    if errors:raise SystemExit('Source/mapping/coverage errors recorded; inspect summary before using data')

if __name__=='__main__':main()
