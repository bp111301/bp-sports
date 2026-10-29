"""Restore exact original source bytes; never regenerate frozen history remotely."""
import hashlib,json,tarfile
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def restore(root,configuration):
 root=Path(root);spec=configuration['frozen_history_archive'];archive=root/spec['path']
 if sha(archive)!=spec['sha256']:raise ValueError('Frozen source archive hash mismatch')
 expected={}
 for sport in ['cfb','nhl']:
  meta=json.loads((root/f'research/confidence_projection_20261028/final_bundles/{sport}.json').read_text())
  for relative,digest in meta['source_file_sha256'].items():
   if sport=='cfb' and not relative.endswith('cfb_matchup_line_2025.csv'):continue
   path=root/relative
   if not path.resolve().is_relative_to((root/'runtime').resolve()):raise ValueError('Frozen sources may only restore to runtime')
   if path.name in expected:raise ValueError('Duplicate archived input name')
   expected[path.name]=(path,digest)
 restored=0
 with tarfile.open(archive,'r:gz') as tar:
  members=tar.getmembers()
  if len(members)!=len(expected) or len({m.name for m in members})!=len(members) or {m.name for m in members}!=set(expected):raise ValueError('Unexpected frozen source archive members')
  for member in members:
   if not member.isfile() or Path(member.name).name!=member.name:raise ValueError('Unsafe frozen source archive member')
   path,digest=expected[member.name];raw=tar.extractfile(member).read()
   if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Original archived source checksum mismatch')
   if not path.exists() or sha(path)!=digest:
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);restored+=1
 return {'verified_original_inputs':len(expected),'restored_runtime_inputs':restored,'source_archive_sha256':spec['sha256']}
