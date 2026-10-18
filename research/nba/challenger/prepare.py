"""Audit only; no candidate fitting or evaluation in this entry point."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import argparse
import hashlib
import json
import sys
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from baseline import ROOT,load_games
from injuries import cutoff_for,report_files,load_report,choose_report,usable


def history():
    manifest_path=ROOT/'model/nba/v1/manifest.json'
    if not manifest_path.exists():manifest_path=ROOT/'runtime/nba/v1_manifest.json'
    manifest=json.loads(manifest_path.read_text())
    hashes={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in manifest['source_hashes']}
    if hashes!=manifest['source_hashes']:raise ValueError('V1 team source hashes changed')
    cache=ROOT/'runtime/nba/games.parquet'
    if cache.exists():return pd.read_parquet(cache)
    games,audit=load_games()
    if len(games)!=manifest['training_games']:raise ValueError('V1 eligible population differs')
    games.to_parquet(cache,index=False)
    (ROOT/'runtime/nba/team_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    return games


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--offline',action='store_true',help='Audit cached inputs only; never download')
    args=parser.parse_args()
    games=history();rows=games[games.season>=2021].to_dict('records');reports={}
    cache=ROOT/'runtime/nba/injuries';cache.mkdir(parents=True,exist_ok=True)
    for attempt in range(3):
        unresolved=[g for g in rows if not any(usable(reports.get(f,{}),cutoff_for(g['start_time'])) for f in report_files(cutoff_for(g['start_time'])))]
        files=sorted({report_files(cutoff_for(g['start_time']))[attempt] for g in unresolved})
        print(f'Report phase {attempt+1}: {len(files)} documents',flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs={pool.submit(load_report,f,cache,args.offline):f for f in files}
            for count,job in enumerate(as_completed(jobs),1):
                reports[jobs[job]]=job.result()
                if count%100==0:print(f'Parsed {count}/{len(files)} documents',flush=True)
    contexts={};coverage={}
    for g in rows:
        report,home,away=choose_report(g,reports)
        contexts[g['game_id']]=dict(filename=report.get('filename'),cutoff=cutoff_for(g['start_time']).isoformat(),home=home,away=away)
        season=str(g['season']);m=coverage.setdefault(season,dict(games=0,both_known=0,document_available=0))
        m['games']+=1;m['document_available']+=bool(report);m['both_known']+=bool(home['known'] and away['known'])
    receipts=[{k:v for k,v in report.items() if k!='teams'} for report in reports.values()]
    root=ROOT/'runtime/nba'
    (root/'availability_contexts.json').write_text(json.dumps(contexts)+'\n')
    (root/'report_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    (root/'availability_coverage.json').write_text(json.dumps(coverage,indent=2)+'\n')
    print(json.dumps(coverage,indent=2),flush=True)


if __name__=='__main__':main()
