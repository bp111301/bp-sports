"""NFL capture coverage and actual kickoff windows; standard-library only."""
import argparse
import csv
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

URL='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
EARLY_HOURS=72
REFRESH_HOURS=24


def timestamp(value):
    try:
        result=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError,TypeError):return None


def truth(value):return str(value).lower() in ('true','1','1.0','yes')


def season_for(now):
    local=now.astimezone(ZoneInfo('America/Chicago'))
    return local.year if local.month>=9 else local.year-1


def future_games(rows,now):
    games=[]
    for row in rows:
        if str(row.get('season'))!=str(season_for(now)) or row.get('game_type')!='REG':continue
        if str(row.get('home_score','')).strip() or str(row.get('away_score','')).strip():continue
        try:
            start=datetime.fromisoformat(row['gameday']+'T'+row['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
        except (ValueError,KeyError,TypeError):continue
        if start>now:games.append({**row,'start':start})
    return games


def capture_health(rows,forecasts,now,metadata=None,availability=None):
    games=future_games(rows,now)
    if games:
        week=min(int(g['week']) for g in games)
        games=[g for g in games if int(g['week'])==week]
    else:week=None
    latest={}
    for forecast in forecasts:
        captured=timestamp(forecast.get('captured_at_utc'))
        if not captured or captured>now or truth(forecast.get('qb_input_review_required')):continue
        gid=forecast.get('game_id')
        if gid not in latest or captured>latest[gid][0]:latest[gid]=(captured,forecast)
    missing=[];stale=[];blocked=[];captures=[];warnings={}
    for game in games:
        gid=game.get('game_id');saved=latest.get(gid)
        report=(availability or {}).get('games',{}).get(gid,{})
        issues=list(report.get('source_errors',[]))
        if not report:issues.append('availability_not_checked')
        elif any(report.get(side,{}).get('qb_evidence_state')!='confirmed' for side in ['home','away']):issues.append('starter_unconfirmed')
        if issues:warnings[gid]=issues
        if (report.get('home_team'),report.get('away_team'))==(game.get('home_team'),game.get('away_team')) and report.get('qb_review_required'):
            blocked.append(gid)
        if not saved:
            missing.append(gid);continue
        captured,forecast=saved
        saved_start=timestamp(forecast.get('kickoff_utc'))
        valid=(captured<game['start'] and (saved_start is None or saved_start==game['start'])
               and forecast.get('home_team')==game.get('home_team') and forecast.get('away_team')==game.get('away_team')
               and forecast.get('v4_pick') in (game.get('home_team'),game.get('away_team')))
        try:valid=valid and .5<=float(forecast.get('v4_adjusted_confidence'))<=1
        except (ValueError,TypeError):valid=False
        if not valid:missing.append(gid);continue
        captures.append(captured)
        limit=timedelta(minutes=35) if game['start']-now<=timedelta(minutes=100) else timedelta(hours=REFRESH_HOURS)
        if now-captured>limit:stale.append(gid)
    opens=bool(games and min(g['start'] for g in games)-now<=timedelta(hours=EARLY_HOURS))
    status='idle' if not games else 'outside_capture_window' if not opens else 'blocked' if blocked else 'missing' if missing else 'stale' if stale else 'ready'
    reason=None
    if opens and blocked:reason='QB input review required: '+', '.join(sorted(blocked))
    elif opens and missing:reason='Missing upcoming forecasts: '+', '.join(sorted(missing))
    elif opens and stale:reason='Upcoming forecasts need refresh: '+', '.join(sorted(stale))
    return {'checked_at_utc':now.isoformat(),'season':season_for(now),'week':week,'status':status,
            'capture_window_open':opens,'expected_games':len(games),'covered_games':len(games)-len(missing),
            'first_kickoff_utc':min((g['start'] for g in games),default=now).isoformat() if games else None,
            'missing_upcoming_game_ids':sorted(missing),'stale_upcoming_game_ids':sorted(stale),
            'blocked_upcoming_game_ids':sorted(blocked),'capture_blocked_reason':reason,
            'availability_warnings':warnings,
            'last_forecast_at_utc':max(captures).isoformat() if captures else None,
            'last_build_completed_at_utc':(metadata or {}).get('captured_at_utc')}


def run_reason(rows,now,force=False,forecasts=None,metadata=None):
    if force:return 'explicit_refresh'
    local=now.astimezone(ZoneInfo('America/Chicago'))
    if local.hour==8 and local.weekday() in (3,6):return 'morning_refresh'
    if any(g['start']-now<=timedelta(minutes=100) for g in future_games(rows,now)):return 'pregame_window'
    if forecasts is not None:
        health=capture_health(rows,forecasts,now,metadata)
        built=timestamp((metadata or {}).get('captured_at_utc'))
        cooldown=built is not None and timedelta(0)<=now-built<timedelta(hours=1)
        if health['capture_window_open'] and (health['missing_upcoming_game_ids'] or health['stale_upcoming_game_ids']) and not cooldown:
            return 'early_slate_coverage'
    return None


def should_run(rows,now,force=False,forecasts=None,metadata=None):
    return bool(run_reason(rows,now,force,forecasts,metadata))


def read_text(url):
    with urlopen(Request(url,headers={'User-Agent':'BP-Sports-Capture/1.0'}),timeout=30) as response:
        raw=response.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:raise ValueError('Capture input exceeds size limit')
        return raw.decode()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--force',action='store_true');parser.add_argument('--due-only',action='store_true')
    parser.add_argument('--remote',action='store_true');parser.add_argument('--health-only',action='store_true')
    parser.add_argument('--schedule',type=Path);parser.add_argument('--ledger',type=Path,default=Path('data/ledger/prediction_ledger.csv'))
    parser.add_argument('--metadata',type=Path,default=Path('data/current/prediction_metadata.json'))
    parser.add_argument('--availability',type=Path,default=Path('data/current/nfl_availability.json'))
    parser.add_argument('--health-output',type=Path);parser.add_argument('--fail-on-gaps',action='store_true')
    parser.add_argument('--update-metadata',action='store_true');args=parser.parse_args()
    now=datetime.now(timezone.utc)
    raw=args.schedule.read_text() if args.schedule else read_text(URL)
    rows=list(csv.DictReader(io.StringIO(raw)))
    if args.remote:
        base='https://raw.githubusercontent.com/'+os.environ.get('GITHUB_REPOSITORY','bp111301/bp-sports')+'/main/'
        forecasts=list(csv.DictReader(io.StringIO(read_text(base+args.ledger.as_posix()))))
        metadata=json.loads(read_text(base+args.metadata.as_posix()))
    else:
        forecasts=list(csv.DictReader(io.StringIO(args.ledger.read_text()))) if args.ledger.exists() else []
        metadata=json.loads(args.metadata.read_text()) if args.metadata.exists() else {}
    availability=json.loads(args.availability.read_text()) if args.availability.exists() else {}
    health=capture_health(rows,forecasts,now,metadata,availability)
    reason=run_reason(rows,now,args.force,forecasts,metadata)
    health['generation_requested']=bool(reason);health['generation_reason']=reason
    if args.health_output:
        args.health_output.parent.mkdir(parents=True,exist_ok=True)
        args.health_output.write_text(json.dumps(health,indent=2)+'\n')
    if args.update_metadata:
        metadata.update(nfl_capture_health=health,
                        missing_upcoming_game_ids=health['missing_upcoming_game_ids'] if health['capture_window_open'] else [],
                        capture_blocked_reason=health['capture_blocked_reason'])
        args.metadata.write_text(json.dumps(metadata,indent=2)+'\n')
    if args.due_only:
        if reason:print(reason)
    elif args.health_only:print(json.dumps(health,indent=2))
    else:
        print('run='+str(bool(reason)).lower());print('season='+str(season_for(now)))
        print('reason='+(reason or 'not_due'))
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary and not args.due_only:
        with open(summary,'a') as file:
            file.write('\nNFL forecast coverage: '+health['status']+'; '+str(health['covered_games'])+'/'+str(health['expected_games'])+' games.\n')
            file.write('Generation: '+(reason or 'skipped; no generation requested')+'. Last actual saved forecast: '+str(health['last_forecast_at_utc'])+'.\n')
            if health['capture_blocked_reason']:file.write(health['capture_blocked_reason']+'\n')
            if health['availability_warnings']:file.write('Availability evidence remains incomplete for '+str(len(health['availability_warnings']))+' games; coverage ready does not mean starters confirmed.\n')
    if args.fail_on_gaps and health['capture_blocked_reason']:
        raise SystemExit('::error::'+health['capture_blocked_reason'])


if __name__=='__main__':main()
