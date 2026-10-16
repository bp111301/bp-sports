"""Read-only cross-sport prospective dashboard. Parallel experiments stay separate."""
UI_REVISION="weekly-results-20261013"
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
import io,json,math,html
import pandas as pd
import streamlit as st
from nhl_ui import audit_note
from navigation_ui import open_board
from game_center_ui import filter_favorites,score_html,confidence_html,context,load_scores
from game_status import display_state
from matchup_details_ui import game_tile, details_button

RAW='https://raw.githubusercontent.com/bp111301/bp-sports/'
SOURCES={
 'nfl':('main','data/ledger/prediction_ledger.csv'), 'nfl_update':('main','data/current/prediction_metadata.json'),
 'cfb':('main','data/cfb/ledger/prediction_ledger.csv'), 'cfb_update':('main','data/cfb/current/metadata.json'),
 'shadow':('main','data/cfb/v2_shadow/verified_prediction_ledger.csv'), 'shadow_update':('main','data/cfb/v2_shadow/metadata.json'),
 'nhl':('nhl-v1-research','data/nhl/v2_research/prediction_ledger.csv'), 'nhl_update':('nhl-v1-research','data/nhl/v2_research/summary.json'),
 'goalie':('nhl-v1-research','data/nhl/goalie_experiment/paired_ledger.jsonl'), 'goalie_update':('nhl-v1-research','data/nhl/goalie_experiment/summary.json'),
 'nba':('nba-v1-research','data/nba/prospective/dashboard.json')}
PRIMARY={'NFL':'nfl','CFB':'cfb','NHL':'reference_control','NBA':'nba'}
LABELS={'nfl':'NFL V4','cfb':'CFB V1','reference_control':'NHL reference','nba':'NBA V1','shadow':'CFB Candidate B','decay2_logistic':'NHL recency weighting','linear_regulation_blend':'NHL regulation blend','goalie_team_control':'Goalie test · team control','goalie_inferred_goalie':'Goalie test · inferred starter','goalie_confirmed_goalie':'Goalie test · confirmed starter'}
COLORS={'NFL':'#85b4ff','CFB':'#f3cc73','NHL':'#77d7db','NBA':'#f5ac74'}
LIMITS={'NFL':108,'CFB':30,'NHL':30,'NBA':3}
FROZEN_NBA='c57d804ab9062542e9e456a9585327bbb677732e5ad55b0186f91ddbdf5e079f'
FROZEN_NHL='d60b32b93d795cc0905f626489720640eeb4691002b40aa6b2b38440953d5cbe'
FROZEN_SHADOW='43363558b09e708bd7e9131c87250dc65a67faf770bdcb3627e9b4ac8a9dd1c6'
COLUMNS=['game_id','sport','group','home','away','p','created','start','settled','y','details']

def esc(value):return html.escape(str(value),quote=True)
def flag(value):return str(value).lower() in ('true','1','1.0','yes')
def ts(value):return pd.to_datetime(value,utc=True,errors='coerce')

def fetch_source(item):
    key,(branch,path)=item
    try:
        with urlopen(Request(RAW+branch+'/'+path,headers={'User-Agent':'BP-Sports-Overview/1.0'}),timeout=8) as response:
            raw=response.read(8*1024*1024+1)
            if len(raw)>8*1024*1024:raise ValueError('Feed too large')
        text=raw.decode('utf-8')
        if path.endswith('.csv'):value=pd.read_csv(io.StringIO(text)).to_dict('records')
        elif path.endswith('.jsonl'):value=[json.loads(line) for line in text.splitlines() if line]
        else:value=json.loads(text)
        return key,dict(ok=True,data=value)
    except Exception:return key,dict(ok=False,data=None)

@st.cache_data(ttl=120)
def load_overview():
    with ThreadPoolExecutor(max_workers=8) as pool:return dict(pool.map(fetch_source,SOURCES.items()))

def row(game_id,sport,group,home,away,p,created,start,settled=False,y=None,details=None):
    return dict(game_id=str(game_id),sport=sport,group=group,home=home,away=away,p=float(p),created=ts(created),start=ts(start),settled=bool(settled),y=y,details=details or {})

