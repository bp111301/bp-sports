"""Fetch only protocol-approved source years and verify their recorded hashes."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import sys
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from baseline import ROOT


def main():
    manifest_path=ROOT/'model/nba/v1/manifest.json'
    if not manifest_path.exists():manifest_path=ROOT/'runtime/nba/v1_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    jobs=[]
    for relative,sha in manifest['source_hashes'].items():
        path=Path(relative);season=int(path.stem.split('_')[-1]);kind=path.stem.split('_')[0]
        if season not in range(2016,2026) or kind not in ('box','schedule'):raise ValueError('Unapproved V1 source')
        tag,stem=('espn_nba_team_boxscores','team_box') if kind=='box' else ('espn_nba_schedules','nba_schedule')
        url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/{tag}/{stem}_{season}.parquet'
        jobs.append((ROOT/path,url,sha))
    for source in json.loads((Path(__file__).parent/'PLAYER_SOURCES.json').read_text()):
        season=source['season']
        if season not in range(2020,2026):raise ValueError('Unapproved player source')
        jobs.append((ROOT/f'runtime/nba/player_box_{season}.parquet',source['url'],source['sha256']))
    def fetch(job):
        path,url,sha=job;path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            response=requests.get(url,timeout=(15,90));response.raise_for_status()
            content=response.content
            if hashlib.sha256(content).hexdigest()!=sha:raise ValueError('Downloaded source hash mismatch: '+str(path))
            path.write_bytes(content)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Cached source hash mismatch: '+str(path))
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,jobs))
    print('Verified 20 V1 team inputs and 6 player inputs; no 2026 inputs requested')


if __name__=='__main__':main()
