"""Lightweight schedule gate: actual kickoff windows, including international games."""
import argparse,csv,io,urllib.request
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo

URL='https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'

def season_for(now):
    local=now.astimezone(ZoneInfo('America/Chicago'))
    return local.year if local.month>=9 else local.year-1

def should_run(rows,now,force=False):
    if force:return True
    local=now.astimezone(ZoneInfo('America/Chicago'))
    if local.hour==8 and local.weekday() in (3,6):return True
    for row in rows:
        if str(row.get('season'))!=str(season_for(now)) or row.get('game_type')!='REG':continue
        if row.get('home_score') or row.get('away_score'):continue
        try:
            start=datetime.fromisoformat(row['gameday']+'T'+row['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
        except (ValueError,KeyError):continue
        if timedelta(0)<start-now<=timedelta(minutes=100):return True
    return False

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--force',action='store_true');args=parser.parse_args();now=datetime.now(timezone.utc)
    rows=[]
    if not args.force:
        with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'BP-Sports/1.0'}),timeout=30) as response:
            rows=list(csv.DictReader(io.StringIO(response.read().decode())))
    print('run='+str(should_run(rows,now,args.force)).lower());print('season='+str(season_for(now)))

if __name__=='__main__':main()