def normalize(key,data,now):
    rows=[]
    if key=='nfl':
        # Repeated refreshes do not create additional graded games.
        d=pd.DataFrame(data)
        if d.empty:return []
        d['captured_at_utc']=pd.to_datetime(d.captured_at_utc,utc=True,errors='coerce')
        d=d.dropna(subset=['captured_at_utc']);d=d[d.captured_at_utc.le(now)].sort_values('captured_at_utc').drop_duplicates('game_id')
        for r in d.to_dict('records'):
            if r.get('settlement_status')=='tie':continue
            confidence=float(r['v4_adjusted_confidence']);p=confidence if r['v4_pick']==r['home_team'] else 1-confidence
            final=r.get('settlement_status')=='final';h=pd.to_numeric(r.get('actual_home_score'),errors='coerce');a=pd.to_numeric(r.get('actual_away_score'),errors='coerce')
            if final and not (pd.notna(h) and pd.notna(a) and h!=a):continue
            rows.append(row(r['game_id'],'NFL','nfl',r['home_team'],r['away_team'],p,r['captured_at_utc'],None,final,int(h>a) if final else None,details=r))
    elif key in ('cfb','shadow'):
        for r in data:
            start=r.get('schedule_kickoff_utc')
            if pd.isna(start):start=r['kickoff_utc']
            final=pd.notna(r.get('correct')) if key=='cfb' else flag(r.get('settled',False))
            if key=='shadow':
                if r.get('bundle_sha256')!=FROZEN_SHADOW:raise ValueError('Shadow model identity mismatch')
                frozen=ts(r.get('bundle_frozen_at_utc'))
                if pd.isna(frozen) or ts(r['snapshot_created_utc'])<frozen:continue
            winner=r.get('actual_winner');y=int(winner==r['home_team']) if final and winner in (r['home_team'],r['away_team']) else None
            rows.append(row(r['game_id'],'CFB',key,r['home_team'],r['away_team'],r['home_win_prob'],r['snapshot_created_utc'],start,final,y,details=r))
    elif key=='nhl':
        for r in data:
            if r.get('bundle_sha256')!=FROZEN_NHL:raise ValueError('NHL model identity mismatch')
            if r['candidate'] not in ('reference_control','decay2_logistic','linear_regulation_blend') or r['status'] not in ('pending','settled'):continue
            rows.append(row(r['game_id'],'NHL',r['candidate'],r['home_team'],r['away_team'],r['home_win_prob'],r['created_at_utc'],r['start_time_utc'],r['status']=='settled',pd.to_numeric(r.get('actual_home_win'),errors='coerce'),details=r))
    elif key=='goalie':
        for r in data:
            if r.get('status') not in ('pending','settled'):continue
            probabilities=r['probabilities']
            if set(probabilities)!={'team_control','inferred_goalie','confirmed_goalie'}:raise ValueError('Incomplete goalie comparison')
            for name,p in probabilities.items():rows.append(row(r['game_id'],'NHL','goalie_'+name,r['home_team'],r['away_team'],p,r['created_at_utc'],r['start_time_utc'],r['status']=='settled',r.get('actual_home_win'),details=r))
    elif key=='nba':
        if data.get('feed_status')!='enabled':raise ValueError('NBA feed unavailable')
        if data.get('bundle_sha256')!=FROZEN_NBA:raise ValueError('NBA model identity mismatch')
        for r in data.get('predictions',[]):
            if r.get('season')!=2027 or r.get('season_type')!=2 or r.get('status') not in ('pending','settled'):continue
            if r.get('bundle_sha256')!=data.get('bundle_sha256'):raise ValueError('NBA model identity mismatch')
            rows.append(row(r['game_id'],'NBA','nba',r['home_team'],r['away_team'],r['home_win_prob'],r['created_at_utc'],r['start_time_utc'],r['status']=='settled',r.get('actual_home_win'),details=r))
    valid=[]
    for r in rows:
        if not math.isfinite(r['p']) or not 0<=r['p']<=1 or pd.isna(r['created']) or r['created']>now:continue
        if r['sport']!='NFL' and (pd.isna(r['start']) or r['created']>=r['start']):continue
        if r['settled'] and (r['y'] not in (0,1) or (pd.notna(r['start']) and r['start']>now)):continue
        valid.append(r)
    if pd.DataFrame(valid,columns=COLUMNS).duplicated(['group','game_id']).any():raise ValueError('Duplicate prospective forecasts')
    return valid

def prepare(payload,now):
    records=[];available={};updates={}
    for key in ('nfl','cfb','shadow','nhl','goalie','nba'):
        source=payload.get(key,{});available[key]=source.get('ok',False)
        if available[key]:
            try:records+=normalize(key,source['data'],now)
            except (ValueError,TypeError,KeyError):available[key]=False
    for sport,key,field in [('NFL','nfl_update','captured_at_utc'),('CFB','cfb_update','generated_at_utc'),('NHL','nhl_update','as_of_utc')]:
        source=payload.get(key,{})
        updates[sport]=ts(source['data'].get(field)) if source.get('ok') else pd.NaT
    updates['NBA']=ts(payload['nba']['data'].get('updated_at_utc')) if payload.get('nba',{}).get('ok') else pd.NaT
    board=pd.DataFrame(records,columns=COLUMNS)
    if not board.empty:board['confidence']=board.p.where(board.p.ge(.5),1-board.p)
    else:board['confidence']=pd.Series(dtype=float)
    return board,available,updates

def metrics(board):
    settled=board[board.settled];n=len(settled)
    if not n:return dict(games=0,wins=0,losses=0,accuracy=None,brier=None,log_loss=None)
    p=settled.p.astype(float);y=settled.y.astype(float);wins=int((p.ge(.5)==y).sum());q=p.clip(1e-15,1-1e-15)
    loss=-sum(a*math.log(b)+(1-a)*math.log(1-b) for a,b in zip(y,q))/n
    return dict(games=n,wins=wins,losses=n-wins,accuracy=wins/n,brier=float(((p-y)**2).mean()),log_loss=loss)

def ct(value):
    return 'Update time unavailable' if pd.isna(value) else value.tz_convert('America/Chicago').strftime('%b %d · %I:%M %p CT').replace(' 0',' ')

def freshness(sport,stamp,now):
    if pd.isna(stamp) or stamp>now:return 'Update time unavailable','unknown'
    if now-stamp>pd.Timedelta(hours=LIMITS[sport]):return 'Update overdue','warning'
    return 'Feed verified','good'

def table(headers,rows):
    return '<div class="ov-table-wrap"><table class="ov-table"><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table></div>'

def game_state(r,now):
    if r.settled:return ('Win','win') if (r.p>=.5)==r.y else ('Loss','loss')
    if pd.notna(r.start) and r.start<=now:return 'Awaiting final','waiting'
    return 'Pregame','pregame'

def select_games(board,view,sport,query,now):
    shown=board.copy()
    if sport!='All sports':shown=shown[shown.sport==sport]
    if view=='Today':
        today=now.tz_convert('America/Chicago').date()
        shown=shown[shown.start.map(lambda t:pd.notna(t) and t.tz_convert('America/Chicago').date()==today)]
    elif view=='Upcoming':shown=shown[(~shown.settled)&shown.start.gt(now)]
    elif view=='Awaiting finals':shown=shown[(~shown.settled)&shown.start.le(now)]
    elif view=='Results':shown=shown[shown.settled]
    if query.strip():
        q=query.strip().casefold()
        shown=shown[shown.apply(lambda r:q in (str(r.home)+' '+str(r.away)).casefold(),axis=1)]
    return shown.sort_values(['start','created'],ascending=view!='Results',na_position='last')

