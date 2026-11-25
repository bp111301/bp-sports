"""Actual app feed loaders must prefer fresh NFL data over a stale checkout."""
import ast
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request

import pandas as pd


def loaders(urlopen):
    tree=ast.parse(Path('app.py').read_text())
    selected=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name in ['current_feed_text','load_csv','load_json'])
              or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NFL_LIVE_FILES' for t in n.targets))]
    namespace=dict(io=io,json=json,pd=pd,Request=Request,urlopen=urlopen,
                   st=SimpleNamespace(cache_data=lambda **kwargs:lambda f:f))
    exec(compile(ast.Module(body=selected,type_ignores=[]),'app.py','exec'),namespace)
    return namespace


def test_fresh_nfl_predictions_and_metadata_override_stale_host_checkout(tmp_path,monkeypatch):
    observed=[]
    def remote(request,**kwargs):
        observed.append(request.full_url)
        if request.full_url.endswith('.csv'):return io.BytesIO(b'game_id,v4_pick\n2026_12_GB_LA,LA\n')
        return io.BytesIO(b'{"week":12,"v4_adjusted":{"correct":67}}')
    load=loaders(remote)
    current=tmp_path/'data/current';current.mkdir(parents=True)
    (current/'website_feed.csv').write_text('game_id,v4_pick\n2026_11_OLD,GB\n')
    (current/'prediction_metadata.json').write_text('{"week":11}')
    monkeypatch.chdir(tmp_path)
    assert load['load_csv']('data/current/website_feed.csv').iloc[0].game_id=='2026_12_GB_LA'
    assert load['load_json']('data/current/prediction_metadata.json')['week']==12
    assert load['load_json']('data/ledger/summary.json')['v4_adjusted']['correct']==67
    assert len(observed)==3 and all('/bp111301/bp-sports/main/' in u for u in observed)


def test_remote_outage_keeps_existing_local_fallback_and_history_stays_local(tmp_path,monkeypatch):
    calls=[]
    def unavailable(request,**kwargs):calls.append(request.full_url);raise TimeoutError('provider unavailable')
    load=loaders(unavailable)
    current=tmp_path/'data/current';current.mkdir(parents=True)
    (current/'website_feed.csv').write_text('game_id\nsaved\n')
    (current/'prediction_metadata.json').write_text('{"week":11}')
    (tmp_path/'history.csv').write_text('record\nunchanged\n')
    monkeypatch.chdir(tmp_path)
    assert load['load_csv']('data/current/website_feed.csv').iloc[0].game_id=='saved'
    assert load['load_json']('data/current/prediction_metadata.json')['week']==11
    assert load['load_csv']('history.csv').iloc[0].record=='unchanged'
    assert len(calls)==2
