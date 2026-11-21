"""The live API may cap a page even when its requested limit means all rows."""
import importlib.util
import json
from pathlib import Path
from urllib.parse import parse_qs,urlparse

import pytest

spec=importlib.util.spec_from_file_location('nhl_stats',Path(__file__).with_name('nhl_stats.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_server_capped_pages_are_complete_and_all_receipts_are_retained():
    rows=[{'gameId':i//2,'teamId':i%2} for i in range(716)];calls=[]
    def fetch(url):
        q=parse_qs(urlparse(url).query);start=int(q['start'][0]);calls.append(start)
        assert json.loads(q['sort'][0])==[{'property':'gameId','direction':'ASC'},{'property':'teamId','direction':'ASC'}]
        # Simulate a provider page cap smaller than the requested page size.
        return json.dumps({'data':rows[start:start+73],'total':len(rows)}),{'url':url,'sha256':str(start)}
    frame,receipts=m.report_rows('summary',fetch)
    assert frame.to_dict('records')==rows and len(receipts)==10
    assert calls==list(range(0,716,73))
    assert [r['sha256'] for r in receipts]==list(map(str,calls))


@pytest.mark.parametrize('mode',['duplicate','empty','changing_total','invalid_total','excess'])
def test_incomplete_or_unstable_sources_never_reach_forecasting(mode):
    def fetch(url):
        start=int(parse_qs(urlparse(url).query)['start'][0]);total=3
        page=[dict(gameId=1,teamId=1)]
        if start:
            page=[dict(gameId=2,teamId=2)]
            if mode=='duplicate':page=[dict(gameId=1,teamId=1)]
            elif mode=='empty':page=[]
            elif mode=='changing_total':total=4
            elif mode=='invalid_total':total='3'
            elif mode=='excess':page=[dict(gameId=i,teamId=i) for i in range(2,6)]
        return json.dumps(dict(data=page,total=total)),{}
    with pytest.raises(ValueError):m.report_rows('powerplay',fetch)


def test_empty_report_terminates_without_requesting_another_page():
    calls=[]
    def fetch(url):calls.append(url);return json.dumps(dict(total=0,data=[])),{'url':url}
    frame,receipts=m.report_rows('penaltykill',fetch)
    assert frame.empty and len(calls)==len(receipts)==1