def game_cards(board,now):
    cards=[]
    for r in board.itertuples():
        state,cls=game_state(r,now)
        if not r.settled:state=display_state(context(r.sport,r.game_id,r.home,r.away),False,r.start,now)
        status=context(r.sport,r.game_id,r.home,r.away)
        scores=score_html(r.sport,r.game_id,r.home,r.away,r.settled,r.start,now) if r.settled or status and status.get('state') in ('live','final') else ''
        pick=r.home if r.p>=.5 else r.away
        winner=r.home if r.y==1 else r.away
        detail='Final winner: '+str(winner) if r.settled else 'Result pending · excluded from record' if cls=='waiting' else 'Saved before game time'
        time=ct(r.start) if pd.notna(r.start) else 'Kickoff time on NFL board'
        note=audit_note(r.game_id,FROZEN_NHL) if r.sport=='NHL' else None
        audit=f'<div class="desk-detail" style="color:#f1d28f">Input concern · missing power-play feature. <a href="{esc(note["report_url"])}" target="_blank" rel="noopener noreferrer">View audit</a></div>' if note else ''
        cards.append(f'<article class="desk-game" style="--accent:{COLORS[r.sport]}"><div class="desk-top"><span class="desk-sport">{esc(r.sport)}</span><span class="desk-state {cls}">{state}</span></div><div class="desk-time">{esc(time)}</div>{scores}<div class="desk-match">{esc(r.away)} <span>@</span> {esc(r.home)}</div><div class="desk-pick"><div><small>SAVED PICK</small><strong>{esc(pick)}</strong></div><div class="desk-prob">{r.confidence*100:.1f}%<small>MODEL PROBABILITY</small></div></div><div class="desk-bar" aria-label="Win confidence {r.confidence*100:.1f}%"><div style="width:{r.confidence*100:.1f}%"></div></div><div class="desk-detail">{esc(detail)}</div>{confidence_html(r.confidence,r.sport,bool(note))}{audit}</article>')
    return '<div class="desk-grid">'+''.join(cards)+'</div>'

def select_day(board,day,sport='All sports'):
    shown=board[board.apply(lambda r:PRIMARY.get(r.sport)==r.group,axis=1).astype(bool)].copy()
    if sport!='All sports':shown=shown[shown.sport==sport]
    shown=shown[shown.start.map(lambda t:pd.notna(t) and ts(t).tz_convert('America/Chicago').date()==day)]
    return shown.drop_duplicates(['sport','game_id']).sort_values(['start','sport'])

def render_game_cards(board,now,key):
    for offset in range(0,len(board),3):
        with st.container(key=key+'_row_'+str(offset)):
            columns=st.columns(3)
            for column,(_,r) in zip(columns,board.iloc[offset:offset+3].iterrows()):
                with column:
                    game_tile(r.sport,r,key+'_'+r.sport+'_'+str(r.game_id),
                              game_cards(pd.DataFrame([r]),now).replace('class="desk-grid"','class="desk-single"'),
                              LABELS[r.group],now=now)

def render_daily_results(primary,available,now):
    st.markdown('<div class="section-title">Results by date</div><div class="section-sub">Review a game night · dates and times are Central</div>',unsafe_allow_html=True)
    dated=primary[primary.start.notna()]
    if dated.empty:st.info('No saved games have a verified game date yet.');return
    dates=sorted({ts(t).tz_convert('America/Chicago').date() for t in dated.start})
    finals=dated[dated.settled]
    default=max(ts(t).tz_convert('America/Chicago').date() for t in finals.start) if len(finals) else min(dates,key=lambda d:abs((d-now.tz_convert('America/Chicago').date()).days))
    left,right=st.columns([2,1])
    day=left.date_input('Game date (Central)',value=default,min_value=min(dates),max_value=max(dates),key='daily_date')
    sport=right.selectbox('Results sport',['All sports',*PRIMARY],key='daily_sport')
    personal=filter_favorites(primary,None,'daily_my_teams',home='home',away='away')
    shown=select_day(personal,day,sport);m=metrics(shown)
    a,b,c=st.columns(3);a.metric('Slate record',f"{m['wins']}–{m['losses']}");b.metric('Awaiting grading',len(shown)-m['games']);c.metric('Graded accuracy',f"{m['accuracy']*100:.1f}%" if m['games'] else '—')
    st.caption(f"{day:%B %d, %Y} · {len(shown)} saved matchups · {m['games']} graded. One primary forecast per game; pending games stay out of accuracy. NHL uses the experimental reference control. Filters affect this slate only.")
    missing=[s for s,k in [('NFL','nfl'),('CFB','cfb'),('NHL','nhl'),('NBA','nba')] if (sport=='All sports' or sport==s) and not available.get(k)]
    if missing:st.warning('This slate is incomplete: '+', '.join(missing)+' grading feeds are unavailable.')
    if shown.empty:st.info('No saved matchups match this date and filter.');return
    rows=[]
    for s in PRIMARY:
        section=shown[shown.sport==s]
        if section.empty:continue
        sm=metrics(section);rows.append([s,f"{sm['wins']}–{sm['losses']}",sm['games'],len(section)-sm['games'],f"{sm['accuracy']*100:.1f}%" if sm['games'] else '—'])
    st.markdown(table(['SPORT','RECORD','GRADED','PENDING','ACCURACY'],rows),unsafe_allow_html=True)
    render_game_cards(shown,now,'daily_details')
    if primary.start.isna().any():st.caption('Saved games with unavailable start times are excluded from date grouping until their dates can be verified.')

