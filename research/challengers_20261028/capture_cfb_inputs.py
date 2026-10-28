"""Separate append-only input receipts for freshly built frozen CFB V1 slates."""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import joblib,numpy as np,pandas as pd
import cfb

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(data):return hashlib.sha256(data).hexdigest()
def timestamp(value):return pd.to_datetime(value,utc=True,errors='coerce')
def values(row,features):return {f:None if pd.isna(row[f]) else float(row[f]) for f in features}
def receipt_payloads(predictions,ledger,raw,bundle,source_hashes,model_sha,now):
    if predictions.game_id.duplicated().any() or raw.game_id.duplicated().any() or ledger.game_id.duplicated().any():raise ValueError('Duplicate source or forecast game IDs')
    if bundle.get('version')!='CFB_V1':raise ValueError('Wrong frozen CFB version')
    if raw.season.ne(2026).any():raise ValueError('Wrong live input season')
    generated=timestamp(predictions.snapshot_created_utc)
    if generated.isna().any() or generated.gt(now).any() or (now-generated).gt(pd.Timedelta(minutes=10)).any():raise ValueError('Input receipts require the fresh same-job prediction slate')
    ids=predictions.game_id.astype(str).tolist();lookup=raw.set_index(raw.game_id.astype(str));selected=lookup.loc[ids].reset_index(drop=True)
    fx=cfb.base.build_matrix(selected);px=cfb.pri.matrix(selected,float(bundle['prior_k']));cf=list(bundle['context_features']);pf=list(bundle['prior_features'])
    pc=bundle['context_model'].predict_proba(fx[cf])[:,1];pp=bundle['prior_model'].predict_proba(px[pf])[:,1];replay=float(bundle['context_weight'])*pc+float(bundle['prior_weight'])*pp
    saved=pd.to_numeric(predictions.home_win_prob).to_numpy(float)
    if not np.isfinite(saved).all() or not np.allclose(saved,replay,atol=1e-12,rtol=0):raise ValueError('Input replay does not match the saved current forecast')
    old=ledger.set_index(ledger.game_id.astype(str));records=[]
    for i,r in enumerate(predictions.to_dict('records')):
        gid=str(r['game_id']);start=timestamp(r['kickoff_utc']);created=timestamp(r['snapshot_created_utc'])
        if pd.isna(start) or not created<start or start<=now:raise ValueError('Late or invalid CFB capture')
        original=old.loc[gid]
        if (str(original.home_team),str(original.away_team))!=(str(r['home_team']),str(r['away_team'])):raise ValueError('Ledger team identity mismatch')
        first=timestamp(original.snapshot_created_utc)==created
        records.append({'receipt_key':str(r['prediction_id'])+':'+created.isoformat(),'prediction_id':str(r['prediction_id']),'game_id':gid,'model_version':'CFB_V1','bundle_sha256':model_sha,'forecast_captured_at_utc':created.isoformat(),'observed_at_utc':now.isoformat(),'kickoff_utc':start.isoformat(),'home_team':str(r['home_team']),'away_team':str(r['away_team']),'receipt_role':'official_first_capture_inputs' if first else 'later_refresh_inputs_not_original_forecast','official_first_captured_at_utc':timestamp(original.snapshot_created_utc).isoformat(),'home_win_prob':float(saved[i]),'component_probabilities':{'context':float(pc[i]),'prior':float(pp[i])},'component_weights':{'context':float(bundle['context_weight']),'prior':float(bundle['prior_weight'])},'feature_vectors':{'context':values(fx.iloc[i],cf),'prior':values(px.iloc[i],pf)},'source_sha256':source_hashes})
    return records
def append_receipts(path,records):
    path=Path(path);known={}
    if path.exists():
        for line in path.read_text().splitlines():
            r=json.loads(line);digest=r.pop('receipt_sha256')
            if sha(canonical(r).encode())!=digest or r['receipt_key'] in known:raise ValueError('Existing input receipt integrity failure')
            known[r['receipt_key']]=r
    additions=[]
    for record in records:
        old=known.get(record['receipt_key'])
        if old is not None:
            if {k:v for k,v in old.items() if k!='observed_at_utc'}!={k:v for k,v in record.items() if k!='observed_at_utc'}:raise ValueError('Cannot rewrite a captured input receipt')
            continue
        known[record['receipt_key']]=record;additions.append({**record,'receipt_sha256':sha(canonical(record).encode())})
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:
        for record in additions:f.write(canonical(record)+'\n')
    return len(additions)
def coverage(schedule,raw,predictions,now):
    start=pd.to_datetime(schedule.start_date,utc=True,format='mixed',errors='coerce');future=schedule[start.gt(now)&start.le(now+pd.Timedelta(days=8))].copy()
    truth=lambda s:s.astype(str).str.lower().isin(['true','1','1.0'])
    source=set(raw.game_id.astype(str));saved=set(predictions.game_id.astype(str));groups={}
    for label,mask in [('fbs_vs_fbs',truth(future.fbs_game)),('fbs_vs_fcs',truth(future.fbs_participant)&~truth(future.fbs_game))]:
        x=future[mask];ids=set(x.game_id.astype(str));groups[label]={'scheduled_games':len(x),'missing_feature_game_ids':sorted(ids-source),'missing_current_forecast_game_ids':sorted(ids-saved)}
    return {'checked_at_utc':now.isoformat(),'horizon_days':8,'scope':'source and current-slate coverage; no forecasts invented','groups':groups}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--predictions',default='data/cfb/current/predictions.csv');ap.add_argument('--ledger',default='data/cfb/ledger/prediction_ledger.csv');ap.add_argument('--raw',default='runtime/cfb/matchup_line/cfb_matchup_line_2026.csv');ap.add_argument('--schedule',default='runtime/cfb/schedules/cfb_schedules_2026.csv.gz');ap.add_argument('--out-dir',default='data/cfb/input_receipts');a=ap.parse_args()
    now=pd.Timestamp.now(tz='UTC');bundle_path=Path('model/cfb/v1/frozen_bundle.joblib');manifest=json.loads(bundle_path.with_name('bundle_manifest.json').read_text());model_sha=sha(bundle_path.read_bytes())
    if model_sha!=manifest['sha256']:raise ValueError('Frozen CFB bundle integrity failure')
    hashes={p:sha(Path(p).read_bytes()) for p in [a.raw,a.schedule,a.predictions]};before={p:sha(Path(p).read_bytes()) for p in [a.predictions,a.ledger,str(bundle_path)]}
    bundle=joblib.load(bundle_path);pred=pd.read_csv(a.predictions);ledger=pd.read_csv(a.ledger);raw=pd.read_csv(a.raw,low_memory=False);schedule=pd.read_csv(a.schedule,low_memory=False)
    records=receipt_payloads(pred,ledger,raw,bundle,hashes,model_sha,now);out=Path(a.out_dir);n=append_receipts(out/'observations.jsonl',records);health=coverage(schedule,raw,pred,now);health['new_input_receipts']=n;health['first_capture_receipts']=sum(r['receipt_role']=='official_first_capture_inputs' for r in records)
    if any(sha(Path(p).read_bytes())!=h for p,h in before.items()):raise ValueError('Protected CFB artifacts changed while observing inputs')
    (out/'coverage.json').write_text(json.dumps(health,indent=2)+'\n');print(json.dumps(health,indent=2))
if __name__=='__main__':main()
