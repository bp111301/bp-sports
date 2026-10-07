"""Read-only cross-sport prospective dashboard. Parallel experiments stay separate."""
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
import io,json,math,html
import pandas as pd
import streamlit as st
from nhl_ui import audit_note

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
COLUMNS=['game_id','sport','group','home','away','p','created','start','settled','y']

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

def row(game_id,sport,group,home,away,p,created,start,settled=False,y=None):
    return dict(game_id=str(game_id),sport=sport,group=group,home=home,away=away,p=float(p),created=ts(created),start=ts(start),settled=bool(settled),y=y)

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
            rows.append(row(r['game_id'],'NFL','nfl',r['home_team'],r['away_team'],p,r['captured_at_utc'],None,final,int(h>a) if final else None))
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
            rows.append(row(r['game_id'],'CFB',key,r['home_team'],r['away_team'],r['home_win_prob'],r['snapshot_created_utc'],start,final,y))
    elif key=='nhl':
        for r in data:
            if r.get('bundle_sha256')!=FROZEN_NHL:raise ValueError('NHL model identity mismatch')
            if r['candidate'] not in ('reference_control','decay2_logistic','linear_regulation_blend') or r['status'] not in ('pending','settled'):continue
            rows.append(row(r['game_id'],'NHL',r['candidate'],r['home_team'],r['away_team'],r['home_win_prob'],r['created_at_utc'],r['start_time_utc'],r['status']=='settled',pd.to_numeric(r.get('actual_home_win'),errors='coerce')))
    elif key=='goalie':
        for r in data:
            if r.get('status') not in ('pending','settled'):continue
            probabilities=r['probabilities']
            if set(probabilities)!={'team_control','inferred_goalie','confirmed_goalie'}:raise ValueError('Incomplete goalie comparison')
            for name,p in probabilities.items():rows.append(row(r['game_id'],'NHL','goalie_'+name,r['home_team'],r['away_team'],p,r['created_at_utc'],r['start_time_utc'],r['status']=='settled',r.get('actual_home_win')))
    elif key=='nba':
        if data.get('feed_status')!='enabled':raise ValueError('NBA feed unavailable')
        if data.get('bundle_sha256')!=FROZEN_NBA:raise ValueError('NBA model identity mismatch')
        for r in data.get('predictions',[]):
            if r.get('season')!=2027 or r.get('season_type')!=2 or r.get('status') not in ('pending','settled'):continue
            if r.get('bundle_sha256')!=data.get('bundle_sha256'):raise ValueError('NBA model identity mismatch')
            rows.append(row(r['game_id'],'NBA','nba',r['home_team'],r['away_team'],r['home_win_prob'],r['created_at_utc'],r['start_time_utc'],r['status']=='settled',r.get('actual_home_win')))
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

def open_board(sport):st.session_state['bp_sport']=sport

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
        state,cls=game_state(r,now);pick=r.home if r.p>=.5 else r.away
        winner=r.home if r.y==1 else r.away
        detail='Final winner: '+str(winner) if r.settled else 'Result pending · excluded from record' if cls=='waiting' else 'Saved before game time'
        time=ct(r.start) if pd.notna(r.start) else 'Kickoff time on NFL board'
        note=audit_note(r.game_id,FROZEN_NHL) if r.sport=='NHL' else None
        audit=f'<div class="desk-detail" style="color:#f1d28f">Input concern · missing power-play feature. <a href="{esc(note["report_url"])}" target="_blank" rel="noopener noreferrer">View audit</a></div>' if note else ''
        cards.append(f'<article class="desk-game" style="--accent:{COLORS[r.sport]}"><div class="desk-top"><span class="desk-sport">{esc(r.sport)}</span><span class="desk-state {cls}">{state}</span></div><div class="desk-time">{esc(time)}</div><div class="desk-match">{esc(r.away)} <span>@</span> {esc(r.home)}</div><div class="desk-pick"><div><small>SAVED PICK</small><strong>{esc(pick)}</strong></div><div class="desk-prob">{r.confidence*100:.1f}%<small>MODEL PROBABILITY</small></div></div><div class="desk-detail">{esc(detail)}</div>{audit}</article>')
    return '<div class="desk-grid">'+''.join(cards)+'</div>'

