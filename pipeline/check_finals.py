"""Settlement-only checks. Never create forecasts or load/refit model weights."""
import argparse, hashlib, importlib.util, io, json, math, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import requests

def get(url):
    r=requests.get(url,timeout=45);r.raise_for_status();return r.json()

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
    return math.isfinite(h) and math.isfinite(a) and min(h,a)>=0

def module(path):
    path=Path(path);sys.path.insert(0,str(path.parent));spec=importlib.util.spec_from_file_location(path.stem,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def espn_events(sport,dates):
    url=f'https://site.api.espn.com/apis/site/v2/sports/football/{sport}/scoreboard'
    events={}
    for day in sorted(dates):
        query=f'?dates={day:%Y%m%d}&limit=1000'+('&groups=80' if sport=='college-football' else '')
        for e in get(url+query).get('events',[]):
            events[str(e['id'])]=e
    return events.values()

def cfb(now):
    paths=[Path('data/cfb/ledger/prediction_ledger.csv'),Path('data/cfb/v2_shadow/verified_prediction_ledger.csv')]
    frames=[pd.read_csv(p) for p in paths if p.exists()]
    combined=pd.concat(frames,ignore_index=True)
    pending=combined[combined.correct.isna()]
    dates=set(pd.to_datetime(pending.schedule_kickoff_utc.fillna(pending.kickoff_utc),utc=True).dt.tz_convert('America/New_York').dt.date)
    dates={d for d in dates if d<=now.tz_convert('America/New_York').date()}
    # Overlay live ESPN states onto the full schedule so future kickoff metadata remains intact.
    schedule_url='https://github.com/sportsdataverse/sportsdataverse-data/releases/download/cfb_schedules/cfb_schedules_2026.csv.gz'
    response=requests.get(schedule_url,timeout=90);response.raise_for_status()
    schedule=pd.read_csv(io.BytesIO(response.content),compression='gzip');index={int(r['game_id']):r for r in schedule.to_dict('records')}
    for e in espn_events('college-football',dates):
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
def nfl(now):
    path=Path('data/ledger/prediction_ledger.csv');ledger=pd.read_csv(path);ledger['scored_at_utc']=ledger.scored_at_utc.astype('object')
    response=requests.get('https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',timeout=45);response.raise_for_status();schedule=pd.read_csv(io.StringIO(response.text))
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
    locked=[c for c in ledger if c not in ['actual_home_score','actual_away_score','settlement_status','scored_at_utc']];before=ledger[locked].copy()
    for i,p in pending.iterrows():
        actual=finals.get(p.game_id)
        if not actual:continue
        check={**p.to_dict(),'start_time_utc':actual['start_time_utc']}
        if not final_valid(check,actual,now,capture='captured_at_utc'):continue
        h,a=float(actual['home_score']),float(actual['away_score'])
        ledger.loc[i,['actual_home_score','actual_away_score','settlement_status','scored_at_utc']]=[h,a,'tie' if h==a else 'final',now.isoformat()]
    pd.testing.assert_frame_equal(before,ledger[locked]);ledger.to_csv(path,index=False)
    first=ledger.sort_values('captured_at_utc').drop_duplicates('game_id');final=first[first.settlement_status.eq('final')].copy();m=module('pipeline/settle_predictions.py')
    summary=dict(evaluation_rule='First captured pregame snapshot per game; ties excluded',unique_games=len(first),settled_games=len(final),pending_games=int(first.settlement_status.eq('pending').sum()),updated_at_utc=now.isoformat(),v3=m.metrics(final,'v3_pick','v3_confidence'),v4_core=m.metrics(final,'v4_pick','v4_core_confidence'),v4_adjusted=m.metrics(final,'v4_pick','v4_adjusted_confidence'))
    (path.parent/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')

def nhl(now):
    root=Path('data/nhl');path=root/'v2_research/prediction_ledger.csv';ledger=pd.read_csv(path);ledger['settled_at_utc']=ledger.settled_at_utc.astype('object');pairpath=root/'goalie_experiment/paired_ledger.jsonl'
    pairs=[json.loads(l) for l in pairpath.read_text().splitlines() if l.strip()] if pairpath.exists() else []
    pending=ledger[ledger.status.eq('pending')];ids={int(r.game_id) for _,r in pending.iterrows() if pd.Timestamp(r.start_time_utc)<=now}
    ids.update(int(r['game_id']) for r in pairs if r['status']=='pending' and pd.Timestamp(r['start_time_utc'])<=now)
    def fetch(gid):
        j=get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore')
        if int(j['id'])!=gid:raise ValueError('NHL game identity mismatch')
        return gid,dict(home_team=j['homeTeam']['abbrev'],away_team=j['awayTeam']['abbrev'],home_score=j['homeTeam'].get('score'),away_score=j['awayTeam'].get('score'),start_time_utc=j['startTimeUTC'],completed=j['gameState'] in ['OFF','FINAL'])
    with ThreadPoolExecutor(max_workers=8) as pool:finals=dict(pool.map(fetch,sorted(ids)))
    manifest=json.loads(Path('model/nhl/v2_research/manifest.json').read_text());bundle=Path('model/nhl/v2_research/watchlist.joblib')
    assert hashlib.sha256(bundle.read_bytes()).hexdigest()==manifest['bundle_sha256']
    for i,p in pending.iterrows():
        actual=finals.get(int(p.game_id))
        if p.bundle_sha256!=manifest['bundle_sha256'] or not final_valid(p,actual,now) or actual['home_score']==actual['away_score']:continue
        ledger.loc[i,['status','actual_home_win','settled_at_utc']]=['settled',int(float(actual['home_score'])>float(actual['away_score'])),now.isoformat()]
    ledger.to_csv(path,index=False)
    sp=root/'v2_research/summary.json';s=json.loads(sp.read_text());s.update(as_of_utc=now.isoformat(),new_prediction_rows=0,total_prediction_rows=len(ledger),pending=int(ledger.status.eq('pending').sum()),settled=int(ledger.status.eq('settled').sum()),metrics=[dict(candidate=name,**metrics(rows.to_dict('records'))) for name,rows in ledger[ledger.status.eq('settled')].groupby('candidate')]);sp.write_text(json.dumps(s,indent=2)+'\n')
    if pairpath.exists():
        pm=json.loads(Path('model/nhl/goalie_experiment/manifest.json').read_text())
        assert hashlib.sha256(Path('model/nhl/goalie_experiment/frozen_bundle.joblib').read_bytes()).hexdigest()==pm['bundle_sha256']
        for r in pairs:
            actual=finals.get(int(r['game_id']))
            if r['status']=='pending' and r['bundle_sha256']==pm['bundle_sha256'] and final_valid(r,actual,now) and float(actual['home_score'])!=float(actual['away_score']):
                r.update(status='settled',actual_home_win=int(float(actual['home_score'])>float(actual['away_score'])),settled_at_utc=now.isoformat())
        pairpath.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in pairs));sp=root/'goalie_experiment/summary.json';s=json.loads(sp.read_text());settled=[r for r in pairs if r['status']=='settled']
        s.update(as_of_utc=now.isoformat(),settled_paired_games=len(settled),pending_paired_games=sum(r['status']=='pending' for r in pairs),metrics=[dict(candidate=c,**metrics([{**r,'home_win_prob':r['probabilities'][c]} for r in settled])) for c in ['team_control','inferred_goalie','confirmed_goalie']] if settled else [])
        if settled:
            by={r['candidate']:r for r in s['metrics']};s['confirmed_minus_control']={c:{k:by['confirmed_goalie'][k]-by[c][k] for k in ['accuracy','brier','log_loss']} for c in ['team_control','inferred_goalie']}
        sp.write_text(json.dumps(s,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('sport',choices=['nfl','cfb','nhl']);a=ap.parse_args();now=pd.Timestamp.now(tz='UTC')
    globals()[a.sport](now)
    directory=Path('data/current') if a.sport=='nfl' else Path('data')/a.sport
    directory.mkdir(parents=True,exist_ok=True);(directory/'result_check.json').write_text(json.dumps(dict(sport=a.sport,checked_at_utc=now.isoformat(),status='success',interval_minutes=15,forecasts_unchanged=True),indent=2)+'\n')
    print(f'{a.sport}: final-score check completed')
if __name__=='__main__':main()