def weekly_board(payload, sport, now, latest=False):
    """Read-only results, with one snapshot per game and ties kept out of accuracy."""
    board, available, _ = prepare(payload, now)
    section = board[(board.sport == sport) & (board.group == PRIMARY[sport])].copy()
    section['tie'] = False
    if sport == 'NFL' and available.get('nfl'):
        data = pd.DataFrame(payload['nfl']['data'])
        if not data.empty:
            data['captured_at_utc'] = pd.to_datetime(data.captured_at_utc, utc=True, errors='coerce')
            data = data[data.captured_at_utc.le(now)].sort_values('captured_at_utc', kind='stable')
            # A verified kickoff, when present, must also precede no selected snapshot.
            valid = []
            for item in data.to_dict('records'):
                status = context('NFL', item['game_id'], item['home_team'], item['away_team'])
                start = ts(status.get('start_time_utc')) if status else pd.NaT
                if pd.notna(start) and item['captured_at_utc'] >= start:continue
                valid.append(item)
            data = pd.DataFrame(valid)
            records = []
            if not data.empty:
                for item in data.drop_duplicates('game_id', keep='last' if latest else 'first').to_dict('records'):
                    h = pd.to_numeric(item.get('actual_home_score'), errors='coerce')
                    a = pd.to_numeric(item.get('actual_away_score'), errors='coerce')
                    tie = item.get('settlement_status') == 'tie' and pd.notna(h) and h == a
                    final = item.get('settlement_status') == 'final' and pd.notna(h) and pd.notna(a) and h != a
                    confidence = float(item['v4_adjusted_confidence'])
                    if not math.isfinite(confidence) or not .5 <= confidence <= 1:continue
                    p = confidence if item['v4_pick'] == item['home_team'] else 1-confidence
                    r = row(item['game_id'], 'NFL', 'nfl', item['home_team'], item['away_team'], p, item['captured_at_utc'], None, final, int(h > a) if final else None, item)
                    r.update(tie=tie, confidence=confidence)
                    records.append(r)
            section = pd.DataFrame(records, columns=COLUMNS+['tie','confidence'])
    section['start']=pd.to_datetime(section['start'],utc=True).astype('datetime64[ns, UTC]')
    periods = []
    for index, item in section.iterrows():
        status = context(sport, item.game_id, item.home, item.away)
        if status:section.loc[index, 'start'] = ts(status.get('start_time_utc'))
        details = item.details
        if sport == 'NFL':
            bits = str(item.game_id).split('_')
            period = f'{bits[0]} · Week {int(bits[1])}' if len(bits) >= 2 and bits[1].isdigit() else 'Week unavailable'
        elif sport == 'CFB':period = f"{details.get('season', 'Unknown')} · Week {details.get('week', 'Unknown')}"
        else:
            start = ts(section.loc[index, 'start'])
            if pd.isna(start):period = 'Date unavailable'
            else:
                day = start.tz_convert('America/Chicago').normalize()
                monday = day-pd.Timedelta(days=day.weekday())
                period = monday.strftime('Week of %Y-%m-%d')
        periods.append(period)
    section['period'] = periods
    return section, available.get('nhl' if sport == 'NHL' else sport.lower(), False)


def weekly_metrics(section):
    m = metrics(section[~section.tie.astype(bool)])
    m['ties'] = int(section.tie.sum())
    m['pending'] = len(section)-m['games']-m['ties']
    return m


def weekly_game_table(section):
    rows = []
    for r in section.sort_values(['start','created'], na_position='last').itertuples():
        d = r.details
        h = d.get('actual_home_score', d.get('home_points_final', d.get('home_score')))
        a = d.get('actual_away_score', d.get('away_points_final', d.get('away_score')))
        # Score feeds can publish a final before the grading ledger settles it.
        if (r.settled or r.tie) and (pd.isna(h) or pd.isna(a)):
            status = context(r.sport, r.game_id, r.home, r.away)
            if status:h, a = status.get('home_score'), status.get('away_score')
        score = f'{int(float(a))}–{int(float(h))}' if (r.settled or r.tie) and pd.notna(a) and pd.notna(h) else '—'
        result = 'Tie · excluded' if r.tie else ('Win' if (r.p >= .5) == r.y else 'Loss') if r.settled else 'Pending'
        rows.append({'Game':f'{r.away} @ {r.home}', 'Saved pick':r.home if r.p >= .5 else r.away,
                     'Confidence':f'{r.confidence*100:.1f}%', 'Final (away–home)':score, 'Result':result,
                     'Game time (CT)':ct(r.start), 'Snapshot (CT)':ct(r.created)})
    return pd.DataFrame(rows)


