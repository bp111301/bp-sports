"""Replay existing input receipts; never create or backfill a shadow forecast."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE));import events

def main():
 a=argparse.ArgumentParser();a.add_argument('--reference-python',required=True);a.add_argument('--receipts',default=str(ROOT/'data/cfb/input_receipts/observations.jsonl'));a.add_argument('--out',default=str(ROOT/'runtime/confidence_shadow/reference_replay.json'));args=a.parse_args()
 path=Path(args.receipts);original=path.read_bytes();rows=[]
 for line in original.decode().splitlines():
  r=json.loads(line);digest=r.pop('receipt_sha256')
  if events.digest(r)!=digest:raise ValueError('Original input receipt digest failed')
  rows.append(r)
 if not rows:raise ValueError('No original input receipts to validate')
 payload={'sport':'cfb_replay','context':[r['feature_vectors']['context'] for r in rows],'prior':[r['feature_vectors']['prior'] for r in rows]}
 out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);inp=out.with_suffix('.input.json');result=out.with_suffix('.result.json');inp.write_text(events.canonical(payload))
 subprocess.run([args.reference_python,str(HERE/'reference_worker.py'),'--input',str(inp),'--output',str(result)],check=True,timeout=120)
 reference=json.loads(result.read_text());p=np.asarray(reference['probabilities']);old=np.array([r['home_win_prob'] for r in rows]);delta=float(np.max(np.abs(p-old)))
 if not np.allclose(p,old,rtol=0,atol=1e-12):raise ValueError('Original CFB reference replay failed')
 if path.read_bytes()!=original:raise ValueError('Original receipts changed')
 proof={'reference_receipts_replayed':len(rows),'max_abs_probability_difference':delta,'original_receipt_file_sha256':hashlib.sha256(original).hexdigest(),'reference_bundle_sha256':reference['reference_bundle_sha256'],'producer_versions':reference['producer_versions'],'backfilled_shadow_forecasts':0}
 out.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2))
if __name__=='__main__':main()
