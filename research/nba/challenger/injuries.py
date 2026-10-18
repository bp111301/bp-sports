"""Official NBA report receipts and conservative, timestamp-checked parsing."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import hashlib
import io
import json
import re
import subprocess
import unicodedata
import xml.etree.ElementTree as ET
import pandas as pd
from pypdf import PdfReader
import requests

STATUSES=('Out','Doubtful','Questionable','Probable','Available')
PARSER_VERSION=4
TEAMS=['Atlanta Hawks','Boston Celtics','Brooklyn Nets','Charlotte Hornets','Chicago Bulls',
       'Cleveland Cavaliers','Dallas Mavericks','Denver Nuggets','Detroit Pistons','Golden State Warriors',
       'Houston Rockets','Indiana Pacers','LA Clippers','Los Angeles Lakers','Memphis Grizzlies',
       'Miami Heat','Milwaukee Bucks','Minnesota Timberwolves','New Orleans Pelicans','New York Knicks',
       'Oklahoma City Thunder','Orlando Magic','Philadelphia 76ers','Phoenix Suns','Portland Trail Blazers',
       'Sacramento Kings','San Antonio Spurs','Toronto Raptors','Utah Jazz','Washington Wizards']
CODES=['ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GSW','HOU','IND','LAC','LAL','MEM',
       'MIA','MIL','MIN','NOP','NYK','OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS']


def canonical(value):
    value=unicodedata.normalize('NFKD',str(value))
    return re.sub('[^a-z0-9]','',value.lower())


TEAM_CODES={canonical(t):c for t,c in zip(TEAMS,CODES)}
TEAM_CODES[canonical('Los Angeles Clippers')]='LAC'


def code(value):
    return {'GS':'GSW','NY':'NYK','NO':'NOP','SA':'SAS','UTAH':'UTA','WSH':'WAS','PHO':'PHX','BRK':'BKN'}.get(value,value)


def player_key(value):
    value=str(value)
    if ',' in value:
        last,first=value.split(',',1);value=first+' '+last
    return canonical(value)


def cutoff_for(start):
    start=pd.Timestamp(start).tz_convert('America/New_York')
    evening=pd.Timestamp(str(start.date())+' 18:00',tz='America/New_York')
    return min(start-pd.Timedelta(hours=1),evening).tz_convert('UTC')


def report_files(cutoff):
    local=pd.Timestamp(cutoff).tz_convert('America/New_York').floor('h')-pd.Timedelta(hours=1)
    return ['Injury-Report_'+(local-pd.Timedelta(hours=i)).strftime('%Y-%m-%d_%I%p')+'.pdf' for i in range(3)]


def parse_bbox(xml):
    """Use physical PDF columns: text-layout character offsets vary by page."""
    root=ET.fromstring(xml);pages=[];positions=None;teams={};issues=[]
    day=match=team=None
    for page in root.iter():
        if page.tag.split('}')[-1]!='page':continue
        words=[dict(text=w.text or '',x=float(w.attrib['xMin']),y=(float(w.attrib['yMin'])+float(w.attrib['yMax']))/2)
               for w in page.iter() if w.tag.split('}')[-1]=='word']
        rows=[]
        for word in sorted(words,key=lambda w:(w['y'],w['x'])):
            if not rows or abs(word['y']-rows[-1][0]['y'])>2:rows.append([word])
            else:rows[-1].append(word)
        header_rows=set();banner_bottom=0
        for i,row in enumerate(rows):
            row.sort(key=lambda w:w['x']);text=' '.join(w['text'] for w in row)
            if 'Injury' in text and 'Report' in text:banner_bottom=max(w['y'] for w in row)+6
            compact=''.join(canonical(w['text']) for w in row)
            if 'gamedate' in compact and 'currentstatus' in compact:
                mapping=[]
                for w in row:mapping.extend([w['x']]*len(canonical(w['text'])))
                positions=[mapping[compact.index(label)] for label in ['gamedate','gametime','matchup','team','playername','currentstatus','reason']]+[10000]
                header_rows.add(i)
        if positions is None:raise ValueError('No physical table header')
        def parts(row):
            return [' '.join(w['text'] for w in sorted(row,key=lambda w:w['x']) if positions[j]-3<=w['x']<positions[j+1]-3) for j in range(7)]
        def footer(row):return bool(re.search(r'Page\s+\d+\s+of\s+\d+',' '.join(w['text'] for w in sorted(row,key=lambda w:w['x']))))
        # Gather wrapped team labels before consuming player rows.
        anchors={};team_buffer='';team_start=None;team_index=None
        for i,row in enumerate(rows):
            if i in header_rows or footer(row) or row[0]['y']<banner_bottom or row[0]['y']>float(page.attrib['height'])-25:continue
            value=parts(row)[3]
            if not value:continue
            key=canonical(value)
            if team_buffer and row[0]['y']-team_start<25:key=team_buffer+key
            if key in TEAM_CODES:
                anchors[team_index if team_buffer else i]=TEAM_CODES[key];team_buffer='';team_start=None;team_index=None
            elif any(t.startswith(key) for t in TEAM_CODES):
                if not team_buffer:team_start=row[0]['y'];team_index=i
                team_buffer=key
            else:issues.append('unrecognized_team:'+value);anchors[i]=None;team_buffer='';team_start=None;team_index=None
        status_rows=[(i,row[0]['y']) for i,row in enumerate(rows) if i not in header_rows and parts(row)[5] in STATUSES]
        name_cells={}
        for j,(i,y) in enumerate(status_rows):
            lo=max(y-12,(status_rows[j-1][1]+y)/2) if j else y-12
            hi=min(y+12,(status_rows[j+1][1]+y)/2) if j+1<len(status_rows) else y+12
            name_cells[i]=' '.join(w['text'] for w in sorted(words,key=lambda w:(w['y'],w['x']))
                                   if lo<w['y']<hi and positions[4]-3<=w['x']<positions[5]-3)
        for i,row in enumerate(rows):
            if i in header_rows or footer(row) or row[0]['y']<banner_bottom or row[0]['y']>float(page.attrib['height'])-25:continue
            p=parts(row);date_match=re.search(r'\d\d/\d\d/\d{4}',p[0])
            if date_match:
                next_day=datetime.strptime(date_match.group(),'%m/%d/%Y').date().isoformat()
                if next_day!=day:day=next_day;match=team=None
            m=re.search(r'([A-Z]{2,4})@([A-Z]{2,4})',p[2])
            if m:
                next_match=code(m[1])+'@'+code(m[2])
                if next_match!=match:match=next_match;team=None
            if i in anchors:team=anchors[i]
            if not (day and match and team):continue
            if team not in match.split('@'):
                issues.append('team_matchup_mismatch:'+team+':'+match);team=None;continue
            key='|'.join([day,match,team]);entry=teams.setdefault(key,dict(known=False,explicit_unknown=False,players=[]))
            rest=canonical(' '.join(p[4:]))
            if 'notyetsubmitted' in rest:entry.update(known=False,explicit_unknown=True);continue
            if canonical(p[4]) in ('none','noinjuries','noinjuriestoreport'):entry['known']=not entry['explicit_unknown']
            if p[5] in STATUSES:
                name=name_cells.get(i,'').strip()
                if not name:entry.update(known=False,explicit_unknown=True);issues.append('missing_name:'+key)
                else:entry['players'].append(dict(name=name,key=player_key(name),status=p[5]));entry['known']=not entry['explicit_unknown']
    for key,entry in teams.items():
        keys=[p['key'] for p in entry['players']]
        if len(keys)!=len(set(keys)):entry['known']=False;issues.append('duplicate_player:'+key)
    return teams,issues


def load_report(filename,cache,offline=False):
    url='https://ak-static.cms.nba.com/referee/injury/'+filename
    path=cache/filename;parsed=path.with_suffix('.json')
    if parsed.exists():
        try:
            saved=json.loads(parsed.read_text())
            if saved.get('parser_version')==PARSER_VERSION:return saved
        except json.JSONDecodeError:pass
    receipt=dict(filename=filename,url=url,status='unavailable',parser_version=PARSER_VERSION)
    try:
        if not path.exists():
            if offline:
                return {**receipt,'status':'not_retrieved','reason':'No local PDF or completed cached receipt; offline audit'}
            response=requests.get(url,timeout=(15,45))
            receipt['http_status']=response.status_code
            if response.status_code!=200:
                parsed.write_text(json.dumps(receipt)+'\n');return receipt
            if len(response.content)>5*1024*1024 or not response.content.startswith(b'%PDF'):
                raise ValueError('Invalid PDF response')
            path.write_bytes(response.content)
        raw=path.read_bytes();receipt.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        creation=PdfReader(io.BytesIO(raw)).metadata.creation_date
        if creation is None or creation.tzinfo is None:raise ValueError('Missing timezone-aware PDF creation timestamp')
        text=subprocess.run(['pdftotext','-layout',str(path),'-'],check=True,capture_output=True,text=True).stdout
        header=re.search(r'Injury\s*Report\s*:\s*(\d\d/\d\d/\d\d)\s+(\d\d:\d\d)\s*(AM|PM)',text)
        if not header:raise ValueError('Missing embedded publication timestamp')
        published=pd.Timestamp(datetime.strptime(' '.join(header.groups()),'%m/%d/%y %I:%M %p'),tz='America/New_York')
        xml=subprocess.run(['pdftotext','-bbox',str(path),'-'],check=True,capture_output=True,text=True).stdout
        teams,issues=parse_bbox(xml)
        receipt.update(published_at=published.tz_convert('UTC').isoformat(),teams=teams,parse_issues=issues)
        receipt['created_at']=pd.Timestamp(creation).tz_convert('UTC').isoformat()
        receipt['status']='parsed'
    except Exception as error:
        receipt.update(status='unavailable',error=str(error))
    parsed.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def usable(report,cutoff):
    if report.get('status')!='parsed' or report.get('parse_issues'):return False
    published=pd.Timestamp(report['published_at']);created=pd.Timestamp(report['created_at'])
    return published<=cutoff and created<=cutoff and abs(created-published)<=pd.Timedelta(minutes=5)


def contexts(game,report):
    matchup=code(game['away_team'])+'@'+code(game['home_team'])
    keys=[game['date']+'|'+matchup+'|'+code(game[side+'_team']) for side in ['home','away']]
    return [report.get('teams',{}).get(key,dict(known=False,players=[])) for key in keys]


def choose_report(game,reports):
    cutoff=cutoff_for(game['start_time'])
    for filename in report_files(cutoff):
        report=reports.get(filename,{})
        if usable(report,cutoff):
            home,away=contexts(game,report)
            # A partially submitted report is valid evidence of unknown status;
            # do not hunt for another snapshot based on which players are out.
            return report,home,away
    return {},dict(known=False,players=[]),dict(known=False,players=[])
