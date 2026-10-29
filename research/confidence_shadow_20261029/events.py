"""Append-only, digest-checked paired forecast and settlement events."""
import hashlib,json,os
from pathlib import Path
import pandas as pd

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def stamp(x):
 t=pd.to_datetime(x,utc=True,errors='coerce')
 if t is None or pd.isna(t):raise ValueError('Invalid timestamp')
 return t

def read_events(path,key):
 p=Path(path);events={}
 if not p.exists():return events
 for line in p.read_text().splitlines():
  item=json.loads(line);saved=item.pop('event_sha256')
  if digest(item)!=saved or item[key] in events:raise ValueError('Existing event integrity failure')
  events[item[key]]={**item,'event_sha256':saved}
 return events

def append(path,records,key):
 known=read_events(path,key);add=[]
 for raw in records:
  item=dict(raw);item.pop('event_sha256',None);ident=item[key]
  if ident in known:
   old=dict(known[ident]);old.pop('event_sha256')
   if canonical(old)!=canonical(item):raise ValueError('Cannot rewrite an immutable event')
   continue
  item={**item,'event_sha256':digest(item)};known[ident]=item;add.append(item)
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('a') as f:
  for item in add:f.write(canonical(item)+'\n')
  f.flush();os.fsync(f.fileno())
 return len(add)

def validate_forecast(r,now):
 captured=stamp(r['captured_at_utc']);start=stamp(r['start_time_utc']);snapshot=stamp(r['input_snapshot_at_utc']);now=stamp(now)
 if not snapshot<=captured<=now<start:raise ValueError('Forecast must be newly observed before exact start')
 if start-captured<pd.Timedelta(minutes=10):raise ValueError('Insufficient time to publish a pregame receipt')
 if (captured-snapshot)>pd.Timedelta(minutes=15):raise ValueError('Input snapshot became stale before capture')
 if r['sport'] not in ['cfb','nhl'] or r['game_state'] not in ['FUT','PRE','STATUS_SCHEDULED']:raise ValueError('Unsupported pregame state')
 p=float(r['reference_home_win_prob']);q=float(r['challenger_home_win_prob'])
 if not 0<=p<=1 or not 0<=q<=1 or (p>=.5)!=(q>=.5):raise ValueError('Invalid probability or changed original pick')
 if int(r['home_id'])==int(r['away_id']):raise ValueError('Invalid team identity')
 for f in ['reference_bundle_sha256','challenger_bundle_sha256','input_snapshot_sha256']:
  value=r[f]
  if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid provenance hash')
 return r

def settlement(forecast,official,observed_at):
 now=stamp(observed_at)
 if official['state'] not in ['OFF','FINAL','STATUS_FINAL']:raise ValueError('Official final required')
 if int(official['game_id'])!=int(forecast['game_id']) or int(official['home_id'])!=int(forecast['home_id']) or int(official['away_id'])!=int(forecast['away_id']):raise ValueError('Official settlement identity mismatch')
 if stamp(official['start_time_utc'])!=stamp(forecast['start_time_utc']):raise ValueError('Scheduled start changed; requires explicit review')
 if not stamp(forecast['captured_at_utc'])<stamp(official['start_time_utc'])<now:raise ValueError('Invalid settlement timing')
 h=float(official['home_score']);a=float(official['away_score'])
 if not h>=0 or not a>=0 or not h.is_integer() or not a.is_integer() or h==a:raise ValueError('Invalid official final score')
 return {'forecast_key':forecast['forecast_key'],'forecast_event_sha256':forecast['event_sha256'],'sport':forecast['sport'],'game_id':forecast['game_id'],'observed_at_utc':now.isoformat(),'actual_home_win':int(h>a),'home_score':int(h),'away_score':int(a),'official_final':official}
