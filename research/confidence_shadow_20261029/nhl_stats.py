"""Read complete current-season official NHL reports, with per-page receipts."""
import json
from urllib.parse import urlencode

import pandas as pd


def report_rows(report,fetch,season='20262027',page_size=100):
    if report not in ('summary','powerplay','penaltykill'):
        raise ValueError('Unsupported NHL team report')
    rows=[];receipts=[];seen=set();total=None
    while total is None or len(rows)<total:
        query={'isAggregate':'false','isGame':'true','start':len(rows),'limit':page_size,
               'factCayenneExp':'gamesPlayed>=1','cayenneExp':f'seasonId={season} and gameTypeId=2',
               'sort':json.dumps([{'property':'gameId','direction':'ASC'},
                                  {'property':'teamId','direction':'ASC'}],separators=(',',':'))}
        url='https://api.nhle.com/stats/rest/en/team/'+report+'?'+urlencode(query)
        raw,receipt=fetch(url);data=json.loads(raw)
        count=data.get('total');page=data.get('data')
        if isinstance(count,bool) or not isinstance(count,int) or not 0<=count<=10000 or not isinstance(page,list):
            raise ValueError('Invalid official NHL report pagination')
        if total is not None and count!=total:
            raise ValueError('Official NHL report changed during pagination; retry a fresh snapshot')
        total=count
        if not page and len(rows)<total:
            raise ValueError('Official NHL report truncated before advertised total')
        for row in page:
            identity=(int(row['gameId']),int(row['teamId']))
            if identity in seen:
                raise ValueError('Duplicate official NHL report identity across pages')
            seen.add(identity)
        rows.extend(page);receipts.append(receipt)
        if len(rows)>total:
            raise ValueError('Official NHL report exceeds advertised total')
    return pd.DataFrame(rows),receipts
