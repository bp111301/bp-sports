"""Recover the pinned review inputs into runtime; never fetch today's ledgers."""
import argparse,hashlib,json
from pathlib import Path
from urllib.request import Request,urlopen

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dest',type=Path,default=Path('runtime/prospective_review/20261028/inputs'))
    args=ap.parse_args();args.dest.mkdir(parents=True,exist_ok=True)
    here=Path(__file__).parent;manifest=json.loads((here/'source_manifest.json').read_text())
    for name,source in manifest['sources'].items():
        with urlopen(Request(source['url'],headers={'User-Agent':'BP-Sports-ReadOnly-Review/1.0'}),timeout=60) as response:raw=response.read()
        text=raw.decode('utf-8').rstrip('\n')+'\n'
        if hashlib.sha256(text.encode()).hexdigest()!=source['sha256']:raise ValueError('Pinned review input hash mismatch: '+name)
        (args.dest/name).write_text(text)
    for name in manifest['supplements']:(args.dest/name).write_bytes((here/name).read_bytes())
    print('Recovered '+str(len(manifest['sources']))+' hash-verified pinned inputs to '+str(args.dest))
if __name__=='__main__':main()
