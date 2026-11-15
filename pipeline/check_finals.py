"""Settlement-only checks. Never create forecasts or load/refit model weights."""
import argparse, csv, hashlib, importlib.util, io, json, math, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from zoneinfo import ZoneInfo
import pandas as pd
import requests

REQUEST_ERRORS=[]
LIFECYCLE=[]
CHECKED_IDS=set()
ACTIVE_PENDING=None

def atomic_text(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.partial');temporary.write_text(text);temporary.replace(path)

def write_json(path,value):
    atomic_text(path,json.dumps(value,indent=2,allow_nan=False)+'\n')

def write_settlements(path,before,after,mutable):
    """Preserve the original CSV forecast cell strings, including legacy precision."""
    locked=[c for c in before if c not in mutable]
    pd.testing.assert_frame_equal(before[locked],after[locked],check_dtype=False)
    with Path(path).open(newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
    if len(rows)!=len(after):raise ValueError('Saved forecast row count changed')
    changed=False
    for row,old,new in zip(rows,before.to_dict('records'),after.to_dict('records')):
        for field in mutable:
            a,b=old[field],new[field]
            if (pd.isna(a) and pd.isna(b)) or a==b:continue
            row[field]='' if pd.isna(b) else str(b)
            changed=True
    if not changed:return
    output=io.StringIO(newline='');writer=csv.DictWriter(output,fieldnames=fields)
    writer.writeheader();writer.writerows(rows);atomic_text(path,output.getvalue())

def fetch_available(fetch,ids):
    """A provider outage for one event must not discard other verified finals."""
    def attempt(gid):
        try:return fetch(gid)
        except requests.RequestException as error:
            REQUEST_ERRORS.append(dict(event_id=str(gid),error=str(error)))
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(result for result in pool.map(attempt,ids) if result is not None)

def get_response(url, timeout=45):
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.HTTPError as error:
            status = error.response.status_code
            if attempt == 2 or not (status in (408, 429) or 500 <= status < 600):
                raise
        except (requests.Timeout, requests.ConnectionError):
            if attempt == 2:
                raise
        sleep(2 ** attempt)


def get(url):
    return get_response(url).json()

def metrics(rows,prob='home_win_prob'):
    if not rows:return dict(games=0,correct=0,accuracy=None,brier=None,log_loss=None)
    y=[int(r['actual_home_win']) for r in rows];p=[float(r[prob]) for r in rows]
    correct=sum((v>=.5)==t for v,t in zip(p,y))
    return dict(games=len(y),correct=correct,accuracy=correct/len(y),brier=sum((v-t)**2 for v,t in zip(p,y))/len(y),log_loss=-sum(t*math.log(max(.001,min(.999,v)))+(1-t)*math.log(max(.001,min(.999,1-v))) for v,t in zip(p,y))/len(y))

def final_valid(p,actual,now,capture='created_at_utc',start='start_time_utc'):
    if not actual or not actual.get('completed'):return False
    if (str(p['home_team']),str(p['away_team']))!=(str(actual['home_team']),str(actual['away_team'])):return False
    captured=pd.to_datetime(p[capture],utc=True,errors='coerce');saved=pd.to_datetime(p[start],utc=True,errors='coerce');kickoff=pd.to_datetime(actual['start_time_utc'],utc=True,errors='coerce')
    if any(pd.isna(v) for v in [captured,saved,kickoff]) or not captured<min(saved,kickoff) or not kickoff<now:return False
    try:h,a=float(actual['home_score']),float(actual['away_score'])
    except (ValueError,TypeError):return False
    return math.isfinite(h) and math.isfinite(a) and min(h,a)>=0 and h.is_integer() and a.is_integer()

def module(path):
    path=Path(path);sys.path.insert(0,str(path.parent));spec=importlib.util.spec_from_file_location(path.stem,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def espn_events(sport,dates):
    url=f'https://site.api.espn.com/apis/site/v2/sports/football/{sport}/scoreboard'
    events={}
    for day in sorted(dates):
        query=f'?dates={day:%Y%m%d}&limit=1000'+('&groups=80' if sport=='college-football' else '')
        try:response=get(url+query)
        except requests.RequestException as error:
            REQUEST_ERRORS.append(dict(source=url+query,error=str(error)));continue
        for e in response.get('events',[]):
            events[str(e['id'])]=e
    return events.values()

def pending_dates(values,now):
    starts=pd.to_datetime(values,utc=True,format='mixed',errors='coerce').dropna()
    return {d for d in starts.dt.tz_convert('America/New_York').dt.date if d<=now.tz_convert('America/New_York').date()}

def cfb_pending_events(pending,now):
    # Scoreboard responses can stop at 25 games even when limit=1000 is requested.
    starts=pending.get('schedule_kickoff_utc',pending.kickoff_utc).fillna(pending.kickoff_utc)
    dates=pending_dates(starts,now)
    events={str(e['id']):e for e in espn_events('college-football',dates)}
    due=pending[pd.to_datetime(starts,utc=True,format='mixed',errors='coerce').le(now)]
    missing=sorted({str(int(g)) for g in due.game_id}-set(events))
    def fetch(gid):
        data=get('https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event='+gid)
        event=data.get('header',{})
        if str(event.get('id'))!=gid:raise ValueError('CFB final event identity mismatch')
        competitions=event.get('competitions',[])
        if len(competitions)!=1 or str(competitions[0].get('id'))!=gid:raise ValueError('CFB final competition identity mismatch')
        return gid,event
    events.update(fetch_available(fetch,missing))
    return events.values()

def cfb(now):
    paths=[Path('data/cfb/ledger/prediction_ledger.csv'),Path('data/cfb/v2_shadow/verified_prediction_ledger.csv')]
    frames=[pd.read_csv(p) for p in paths if p.exists()]
    combined=pd.concat(frames,ignore_index=True)
    pending=combined[combined.correct.isna()]
    # Overlay live ESPN states onto the full schedule so future kickoff metadata remains intact.
    schedule_url='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_schedules/cfb_schedules_2026.csv.gz'
    try:
        response=get_response(schedule_url,timeout=30)
        schedule=pd.read_csv(io.BytesIO(response.content),compression='gzip');index={int(r['game_id']):r for r in schedule.to_dict('records')}
    except requests.RequestException as error:
        REQUEST_ERRORS.append(dict(source=schedule_url,error=str(error)))
        # Saved identities are sufficient for official per-event lookup. Nothing
        # in this fallback is final until ESPN verifies that event and its teams.
        index={int(r['game_id']):dict(game_id=int(r['game_id']),home_team=r['home_team'],away_team=r['away_team'],
               start_date=r.get('schedule_kickoff_utc',r['kickoff_utc']),completed=False,start_time_tbd=True)
               for r in combined.to_dict('records')}
    for e in cfb_pending_events(pending,now):
        c=e['competitions'][0];t={x['homeAway']:x for x in c['competitors']};status=c['status']['type']
        old=index.get(int(e['id']),{})
        # Preserve unified schedule names, verified below against ESPN team identity.
        for side in ['home','away']:
            if old and old.get(side+'_team') not in [t[side]['team'].get('location'),t[side]['team'].get('displayName')]:
                guard=module('research/cfb/settlement_guard.py')
                if guard.team(old.get(side+'_team'))!=guard.team(t[side]['team'].get('location')):raise ValueError('CFB team identity mismatch')
        index[int(e['id'])]={**old,'game_id':int(e['id']),'home_team':old.get('home_team',t['home']['team']['location']),'away_team':old.get('away_team',t['away']['team']['location']),'start_date':c['date'],'start_time_tbd':False,'completed':status.get('completed') is True and status.get('state')=='post','home_points':t['home'].get('score'),'away_points':t['away'].get('score')}
    Path('runtime').mkdir(exist_ok=True);target='runtime/cfb_finals.csv';pd.DataFrame(index.values()).to_csv(target,index=False)
    for script in ['settle_predictions.py','settle_candidate_b_shadow.py']:
        subprocess.run([sys.executable,'research/cfb/'+script,'--schedule',target],check=True)
    subprocess.run([sys.executable,'research/cfb/report_candidate_b_shadow.py'],check=True)

NFL_ALIASES={'WSH':'WAS','LAR':'LA'}
def nfl(now,ledger_path='data/ledger/prediction_ledger.csv'):
    path=Path(ledger_path);ledger=pd.read_csv(path,float_precision='round_trip');before=ledger.copy();ledger['scored_at_utc']=ledger.scored_at_utc.astype('object')
    if ledger.prediction_id.duplicated().any():raise ValueError('Duplicate NFL snapshot identity')
    response=get_response('https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv');schedule=pd.read_csv(io.StringIO(response.text))
    pending=ledger[ledger.settlement_status.eq('pending')]
    known=schedule[schedule.game_id.isin(pending.game_id)]
    dates={pd.Timestamp(d).date() for d in known.gameday if pd.Timestamp(d).date()<=now.tz_convert('America/New_York').date()}
    finals={}
    for e in espn_events('nfl',dates):
        c=e['competitions'][0];t={x['homeAway']:x for x in c['competitors']};status=c['status']['type'];start=pd.Timestamp(c['date'])
        home=NFL_ALIASES.get(t['home']['team']['abbreviation'],t['home']['team']['abbreviation']);away=NFL_ALIASES.get(t['away']['team']['abbreviation'],t['away']['team']['abbreviation'])
        matches=known[known.home_team.eq(home)&known.away_team.eq(away)&pd.to_datetime(known.gameday).dt.date.eq(start.tz_convert('America/New_York').date())]
        if len(matches)!=1:continue
        finals[matches.iloc[0].game_id]=dict(home_team=home,away_team=away,start_time_utc=start.isoformat(),completed=status.get('completed') is True and status.get('state')=='post',home_score=t['home'].get('score'),away_score=t['away'].get('score'))
    for i,p in pending.iterrows():
        actual=finals.get(p.game_id)
        if not actual:continue
        saved=p.get('kickoff_utc')
        check={**p.to_dict(),'start_time_utc':saved if pd.notna(saved) else actual['start_time_utc']}
        if not final_valid(check,actual,now,capture='captured_at_utc'):continue
        h,a=float(actual['home_score']),float(actual['away_score'])
        ledger.loc[i,['actual_home_score','actual_away_score','settlement_status','scored_at_utc']]=[h,a,'tie' if h==a else 'final',now.isoformat()]
    write_settlements(path,before,ledger,['actual_home_score','actual_away_score','settlement_status','scored_at_utc'])
    first=ledger.sort_values('captured_at_utc').drop_duplicates('game_id');final=first[first.settlement_status.eq('final')].copy();m=module('pipeline/settle_predictions.py')
    summary=dict(evaluation_rule='First captured pregame snapshot per game; ties excluded',unique_games=len(first),settled_games=len(final),pending_games=int(first.settlement_status.eq('pending').sum()),updated_at_utc=now.isoformat(),v3=m.metrics(final,'v3_pick','v3_confidence'),v4_core=m.metrics(final,'v4_pick','v4_core_confidence'),v4_adjusted=m.metrics(final,'v4_pick','v4_adjusted_confidence'))
    write_json(path.parent/'summary.json',summary)

def nhl(now):
    root=Path('data/nhl');path=root/'v2_research/prediction_ledger.csv';ledger=pd.read_csv(path,float_precision='round_trip');before=ledger.copy();ledger['settled_at_utc']=ledger.settled_at_utc.astype('object');pairpath=root/'goalie_experiment/paired_ledger.jsonl'
    pairs=[json.loads(l) for l in pairpath.read_text().splitlines() if l.strip()] if pairpath.exists() else []
    pending=ledger[ledger.status.eq('pending')];ids={int(r.game_id) for _,r in pending.iterrows() if pd.Timestamp(r.start_time_utc)<=now}
    ids.update(int(r['game_id']) for r in pairs if r['status']=='pending' and pd.Timestamp(r['start_time_utc'])<=now)
    def fetch(gid):
        j=get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore')
        if int(j['id'])!=gid:raise ValueError('NHL game identity mismatch')
        return gid,dict(home_team=j['homeTeam']['abbrev'],away_team=j['awayTeam']['abbrev'],home_score=j['homeTeam'].get('score'),away_score=j['awayTeam'].get('score'),start_time_utc=j['startTimeUTC'],completed=j['gameState'] in ['OFF','FINAL'])
    finals=fetch_available(fetch,sorted(ids))
    manifest=json.loads(Path('model/nhl/v2_research/manifest.json').read_text());bundle=Path('model/nhl/v2_research/watchlist.joblib')
    assert hashlib.sha256(bundle.read_bytes()).hexdigest()==manifest['bundle_sha256']
    for i,p in pending.iterrows():
        actual=finals.get(int(p.game_id))
        if p.bundle_sha256!=manifest['bundle_sha256'] or not final_valid(p,actual,now) or actual['home_score']==actual['away_score']:continue
        ledger.loc[i,['status','actual_home_win','settled_at_utc']]=['settled',int(float(actual['home_score'])>float(actual['away_score'])),now.isoformat()]
    write_settlements(path,before,ledger,['status','actual_home_win','settled_at_utc'])
    sp=root/'v2_research/summary.json';s=json.loads(sp.read_text());s.update(results_checked_at_utc=now.isoformat(),total_prediction_rows=len(ledger),pending=int(ledger.status.eq('pending').sum()),settled=int(ledger.status.eq('settled').sum()),metrics=[dict(candidate=name,**metrics(rows.to_dict('records'))) for name,rows in ledger[ledger.status.eq('settled')].groupby('candidate')]);write_json(sp,s)
    if pairpath.exists():
        pm=json.loads(Path('model/nhl/goalie_experiment/manifest.json').read_text())
        assert hashlib.sha256(Path('model/nhl/goalie_experiment/frozen_bundle.joblib').read_bytes()).hexdigest()==pm['bundle_sha256']
        original_pairs=[r.copy() for r in pairs]
        for r in pairs:
            actual=finals.get(int(r['game_id']))
            if r['status']=='pending' and r['bundle_sha256']==pm['bundle_sha256'] and final_valid(r,actual,now) and float(actual['home_score'])!=float(actual['away_score']):
                r.update(status='settled',actual_home_win=int(float(actual['home_score'])>float(actual['away_score'])),settled_at_utc=now.isoformat())
        original_lines=pairpath.read_text().splitlines(keepends=True)
        if pairs!=original_pairs:
            for old,new in zip(original_pairs,pairs):
                if any(new[k]!=v for k,v in old.items() if k not in ('status','actual_home_win','settled_at_utc')):raise ValueError('NHL saved pair changed')
            atomic_text(pairpath,''.join(line if old==new else json.dumps(new,sort_keys=True)+'\n' for line,old,new in zip(original_lines,original_pairs,pairs)))
        sp=root/'goalie_experiment/summary.json';s=json.loads(sp.read_text());settled=[r for r in pairs if r['status']=='settled']
        s.update(results_checked_at_utc=now.isoformat(),settled_paired_games=len(settled),pending_paired_games=sum(r['status']=='pending' for r in pairs),metrics=[dict(candidate=c,**metrics([{**r,'home_win_prob':r['probabilities'][c]} for r in settled])) for c in ['team_control','inferred_goalie','confirmed_goalie']] if settled else [])
        if settled:
            by={r['candidate']:r for r in s['metrics']};s['confirmed_minus_control']={c:{k:by['confirmed_goalie'][k]-by[c][k] for k in ['accuracy','brier','log_loss']} for c in ['team_control','inferred_goalie']}
        write_json(sp,s)

def basketball_event(event):
    """Normalize official identity and status, retaining designated sides."""
    gid=str(event['id']);competitions=event.get('competitions',[])
    if len(competitions)!=1 or str(competitions[0].get('id'))!=gid:
        raise ValueError('Basketball final competition identity mismatch')
    c=competitions[0];sides={t['homeAway']:t for t in c['competitors']}
    if set(sides)!={'home','away'} or len(c['competitors'])!=2:
        raise ValueError('Basketball final team identity mismatch')
    season=event.get('season',{});status=c.get('status',{}).get('type',{})
    row=dict(game_id=gid,season=season.get('year'),season_type=season.get('type'),
             date=c.get('date'),neutral_site=c.get('neutralSite'),time_valid=c.get('timeValid',False),
             time_valid_missing=c.get('timeValid') is None,
             status_type_name=status.get('name'),status_type_completed=status.get('completed') is True and status.get('state')=='post')
    for side,t in sides.items():
        row[side+'_id']=str(t['team']['id']);row[side+'_score']=t.get('score')
    return row

def basketball_schedule(sport,pending,now):
    global ACTIVE_PENDING
    ACTIVE_PENDING={str(p['game_id']) for p in pending}
    league='nba' if sport=='nba' else 'mens-college-basketball'
    due=[p for p in pending if pd.to_datetime(p['start_time_utc'],utc=True,errors='coerce')<=now]
    ids={str(p['game_id']) for p in due};events={};source_urls={}
    dates=pending_dates(pd.Series([p['start_time_utc'] for p in due],dtype=object),now)
    for day in sorted(dates):
        url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/scoreboard?dates={day:%Y%m%d}&limit=1000'
        if sport=='cbb':url+='&groups=50'
        try:response=get(url)
        except requests.RequestException as error:
            REQUEST_ERRORS.append(dict(source=url,error=str(error)));continue
        for event in response.get('events',[]):
            if str(event['id']) in ids:
                events[str(event['id'])]=event;source_urls[str(event['id'])]=url
    def missing(gid):
        event=get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/summary?event={gid}').get('header',{})
        if str(event.get('id'))!=gid:raise ValueError('Basketball final event identity mismatch')
        return gid,event
    for gid,event in fetch_available(missing,sorted(ids-set(events))).items():
        events[gid]=event
        source_urls[gid]=f'https://site.api.espn.com/apis/site/v2/sports/basketball/{league}/summary?event={gid}'
    rows=[{**basketball_event(e),'result_source_url':source_urls[str(e['id'])],
           'result_source_event_sha256':hashlib.sha256(json.dumps(e,sort_keys=True,separators=(',',':')).encode()).hexdigest()} for e in events.values()]
    saved={str(p['game_id']):p for p in due}
    for row in rows:
        CHECKED_IDS.add(row['game_id'])
        p=saved[row['game_id']]
        home=p.get('home_team_id',p.get('home_id'));away=p.get('away_team_id',p.get('away_id'))
        state=None
        same_sides=(row['home_id'],row['away_id'])==(str(home),str(away))
        reversed_neutral=(sport=='cbb' and (row['home_id'],row['away_id'])==(str(away),str(home))
            and str(p.get('neutral_site')).lower() in ('true','1') and str(row['neutral_site']).lower() in ('true','1'))
        if home is not None and not (same_sides or reversed_neutral):
            state='identity_review'
        elif row['status_type_name'] in ('STATUS_POSTPONED','STATUS_CANCELED','STATUS_CANCELLED'):
            state='postponed' if row['status_type_name']=='STATUS_POSTPONED' else 'cancelled'
        if state:
            LIFECYCLE.append(dict(game_id=row['game_id'],state=state,checked_at_utc=now.isoformat(),
                saved_start_time_utc=p['start_time_utc'],official_start_time_utc=row['date'],
                source_url=row['result_source_url'],source_event_sha256=row['result_source_event_sha256']))
        if sport=='cbb':
            # Summary headers omit timeValid. A confirmed final with the exact
            # originally verified tipoff retains that evidence; false or changed
            # source times never receive this fallback.
            if row['time_valid_missing'] and row['status_type_name']=='STATUS_FINAL' and row['status_type_completed']:
                start=pd.to_datetime(row['date'],utc=True,errors='coerce')
                row['time_valid']=pd.notna(start) and start==pd.to_datetime(p['start_time_utc'],utc=True,errors='coerce')
    return pd.DataFrame(rows,columns=[
        'game_id','season','season_type','date','neutral_site','time_valid','status_type_name',
        'status_type_completed','home_id','away_id','home_score','away_score','time_valid_missing',
        'result_source_url','result_source_event_sha256'])

def cbb(now):
    directory=Path('data/cbb/prospective');path=directory/'prediction_ledger.json'
    ledger=json.loads(path.read_text());dashboard=json.loads((directory/'dashboard.json').read_text())
    bundle_sha=hashlib.sha256(Path('research/cbb/results/candidate_bundle.json').read_bytes()).hexdigest()
    if dashboard['bundle_sha256']!=bundle_sha or any(p['bundle_sha256']!=bundle_sha for p in ledger):
        raise ValueError('Frozen CBB model identity changed')
    schedule=basketball_schedule('cbb',[p for p in ledger if p['status']=='pending'],now)
    grader=module('research/cbb/prospective.py');graded,issues=grader.grade(ledger,schedule,now)
    if len(graded)!=len(ledger):raise ValueError('CBB saved forecast count changed')
    for old,new in zip(ledger,graded):
        if any(new[k]!=v for k,v in old.items() if k!='status'):raise ValueError('CBB saved forecast changed')
        if old['status']=='pending' and new['status']=='settled':
            source=schedule[schedule.game_id.eq(str(old['game_id']))].iloc[0]
            new.update(result_source_url=source.result_source_url,result_source_event_sha256=source.result_source_event_sha256)
    checked=set(schedule.game_id)
    issues=[r for r in dashboard.get('grading_issues',[]) if str(r['game_id']) not in checked]+issues
    totals=grader.summary(graded)
    dashboard.update(predictions=graded,summary=totals,grading_issues=issues,
                     results_checked_at_utc=now.isoformat())
    summary={**json.loads((directory/'summary.json').read_text()),**totals,
             'results_checked_at_utc':now.isoformat(),'grading_issues':issues}
    for p,value in [(path,graded),(directory/'dashboard.json',dashboard),(directory/'summary.json',summary)]:
        write_json(p,value)

def nba(now):
    directory=Path('data/nba/prospective');predpath=directory/'predictions.jsonl';resultpath=directory/'results.jsonl'
    original=predpath.read_bytes();predictions=[json.loads(l) for l in original.splitlines() if l.strip()]
    results=[json.loads(l) for l in resultpath.read_text().splitlines() if l.strip()] if resultpath.exists() else []
    manifest=json.loads(Path('model/nba/v1/manifest.json').read_text());settled={r['game_id'] for r in results}
    if hashlib.sha256(Path('model/nba/v1/frozen_bundle.joblib').read_bytes()).hexdigest()!=manifest['bundle_sha256']:
        raise ValueError('Frozen NBA model identity changed')
    if len(settled)!=len(results) or len({p['game_id'] for p in predictions})!=len(predictions):
        raise ValueError('Duplicate NBA ledger identity')
    if any(p['bundle_sha256']!=manifest['bundle_sha256'] or p['season']!=2027 or p['season_type']!=2 for p in predictions):
        raise ValueError('Frozen NBA forecast identity changed')
    if not settled<={p['game_id'] for p in predictions}:raise ValueError('Unknown NBA settlement identity')
    pending=[p for p in predictions if p['game_id'] not in settled]
    schedule={r['game_id']:r for r in basketball_schedule('nba',pending,now).to_dict('records')};new=[]
    for p in pending:
        r=schedule.get(p['game_id'])
        if not r or r['season']!=2027 or r['season_type']!=2 or r['status_type_name']!='STATUS_FINAL' or not r['status_type_completed']:continue
        if (r['home_id'],r['away_id'])!=(p['home_id'],p['away_id']):continue
        actual={**r,'home_team':p['home_team'],'away_team':p['away_team'],'start_time_utc':r['date'],'completed':True}
        if not final_valid(p,actual,now):continue
        h,a=float(r['home_score']),float(r['away_score'])
        if h==a or not h.is_integer() or not a.is_integer():continue
        new.append(dict(game_id=p['game_id'],home_score=h,away_score=a,actual_home_win=int(h>a),
                        actual_start_time_utc=pd.Timestamp(r['date']).isoformat(),settled_at_utc=now.isoformat(),source_state='post_completed',
                        result_source_url=r['result_source_url'],result_source_event_sha256=r['result_source_event_sha256']))
    if new:
        original_results=resultpath.read_text() if resultpath.exists() else ''
        atomic_text(resultpath,original_results+''.join(json.dumps(r,sort_keys=True,allow_nan=False)+'\n' for r in new))
    by_id={r['game_id']:r for r in results+new}
    rows=[{**p,**by_id.get(p['game_id'],{}),'status':'settled' if p['game_id'] in by_id else 'pending',
           'actual_home_win':by_id.get(p['game_id'],{}).get('actual_home_win')} for p in predictions]
    from sklearn.metrics import accuracy_score,brier_score_loss,log_loss
    completed=[r for r in rows if r['status']=='settled'];y=[r['actual_home_win'] for r in completed];p=[r['home_win_prob'] for r in completed]
    record=dict(games=len(y),correct=sum((v>=.5)==t for v,t in zip(p,y)),accuracy=float(accuracy_score(y,[v>=.5 for v in p])),
                brier=float(brier_score_loss(y,p)),log_loss=float(log_loss(y,p,labels=[0,1]))) if y else metrics([])
    dashboard=json.loads((directory/'dashboard.json').read_text())
    dashboard.update(predictions=rows,record=record,results_checked_at_utc=now.isoformat(),
                     grading='Confirmed final checks run separately from forecast builds')
    write_json(directory/'dashboard.json',dashboard)
    if predpath.read_bytes()!=original:raise ValueError('NBA saved forecasts changed')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('sport',choices=['nfl','cfb','nhl','nba','cbb']);a=ap.parse_args();now=pd.Timestamp.now(tz='UTC')
    directory=Path('data/current') if a.sport=='nfl' else Path('data')/a.sport
    path=directory/'result_check.json'
    previous=json.loads(path.read_text()) if path.exists() else {}
    global ACTIVE_PENDING
    REQUEST_ERRORS.clear();LIFECYCLE.clear();CHECKED_IDS.clear();ACTIVE_PENDING=None
    try:
        globals()[a.sport](now)
    except Exception as error:
        write_json(path,{**previous,'sport':a.sport,'attempted_at_utc':now.isoformat(),
                         'status':'failed','errors':[dict(error=str(error))]})
        raise
    # Keep unresolved annotations when an event could not be fetched this time.
    lifecycle={r['game_id']:r for r in previous.get('lifecycle',[])
               if r['game_id'] not in CHECKED_IDS and (ACTIVE_PENDING is None or r['game_id'] in ACTIVE_PENDING)}
    lifecycle.update({r['game_id']:r for r in LIFECYCLE})
    status='degraded' if REQUEST_ERRORS else 'success'
    write_json(path,dict(sport=a.sport,checked_at_utc=now.isoformat(),attempted_at_utc=now.isoformat(),
        last_success_at_utc=previous.get('last_success_at_utc',previous.get('checked_at_utc')) if REQUEST_ERRORS else now.isoformat(),
        status=status,errors=REQUEST_ERRORS,lifecycle=list(lifecycle.values()),interval_minutes=5,forecasts_unchanged=True))
    print(f'{a.sport}: final-score check {status}')
    if REQUEST_ERRORS:raise SystemExit(1)
if __name__=='__main__':main()