def render_weekly_results(now=None):
    now = pd.Timestamp.now(tz='UTC') if now is None else ts(now)
    st.title('Weekly results')
    st.write('Every saved pick, every verified result. Follow weekly progress and how confidence holds up.')
    sport = st.selectbox('Sport', list(PRIMARY), key='weekly_sport')
    mode = st.radio('Forecast to review', ['Original picks · official record','Latest saved pregame picks'], horizontal=True, key='weekly_mode') if sport == 'NFL' else 'Original picks · official record'
    latest = mode == 'Latest saved pregame picks'
    section, ok = weekly_board(load_overview(), sport, now, latest)
    if not ok:st.warning('The grading feed is unavailable. Results cannot be verified right now.');return
    if sport == 'NHL':st.caption('NHL uses the experimental reference control. Challenger and goalie experiments remain separate.')
    st.caption('The official record uses the first saved forecast per game. Latest NFL snapshots are a separate comparison. Ties and pending games are excluded from accuracy. NHL and NBA weeks run Monday–Sunday in Central time.')
    if section.empty:st.info('No prospective games are saved yet. Results will appear after regular-season forecasts and verified finals.');return
    overall = weekly_metrics(section)
    overall_accuracy = f"{overall['accuracy']*100:.1f}% accuracy" if overall['games'] else 'Accuracy pending'
    st.caption(f"Overall in this view: {overall['wins']}–{overall['losses']} · {overall_accuracy} · {overall['ties']} ties · {overall['pending']} pending.")
    def period_key(label):
        if ' · Week ' in label:
            year, week = label.split(' · Week ')
            return (int(year), int(week)) if year.isdigit() and week.isdigit() else (0,0)
        return (label,)
    periods = sorted(section.period.unique(), key=period_key, reverse=True)
    completed = section[section.settled | section.tie.astype(bool)]
    default = periods.index(sorted(completed.period.unique(), key=period_key, reverse=True)[0]) if len(completed) else 0
    period = st.selectbox('Week', periods, index=default, key='weekly_period_'+sport)
    shown = section[section.period == period]
    m = weekly_metrics(shown)
    a,b,c,d = st.columns(4)
    a.metric('Record', f"{m['wins']}–{m['losses']}")
    b.metric('Accuracy', f"{m['accuracy']*100:.1f}%" if m['games'] else '—')
    c.metric('Ties', m['ties']);d.metric('Pending', m['pending'])
    x,y = st.columns(2)
    x.metric('Brier score', f"{m['brier']:.4f}" if m['games'] else '—')
    y.metric('Log loss', f"{m['log_loss']:.4f}" if m['games'] else '—')
    st.caption('Lower Brier score and log loss mean better probability quality. A single week is a small sample.')
    st.subheader('Confidence breakdown')
    bands = []
    for lo,hi,label in [(.5,.6,'50–59.9%'),(.6,.7,'60–69.9%'),(.7,.8,'70–79.9%'),(.8,.9,'80–89.9%'),(.9,1.01,'90–100%')]:
        group = shown[shown.confidence.ge(lo) & shown.confidence.lt(hi)]
        bm = weekly_metrics(group);graded = group[group.settled]
        bands.append({'Confidence':label,'Record':f"{bm['wins']}–{bm['losses']}", 'Graded':bm['games'],
                      'Average estimate':f'{graded.confidence.mean()*100:.1f}%' if len(graded) else '—',
                      'Actual accuracy':f"{bm['accuracy']*100:.1f}%" if bm['games'] else '—'})
    st.dataframe(pd.DataFrame(bands), hide_index=True, use_container_width=True)
    st.subheader('Biggest confidence misses')
    misses = shown[shown.settled & (shown.p.ge(.5) != shown.y)].sort_values('confidence', ascending=False).head(5)
    if misses.empty:st.info('No graded losses in this week yet.')
    else:st.dataframe(weekly_game_table(misses), hide_index=True, use_container_width=True)
    st.subheader('All saved picks & final scores')
    games = weekly_game_table(shown)
    st.dataframe(games, hide_index=True, use_container_width=True)
    st.download_button('Download this week', games.to_csv(index=False), file_name=sport.lower()+'-weekly-results.csv', mime='text/csv')


def yesterday_recap(payload,now):
    """One original primary forecast per game, grouped by Central game date."""
    board,available,_=prepare(payload,now)
    other=board.loc[(board.sport!='NFL') & board.apply(lambda r:PRIMARY.get(r.sport)==r.group,axis=1).astype(bool)].copy() if len(board) else board.copy()
    other['tie']=False
    nfl,_=weekly_board(payload,'NFL',now)
    shown=pd.concat([other,nfl],ignore_index=True)
    shown['start']=pd.to_datetime(shown['start'],utc=True).astype('datetime64[ns, UTC]')
    for i,r in shown.iterrows():
        status=context(r.sport,r.game_id,r.home,r.away)
        if status:shown.at[i,'start']=ts(status.get('start_time_utc'))
    yesterday=(now.tz_convert('America/Chicago').normalize()-pd.DateOffset(days=1)).date()
    shown=shown.loc[shown.start.map(lambda t:pd.notna(t) and ts(t).tz_convert('America/Chicago').date()==yesterday).astype(bool)].copy()
    shown=shown.sort_values(['created','game_id']).drop_duplicates(['sport','game_id']).sort_values(['start','sport'])
    return yesterday,shown,available

