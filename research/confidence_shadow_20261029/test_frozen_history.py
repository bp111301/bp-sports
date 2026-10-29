import importlib.util,json,hashlib,tarfile,io
from pathlib import Path
import pytest
s=importlib.util.spec_from_file_location('frozen_sources',Path(__file__).with_name('frozen_history.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def setup(root,extra=False):
 expected={'cfb_matchup_line_2025.csv':b'a,b\n1,2\n','summary_20182019.csv':b'x,y\n3,4\n'}
 for sport,name in [('cfb','cfb_matchup_line_2025.csv'),('nhl','summary_20182019.csv')]:
  p=root/f'research/confidence_projection_20261028/final_bundles/{sport}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'source_file_sha256':{f'runtime/source/{name}':hashlib.sha256(expected[name]).hexdigest()}}))
 archive=root/'history.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for name,raw in expected.items():
   info=tarfile.TarInfo(name);info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
  if extra:
   info=tarfile.TarInfo('../unowned');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
 return {'frozen_history_archive':{'path':'history.tar.gz','sha256':m.sha(archive)}},expected

def test_exact_bytes_restore_regenerated_or_absent_cache(tmp_path):
 config,expected=setup(tmp_path);p=tmp_path/'runtime/source/summary_20182019.csv';p.parent.mkdir(parents=True);p.write_bytes(b'different csv ordering')
 result=m.restore(tmp_path,config);assert result['restored_runtime_inputs']==2
 for name,raw in expected.items():assert (tmp_path/'runtime/source'/name).read_bytes()==raw
 assert m.restore(tmp_path,config)['restored_runtime_inputs']==0

def test_archive_tampering_and_unexpected_members_rejected(tmp_path):
 config,_=setup(tmp_path);(tmp_path/'history.tar.gz').write_bytes(b'changed')
 with pytest.raises(ValueError,match='hash'):m.restore(tmp_path,config)
 config,_=setup(tmp_path,extra=True)
 with pytest.raises(ValueError,match='members'):m.restore(tmp_path,config)
 assert not (tmp_path/'unowned').exists()

def test_metadata_cannot_restore_into_models(tmp_path):
 config,_=setup(tmp_path);p=tmp_path/'research/confidence_projection_20261028/final_bundles/nhl.json';j=json.loads(p.read_text());j['source_file_sha256']={'model/summary_20182019.csv':next(iter(j['source_file_sha256'].values()))};p.write_text(json.dumps(j))
 with pytest.raises(ValueError,match='runtime'):m.restore(tmp_path,config)
