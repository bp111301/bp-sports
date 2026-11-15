"""Fail a publishing job if it changes an existing forecast or frozen artifact."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import io
import json
from pathlib import Path
import subprocess

FOOTBALL_RESULTS={'status','settled','home_points_final','away_points_final','actual_winner',
                  'correct','brier','settled_at_utc','schedule_kickoff_utc'}
RULES={
    'data/ledger/prediction_ledger.csv':(('prediction_id',),{'actual_home_score','actual_away_score','settlement_status','scored_at_utc'}),
    'data/cfb/ledger/prediction_ledger.csv':(('prediction_id',),FOOTBALL_RESULTS),
    'data/cfb/v2_shadow/verified_prediction_ledger.csv':(('prediction_id',),FOOTBALL_RESULTS),
    'data/nhl/v2_research/prediction_ledger.csv':(('game_id','candidate'),{'status','actual_home_win','settled_at_utc'}),
    'data/nhl/goalie_experiment/paired_ledger.jsonl':(('game_id',),{'status','actual_home_win','settled_at_utc'}),
    'data/nba/prospective/predictions.jsonl':(('game_id',),set()),
    'data/nba/prospective/results.jsonl':(('game_id',),set()),
    'data/cbb/prospective/prediction_ledger.json':(('prediction_id',),{
        'status','actual_home_win','home_score','away_score','actual_winner','correct','brier','log_loss',
        'verified_start_time_utc','settled_at_utc','result_source_url','result_source_event_sha256'}),
}


def records(path,text):
    if path.endswith('.csv'):return list(csv.DictReader(io.StringIO(text)))
    if path.endswith('.jsonl'):return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def equivalent(a,b):
    if a==b:return True
    # CSV writers may change numeric spelling, but never the numeric value.
    if not isinstance(a,str) or not isinstance(b,str):return False
    try:
        left,right=Decimal(a),Decimal(b)
        return left.is_finite() and right.is_finite() and left==right
    except InvalidOperation:return False


def verify_rows(before,after,keys,mutable):
    def index(rows):
        result={}
        for row in rows:
            identity=tuple(str(row[k]) for k in keys)
            if identity in result:raise ValueError('Duplicate forecast identity: '+str(identity))
            result[identity]=row
        return result
    old,new=index(before),index(after)
    for identity,row in old.items():
        if identity not in new:raise ValueError('Saved forecast removed: '+str(identity))
        for field,value in row.items():
            if field not in mutable and (field not in new[identity] or not equivalent(value,new[identity][field])):
                raise ValueError('Saved forecast changed: '+str(identity)+' '+field)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='HEAD');args=parser.parse_args()
    changed=subprocess.check_output(['git','diff','--name-only',args.base],text=True).splitlines()
    for path in changed:
        if path.startswith('model/') or (path.startswith('research/') and '/results/' in path):
            raise SystemExit('Frozen model or historical evaluation changed: '+path)
    for path,(keys,mutable) in RULES.items():
        old=subprocess.run(['git','show',args.base+':'+path],capture_output=True,text=True)
        if old.returncode!=0:continue
        if not Path(path).exists():raise SystemExit('Saved ledger removed: '+path)
        verify_rows(records(path,old.stdout),records(path,Path(path).read_text()),keys,mutable)
    print('Existing forecast fields, model artifacts and historical evaluations are preserved.')


if __name__=='__main__':main()
