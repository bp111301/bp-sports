"""Hash-validated, disposable caches for forward CBB state replay."""
import gzip
import hashlib
import json
from pathlib import Path
import pandas as pd
import develop as v1
from run import player_games


def load_season(season, cache, refresh=False):
    paths = [cache/f'{kind}_{season}.parquet' for kind in ['schedule','box','player_box']]
    cached = cache/f'shadow_state_{season}.json.gz'
    parser_hash = hashlib.sha256(Path(v1.__file__).read_bytes()+Path(__file__).read_bytes()+
                                 Path(__file__).with_name('run.py').read_bytes()).hexdigest()
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths] if all(p.exists() for p in paths) else None
    if cached.exists() and hashes and not refresh:
        data = json.loads(gzip.decompress(cached.read_bytes()))
        if data['source_hashes'] == hashes and data['parser_hash'] == parser_hash:
            for g in data['games']:
                g['start'],g['day'] = pd.Timestamp(g['start']),pd.Timestamp(g['day'])
            return data['games'], {(gid,team):minutes for gid,team,minutes in data['players']}, data['audit']
    if refresh:
        v1.fetch(season,'schedule',cache,refresh=True)
        v1.fetch(season,'box',cache,refresh=True)
    games, audit = v1.season_games(season,cache)
    players, player_audit = player_games(season,cache,games,refresh=refresh)
    audit['players'] = player_audit
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    data = dict(parser_hash=parser_hash,source_hashes=hashes,
                games=[{**g,'start':g['start'].isoformat(),'day':g['day'].isoformat()} for g in games],
                players=[[gid,team,minutes] for (gid,team),minutes in players.items()],audit=audit)
    cached.write_bytes(gzip.compress(json.dumps(data).encode(),mtime=0))
    return games,players,audit


def load_history(cache, seasons):
    games,players,audits = [],{},[]
    for season in seasons:
        batch,rotation,audit = load_season(season,cache)
        games.extend(batch);players.update(rotation);audits.append(audit)
        print(f'Loaded ending-year {season}: {len(batch)} regular-season games',flush=True)
    return games,players,audits
