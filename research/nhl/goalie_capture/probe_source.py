"""Inspect public starting-goalie page structure, excluding article text."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
from pathlib import Path

class NextData(HTMLParser):
    def __init__(self):super().__init__();self.active=False;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('id')=='__NEXT_DATA__':self.active=True
    def handle_endtag(self,tag):
        if tag=='script':self.active=False
    def handle_data(self,text):
        if self.active:self.parts.append(text)

def page_data(html):
    p=NextData();p.feed(html)
    if not p.parts:raise ValueError('Missing public page data; schema not supported')
    return json.loads(''.join(p.parts))['props']['pageProps']

def structure(value,depth=0):
    if depth>8:return type(value).__name__
    if isinstance(value,dict):return {k:('text omitted' if any(s in k.lower() for s in ['description','content','body','excerpt','analysis','text','title','headline']) else structure(v,depth+1)) for k,v in value.items()}
    if isinstance(value,list):return {'length':len(value),'first':structure(value[0],depth+1) if value else None}
    if isinstance(value,str) and len(value)>100:return 'long string omitted'
    return value

if __name__=='__main__':
    import requests
    day=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    url=f'https://www.dailyfaceoff.com/starting-goalies/{day}'
    response=requests.get(url,timeout=45,headers={'User-Agent':'BP-Sports-Research/1.0'});response.raise_for_status()
    result={'source_url':url,'status_code':response.status_code,'schema':structure(page_data(response.text))}
    out=Path('research/nhl/goalie_capture/source_schema.json');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
