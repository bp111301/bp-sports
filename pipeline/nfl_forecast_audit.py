"""Append-only evidence for new NFL forecasts, separate from saved predictions."""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def inputs(root,season,bundle,overrides):
    root=Path(root)
    records=json.loads((root/'manifest.json').read_text())
    expected={'schedules.csv',f'play_by_play_{season}.csv.gz'}
    indexed={item['file']:item for item in records}
    if len(indexed)!=len(records) or not expected.issubset(indexed):
        raise ValueError('NFL input manifest is incomplete or duplicated')
    for name in expected:
        receipt=indexed[name]
        observed=datetime.fromisoformat(receipt['retrieved_at_utc'].replace('Z','+00:00'))
        if observed.tzinfo is None or observed>datetime.now(timezone.utc):
            raise ValueError('NFL input receipt has invalid observation time')
        if digest(root/name)!=receipt['sha256'] or (root/name).stat().st_size!=receipt['bytes']:
            raise ValueError('NFL input receipt does not match '+name)
    return {'input_receipts':[indexed[name] for name in sorted(expected)],
            'bundle_sha256':digest(bundle),
            'effective_overrides_sha256':digest(overrides) if Path(overrides).exists() else None}


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if hasattr(value,'item'):return clean(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    if hasattr(value,'isoformat'):return value.isoformat()
    return value


def append_receipts(path,records):
    """Never rewrite existing evidence, including byte spelling of old lines."""
    path=Path(path);old={}
    if path.exists():
        raw=path.read_bytes()
        if raw and not raw.endswith(b'\n'):raise ValueError('Incomplete NFL audit log')
        for line in raw.splitlines():
            record=json.loads(line);identity=record['prediction_id']
            if identity in old:raise ValueError('Duplicate NFL audit identity')
            old[identity]=record
    pending=[]
    for record in records:
        record=clean(record);identity=record['prediction_id']
        if identity in old:
            if old[identity]!=record:raise ValueError('NFL audit identity already saved with different evidence')
            continue
        pending.append(json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
        old[identity]=record
    if pending:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a') as file:file.writelines(pending)


def records(feed,features,components,bundle_version,evidence,availability,snapshot_id):
    result=[]
    for row in feed.to_dict('records'):
        gid=row['game_id'];context=availability.get('games',{}).get(gid,{})
        capture=datetime.fromisoformat(row['captured_at_utc'])
        for receipt in evidence['input_receipts']+context.get('source_receipts',[]):
            observed=datetime.fromisoformat(receipt['retrieved_at_utc'].replace('Z','+00:00'))
            if observed.tzinfo is None or observed>capture:
                raise ValueError('NFL receipt was not observed before capture')
        vector=clean(features.loc[gid].to_dict())
        result.append(clean({'schema_version':1,'prediction_id':snapshot_id+':'+gid,
                            'game_id':gid,'captured_at_utc':row['captured_at_utc'],
                            'kickoff_utc':row['kickoff_utc'],'bundle_version':bundle_version,**evidence,
                            'features':vector,'missing_features':[k for k,v in vector.items() if v is None],
                            'component_home_probabilities':components[gid],
                            'qb_evidence':{side:context.get(side,{}) for side in ['home','away']},
                            'availability_checked_at_utc':context.get('checked_at_utc'),
                            'availability_source_receipts':context.get('source_receipts',[]),
                            'availability_source_errors':context.get('source_errors',[])}))
    return result