def render_overview(now=None):
    now=pd.Timestamp.now(tz='UTC') if now is None else ts(now)
    if st.button('Refresh all sports',key='overview_refresh'):load_overview.clear()
    board,available,updates=prepare(load_overview(),now)
    primary=board[board.apply(lambda r:PRIMARY[r.sport]==r.group,axis=1)] if len(board) else board
    total_graded=int(primary.settled.sum());saved=len(primary)
    st.markdown('''<style>
.desk-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:16px 0 24px}.desk-game{background:#111a26;border:1px solid #2b384b;border-radius:17px;padding:18px;min-width:0}.desk-top{display:flex;align-items:center;justify-content:space-between}.desk-sport{color:var(--accent);font-size:.72rem;font-weight:900;letter-spacing:.1em}.desk-state{font-size:.65rem;padding:4px 9px;border-radius:99px;background:#1d2a3b;color:#bcd3f2;font-weight:800}.desk-state.win{background:#123224;color:#8ce4b3}.desk-state.loss{background:#39212a;color:#ffb4c2}.desk-state.waiting{background:#372e1d;color:#f1d28f}.desk-time{font-size:.7rem;color:#a4b3c8;margin:12px 0 8px}.desk-match{font-size:1.15rem;font-weight:850;overflow-wrap:anywhere}.desk-match span{font-size:.8rem;color:#73869f}.desk-pick{display:flex;justify-content:space-between;align-items:end;gap:12px;border-top:1px solid #2a3649;margin-top:15px;padding-top:13px}.desk-pick small{display:block;font-size:.56rem;color:#9badc5;letter-spacing:.06em}.desk-pick strong{font-size:1.15rem;overflow-wrap:anywhere}.desk-prob{text-align:right;font-size:1.5rem;font-weight:850}.desk-detail{font-size:.7rem;color:#b9c6d8;margin-top:13px}@media(max-width:1000px){.desk-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.desk-grid{grid-template-columns:1fr}.desk-game{padding:16px}.st-key-bp_sport label{padding:7px 9px}.st-key-bp_sport [role="radiogroup"]{gap:4px}}
.ov-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:18px 0}.ov-sport{background:linear-gradient(140deg,#151e2b,#10151e);border:1px solid #2b3748;border-radius:20px;padding:22px;position:relative;overflow:hidden}.ov-sport:before{content:"";position:absolute;top:0;left:0;width:4px;height:100%;background:var(--accent)}.ov-top{display:flex;justify-content:space-between;gap:10px;align-items:center}.ov-name{font-size:1.35rem;font-weight:950;letter-spacing:-.04em;color:var(--accent)}.ov-tag{font-size:.61rem;font-weight:850;letter-spacing:.08em;border:1px solid #354155;border-radius:99px;padding:5px 9px;color:#c2cfe1;background:#192230}.ov-score{font-size:2.5rem;font-weight:1000;letter-spacing:-.06em;line-height:1.2;margin-top:16px;color:#f4f7fc}.ov-caption{font-size:.7rem;color:#aab9cd;margin-top:2px}.ov-details{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:18px 0}.ov-detail{background:#0d141e;border:1px solid #253143;border-radius:10px;padding:10px}.ov-detail b{font-size:1rem;color:#e2eaf6;display:block}.ov-detail span{font-size:.6rem;color:#91a2b9;text-transform:uppercase;letter-spacing:.04em}.ov-update{border-top:1px solid #283346;padding-top:12px;font-size:.72rem;color:#a4b4ca;display:flex;justify-content:space-between;gap:10px}.ov-status{color:#8bdab1}.ov-status.warning{color:#f4cc7b}.ov-status.unknown{color:#f0a8b1}.ov-table-wrap{border:1px solid #2c394e;border-radius:14px;overflow-x:auto;margin:14px 0}.ov-table{width:100%;border-collapse:collapse;font-size:.8rem;background:#101822;color:#e1e9f4}.ov-table th{text-align:left;padding:12px 14px;background:#182334;color:#a8bad2;font-size:.65rem;font-weight:900;letter-spacing:.06em;white-space:nowrap}.ov-table td{padding:13px 14px;border-top:1px solid #273448;white-space:nowrap}.ov-note{color:#a7b6cc;font-size:.8rem;line-height:1.5;margin:10px 0}.ov-table tbody tr:hover{background:#172230}.ov-meta{color:#93a5bc;font-size:.7rem}.st-key-overview_refresh button{color:#d5e5ff;background:#182841;border:1px solid #39557b}[data-testid="stWidgetLabel"] p,[data-testid="stRadio"] label p{color:#d9e2ef!important}[data-testid="stTabs"] [role="tab"] p{color:#bccbe0!important}[data-testid="stTabs"] [role="tab"][aria-selected="true"] p{color:#91bcff!important}[data-testid="stAlert"] p{color:#dce7f6!important}@media(max-width:1000px){.ov-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.ov-grid{grid-template-columns:1fr;gap:12px}.ov-sport{padding:18px}.ov-update{flex-wrap:wrap}.ov-score{font-size:2.1rem}}
</style><div class="bp-nav"><div class="bp-logo"><div class="bp-mark">BP</div><div><div class="bp-wordmark">B.P. <span>SPORTS</span></div><div class="bp-kicker">THE LIVE PERFORMANCE BOARD</div></div></div><div class="live-pill"><span class="live-dot"></span> WEIGHTS FROZEN</div></div>''',unsafe_allow_html=True)
    missing=[name for name,key in [('NFL','nfl'),('CFB','cfb'),('NHL','nhl'),('NBA','nba')] if not available[key]]
    st.markdown(f'''<div class="hero"><div class="eyebrow">NFL · CFB · NHL · NBA</div><div class="hero-title">Your sports desk.</div><div class="hero-copy">Today’s matchups, saved predictions and settled results. Follow each sport’s live record and see how its probabilities hold up.</div><div class="stat-grid"><div class="stat"><div class="stat-v">{4-len(missing)} / 4</div><div class="stat-l">Feeds verified</div></div><div class="stat"><div class="stat-v">{saved}</div><div class="stat-l">Saved matchups</div></div><div class="stat"><div class="stat-v">{total_graded}</div><div class="stat-l">Finals graded</div></div><div class="stat"><div class="stat-v">Prospective</div><div class="stat-l">Live results only</div></div></div></div>''',unsafe_allow_html=True)
    if missing:st.warning('Live data unavailable for '+', '.join(missing)+'. Those records show — until they can be verified.')
    tabs=st.tabs(['LIVE RECORDS','CONFIDENCE','RESEARCH'])
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
        shown=select_games(primary,view,sport,query,now)
        if shown.empty:st.info('No saved games match this view. Use Results for completed games or Upcoming for future picks.')
        else:
            st.markdown(game_cards(shown.head(24),now),unsafe_allow_html=True)
            if len(shown)>24:
                with st.expander(f'Show the remaining {len(shown)-24} games'):st.markdown(game_cards(shown.iloc[24:],now),unsafe_allow_html=True)
        if view=='Today' and not query.strip():
            recent=select_games(primary,'Results',sport,'',now).head(6)
            if len(recent):
                st.markdown('<div class="section-title">Latest settled results</div>',unsafe_allow_html=True)
                st.markdown(game_cards(recent,now),unsafe_allow_html=True)
        st.caption('Win / Loss grades the saved pick. Awaiting final means the game has started; a confirmed final has not been graded yet. Result checks run about every 15 minutes; source and workflow delays can take longer. NBA excludes preseason.')
    with tabs[1]:
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
    with tabs[2]:
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