def render_yesterday_recap(payload,now):
    day,shown,available=yesterday_recap(payload,now)
    missing=[sport for sport,key in PRIMARY.items() if not available.get('nhl' if sport=='NHL' else key)]
    m=weekly_metrics(shown);accuracy=f"{m['accuracy']:.1%}" if m['games'] else '—'
    chips=[]
    for sport in PRIMARY:
        section=shown[shown.sport==sport]
        if section.empty:continue
        sm=weekly_metrics(section)
        record=f"{sm['wins']}–{sm['losses']}"+(f" · {sm['ties']} tie" if sm['ties'] else '')
        chips.append(f'<span style="font-size:.78rem;color:{COLORS[sport]}">{sport} <b>{record}</b></span>')
    headline='Results incomplete' if missing else f"{m['wins']}–{m['losses']} · {accuracy}" if m['games'] else 'Awaiting grading' if len(shown) else 'No tracked games'
    note=f"{m['games']} graded · {m['pending']} awaiting grading"+(f" · {m['ties']} ties excluded" if m['ties'] else '')
    st.markdown(f'''<section aria-label="Yesterday's recap" style="background:#101a27;border:1px solid #293a50;border-left:3px solid #7baeff;border-radius:14px;padding:15px 18px;margin:0 0 10px">
<div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px"><span style="color:#a7b9d0;font-size:.8rem">Yesterday · {day.strftime('%a, %b %-d')}</span><strong style="font-size:1.1rem;color:#eef4ff">{headline}</strong></div>
<div style="display:flex;flex-wrap:wrap;gap:8px 20px;margin:8px 0">{''.join(chips)}</div><div style="font-size:.72rem;color:#a7b9d0">{note}</div></section>''',unsafe_allow_html=True)
    if missing:st.caption('Missing grading feeds: '+', '.join(missing)+'. Totals are incomplete.')
    if shown.empty:return
    with st.expander('Yesterday’s final scores & game recaps'):
        st.caption('Original saved picks only. NHL uses the experimental reference control; pending games and ties stay out of accuracy.')
        table_rows=weekly_game_table(shown)
        from game_status import score
        for index,r in enumerate(shown.sort_values(['start','created'],na_position='last').itertuples()):
            source=context(r.sport,r.game_id,r.home,r.away)
            if source and source.get('state')=='final':
                h,a=score(source.get('home_score')),score(source.get('away_score'))
                if h is not None and a is not None:table_rows.loc[index,'Final (away–home)']=f'{a}–{h}'
        st.dataframe(table_rows[['Game','Final (away–home)','Saved pick','Result']],hide_index=True,use_container_width=True,height=min(400,38+35*len(table_rows)))
        choices=list(shown.index)
        if st.session_state.get('yesterday_recap_game') not in choices:st.session_state['yesterday_recap_game']=choices[0]
        selected=st.selectbox('Read a game recap',choices,format_func=lambda i:f'{shown.loc[i,"sport"]} · {shown.loc[i,"away"]} @ {shown.loc[i,"home"]}',key='yesterday_recap_game')
        r=shown.loc[selected]
        details_button(r.sport,{**r.details,**r.to_dict()},'yesterday_recap_details',LABELS[r.group],settled=bool(r.settled or r.tie),now=now)

def render_overview(now=None):
    now=pd.Timestamp.now(tz='UTC') if now is None else ts(now)
    payload=load_overview()
    board,available,updates=prepare(payload,now)
    for i,r in board.iterrows():
        status=context(r.sport,r.game_id,r.home,r.away)
        if status:board.loc[i,'start']=ts(status['start_time_utc'])
    primary=board[board.apply(lambda r:PRIMARY[r.sport]==r.group,axis=1)] if len(board) else board
    total_graded=int(primary.settled.sum());saved=len(primary)
    st.markdown('''<style>
.desk-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:16px 0 24px}.desk-game{background:#111a26;border:1px solid #2b384b;border-radius:17px;padding:18px;min-width:0}.desk-top{display:flex;align-items:center;justify-content:space-between}.desk-sport{color:var(--accent);font-size:.72rem;font-weight:900;letter-spacing:.1em}.desk-state{font-size:.65rem;padding:4px 9px;border-radius:99px;background:#1d2a3b;color:#bcd3f2;font-weight:800}.desk-state.win{background:#123224;color:#8ce4b3}.desk-state.loss{background:#39212a;color:#ffb4c2}.desk-state.waiting{background:#372e1d;color:#f1d28f}.desk-time{font-size:.7rem;color:#a4b3c8;margin:12px 0 8px}.desk-match{font-size:1.15rem;font-weight:850;overflow-wrap:anywhere}.desk-match span{font-size:.8rem;color:#73869f}.desk-pick{display:flex;justify-content:space-between;align-items:end;gap:12px;border-top:1px solid #2a3649;margin-top:15px;padding-top:13px}.desk-pick small{display:block;font-size:.56rem;color:#9badc5;letter-spacing:.06em}.desk-pick strong{font-size:1.15rem;overflow-wrap:anywhere}.desk-prob{text-align:right;font-size:1.5rem;font-weight:850}.desk-detail{font-size:.7rem;color:#b9c6d8;margin-top:13px}@media(max-width:1000px){.desk-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.desk-grid{grid-template-columns:1fr}.desk-game{padding:16px}.st-key-bp_sport label{padding:7px 9px}.st-key-bp_sport [role="radiogroup"]{gap:4px}}
.ov-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:18px 0}.ov-sport{background:linear-gradient(140deg,#151e2b,#10151e);border:1px solid #2b3748;border-radius:20px;padding:22px;position:relative;overflow:hidden}.ov-sport:before{content:"";position:absolute;top:0;left:0;width:4px;height:100%;background:var(--accent)}.ov-top{display:flex;justify-content:space-between;gap:10px;align-items:center}.ov-name{font-size:1.35rem;font-weight:950;letter-spacing:-.04em;color:var(--accent)}.ov-tag{font-size:.61rem;font-weight:850;letter-spacing:.08em;border:1px solid #354155;border-radius:99px;padding:5px 9px;color:#c2cfe1;background:#192230}.ov-score{font-size:2.5rem;font-weight:1000;letter-spacing:-.06em;line-height:1.2;margin-top:16px;color:#f4f7fc}.ov-caption{font-size:.7rem;color:#aab9cd;margin-top:2px}.ov-details{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:18px 0}.ov-detail{background:#0d141e;border:1px solid #253143;border-radius:10px;padding:10px}.ov-detail b{font-size:1rem;color:#e2eaf6;display:block}.ov-detail span{font-size:.6rem;color:#91a2b9;text-transform:uppercase;letter-spacing:.04em}.ov-update{border-top:1px solid #283346;padding-top:12px;font-size:.72rem;color:#a4b4ca;display:flex;justify-content:space-between;gap:10px}.ov-status{color:#8bdab1}.ov-status.warning{color:#f4cc7b}.ov-status.unknown{color:#f0a8b1}.ov-table-wrap{border:1px solid #2c394e;border-radius:14px;overflow-x:auto;margin:14px 0}.ov-table{width:100%;border-collapse:collapse;font-size:.8rem;background:#101822;color:#e1e9f4}.ov-table th{text-align:left;padding:12px 14px;background:#182334;color:#a8bad2;font-size:.65rem;font-weight:900;letter-spacing:.06em;white-space:nowrap}.ov-table td{padding:13px 14px;border-top:1px solid #273448;white-space:nowrap}.ov-note{color:#a7b6cc;font-size:.8rem;line-height:1.5;margin:10px 0}.ov-table tbody tr:hover{background:#172230}.ov-meta{color:#93a5bc;font-size:.7rem}.st-key-overview_refresh button{color:#d5e5ff;background:#182841;border:1px solid #39557b}[data-testid="stWidgetLabel"] p,[data-testid="stRadio"] label p{color:#d9e2ef!important}[data-testid="stTabs"] [role="tab"] p{color:#bccbe0!important}[data-testid="stTabs"] [role="tab"][aria-selected="true"] p{color:#91bcff!important}[data-testid="stAlert"] p{color:#dce7f6!important}@media(max-width:1000px){.ov-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.ov-grid{grid-template-columns:1fr;gap:12px}.ov-sport{padding:18px}.ov-update{flex-wrap:wrap}.ov-score{font-size:2.1rem}}

/* Scope native Streamlit columns as well as the HTML cards. */
[class*="st-key-desk_details_row_"],[class*="st-key-remaining_details_row_"],[class*="st-key-recent_details_row_"],[class*="st-key-daily_details_row_"]{min-width:0;max-width:100%}
.desk-single,.desk-game{width:100%;box-sizing:border-box;max-width:100%}
.desk-top{gap:10px;flex-wrap:wrap}.desk-pick>div:first-child{min-width:0;flex:1}.desk-prob{flex-shrink:0;white-space:nowrap}.desk-prob small{white-space:normal}.desk-match{overflow-wrap:normal;word-break:normal}.desk-pick strong{overflow-wrap:normal;word-break:normal}.desk-bar{height:7px;border-radius:99px;background:#26354a;overflow:hidden;margin-top:13px}.desk-bar>div{height:100%;background:var(--accent);border-radius:inherit}.desk-game .bp-score{margin:10px 0;padding:12px}.desk-game .bp-confidence{font-size:.72rem;line-height:1.5}.desk-game .bp-confidence span{display:block;margin-top:5px}
@media(max-width:760px){
:is([class*="st-key-desk_details_row_"],[class*="st-key-remaining_details_row_"],[class*="st-key-recent_details_row_"],[class*="st-key-daily_details_row_"]) [data-testid="stHorizontalBlock"]{flex-direction:column!important;gap:16px!important}
:is([class*="st-key-desk_details_row_"],[class*="st-key-remaining_details_row_"],[class*="st-key-recent_details_row_"],[class*="st-key-daily_details_row_"]) [data-testid="stColumn"]{width:100%!important;min-width:100%!important;flex:1 1 100%!important}
.desk-game{padding:18px}.desk-pick strong{font-size:1.2rem}.desk-prob{font-size:1.6rem}
}
</style>''' ,unsafe_allow_html=True)
    missing=[name for name,key in [('NFL','nfl'),('CFB','cfb'),('NHL','nhl'),('NBA','nba')] if not available[key]]
    st.markdown(f'''<div class="hero"><div class="eyebrow">NFL · CFB · NHL · NBA</div><div class="hero-title">Your sports desk.</div><div class="hero-copy">Today’s matchups, saved predictions and settled results. Follow each sport’s live record and see how its probabilities hold up.</div><div class="stat-grid"><div class="stat"><div class="stat-v">{4-len(missing)} / 4</div><div class="stat-l">Feeds verified</div></div><div class="stat"><div class="stat-v">{saved}</div><div class="stat-l">Saved matchups</div></div><div class="stat"><div class="stat-v">{total_graded}</div><div class="stat-l">Finals graded</div></div><div class="stat"><div class="stat-v">Prospective</div><div class="stat-l">Live results only</div></div></div></div>''',unsafe_allow_html=True)
    if missing:st.warning('Live data unavailable for '+', '.join(missing)+'. Those records show — until they can be verified.')
    render_yesterday_recap(payload,now)
    tabs=st.tabs(['LIVE RECORDS','DAILY RESULTS','CONFIDENCE','RESEARCH'])
    with tabs[0]:
        cards=[]
        for sport,group in PRIMARY.items():
            key='nhl' if sport=='NHL' else sport.lower();ok=available[key];b=board[board.group==group];m=metrics(b);state,cls=freshness(sport,updates[sport],now)
            if not ok:state,cls='Feed unavailable','unknown'
            record=f"{m['wins']}–{m['losses']}" if ok else '—';accuracy=f"{m['accuracy']*100:.1f}%" if ok and m['games'] else '—';pending=len(b)-m['games']
            tag='FROZEN · RESEARCH' if sport=='NHL' else 'FROZEN V4' if sport=='NFL' else 'FROZEN V1'
            sub='Reference control · prospective research' if sport=='NHL' else 'Official prospective record'
            cards.append(f'<div class="ov-sport" style="--accent:{COLORS[sport]}"><div class="ov-top"><div class="ov-name">{sport}</div><div class="ov-tag">{tag}</div></div><div class="ov-score">{record}</div><div class="ov-caption">{sub}</div><div class="ov-details"><div class="ov-detail"><b>{m["games"] if ok else "—"}</b><span>Graded</span></div><div class="ov-detail"><b>{pending if ok else "—"}</b><span>Pending</span></div><div class="ov-detail"><b>{accuracy}</b><span>Accuracy</span></div></div><div class="ov-update"><span>{esc(ct(updates[sport]))}</span><span class="ov-status {cls}">{state}</span></div></div>')
        st.markdown('<div class="ov-grid">'+''.join(cards)+'</div>',unsafe_allow_html=True)
        columns=st.columns(4)
        for column,sport in zip(columns,PRIMARY):column.button('Open '+sport+' board',key='open_'+sport,on_click=open_board,args=(sport,),width='stretch')
        st.caption('Saved and graded totals count one primary forecast per matchup. NHL uses the research reference control; challengers are tracked separately.')
        st.markdown('<div class="section-title">Game center</div><div class="section-sub">Saved picks, clear results, all four sports · Central time</div>',unsafe_allow_html=True)
        f1,f2=st.columns([2,1])
        view=f1.selectbox('Show games',['Today','Results','Upcoming','Awaiting finals','All tracked'],key='desk_view')
        sport=f2.selectbox('Filter sport',['All sports',*PRIMARY],key='desk_sport')
        query=st.text_input('Find a matchup',placeholder='Search Troy, SEA, DET…',key='desk_search')
        personal=filter_favorites(primary,None,"overview_my_teams",home="home",away="away")
        shown=select_games(personal,view,sport,query,now)
        if shown.empty:st.info('No saved games match this view. Use Results for completed games or Upcoming for future picks.')
        else:
            render_game_cards(shown.head(24),now,'desk_details')
            if len(shown)>24:
                with st.expander(f'Show the remaining {len(shown)-24} games'):render_game_cards(shown.iloc[24:],now,'remaining_details')
        if view=='Today' and not query.strip():
            recent=select_games(personal,'Results',sport,'',now).head(6)
            if len(recent):
                st.markdown('<div class="section-title">Latest settled results</div>',unsafe_allow_html=True)
                render_game_cards(recent,now,'recent_details')
        st.caption('Win / Loss grades the saved pick. The game-state label comes from the score source; Win / Loss comes from the grading ledger. A final score can appear before grading. Result checks run about every 15 minutes; source and workflow delays can take longer. NBA excludes preseason.')
    with tabs[1]:
        render_daily_results(primary,available,now)
    with tabs[2]:
        st.markdown('<div class="section-title">Does confidence hold up?</div><div class="ov-note">Compare the confidence saved before each game with actual wins after grading. Empty bands stay unscored until results arrive.</div>',unsafe_allow_html=True)
        sport=st.selectbox('Sport to review',list(PRIMARY),key='overview_confidence_sport');group=PRIMARY[sport];b=board[board.group==group]
        if not available['nhl' if sport=='NHL' else sport.lower()]:st.warning('This sport’s live confidence data is unavailable.')
        else:
            bands=[(.5,.6,'50–59%'),(.6,.7,'60–69%'),(.7,.8,'70–79%'),(.8,.9,'80–89%'),(.9,1.01,'90–100%')];rows=[]
            for lo,hi,label in bands:
                section=b[b.confidence.ge(lo)&b.confidence.lt(hi)];m=metrics(section);scored=section[section.settled]
                rows.append([label,len(section)-m['games'],m['games'],f"{m['wins']}–{m['losses']}",f"{scored.confidence.mean()*100:.1f}%" if len(scored) else '—',f"{m['accuracy']*100:.1f}%" if m['games'] else '—'])
            st.markdown(table(['CONFIDENCE','PENDING','GRADED','RECORD','AVG SAVED CONFIDENCE','ACTUAL WIN RATE'],rows),unsafe_allow_html=True)
            m=metrics(b);cols=st.columns(2);cols[0].metric('Brier score',f"{m['brier']:.4f}" if m['games'] else '—');cols[1].metric('Log loss',f"{m['log_loss']:.4f}" if m['games'] else '—')
            st.caption('Lower Brier score and log loss mean better probability accuracy. A few games are too small a sample to justify changing weights.')
    with tabs[3]:
        st.markdown('<div class="section-title">Frozen challengers</div><div class="ov-note">These experiments have their own records. Parallel predictions for the same game never inflate the totals above.</div>',unsafe_allow_html=True)
        groups=['shadow','reference_control','decay2_logistic','linear_regulation_blend'];rows=[]
        for group in groups:
            key='shadow' if group=='shadow' else 'nhl';b=board[board.group==group];m=metrics(b);ok=available[key]
            rows.append([LABELS[group],len(b) if ok else '—',m['games'] if ok else '—',f"{m['wins']}–{m['losses']}" if ok else '—',f"{m['brier']:.4f}" if m['games'] and ok else '—'])
        st.markdown(table(['MODEL','SAVED','GRADED','RECORD','BRIER'],rows),unsafe_allow_html=True)
        st.caption('Candidate B uses verified snapshots captured after its artifact freeze. Its legacy batch is preserved outside this comparison. NHL candidates remain research models.')
        st.markdown('<div class="section-title">NHL goalie comparison</div><div class="ov-note">All three predictions use the same games and capture time. A game enters only when both starters have valid pregame confirmations.</div>',unsafe_allow_html=True)
        if not available['goalie']:st.warning('The goalie comparison feed is unavailable.')
        else:
            rows=[]
            for name in ('team_control','inferred_goalie','confirmed_goalie'):
                group='goalie_'+name;b=board[board.group==group];m=metrics(b);rows.append([LABELS[group],len(b),m['games'],f"{m['wins']}–{m['losses']}",f"{m['brier']:.4f}" if m['games'] else '—'])
            st.markdown(table(['PAIRED MODEL','SAVED PAIRS','GRADED','RECORD','BRIER'],rows),unsafe_allow_html=True)
            source=load_overview().get('goalie_update',{});stamp=ts(source.get('data',{}).get('as_of_utc')) if source.get('ok') else pd.NaT
            st.caption('Latest goalie comparison update: '+ct(stamp)+'. Formal review starts at 500 settled pairs; no automatic promotion.')
