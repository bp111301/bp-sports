"""Fit and serialize the already-selected CFB V1 on all 2015-2025 development data."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path
import joblib, sklearn
HERE=Path(__file__).parent
def mod(name,file):
    s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py")
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out",default="model/cfb/v1/frozen_bundle.joblib");a=ap.parse_args()
    df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True)
    bx=base.build_matrix(df);cf=base.feature_sets(bx)["cfb_context"];px=pri.matrix(df,7.0)
    rem={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES}
    pf=[c for c in cf if c not in rem]+[f"blend_{f}_diff" for f in pri.BLEND_BASES]
    mc=base.model(cf);mp=base.model(pf);mc.fit(bx[cf],df.home_win);mp.fit(px[pf],df.home_win)
    bundle={"version":"CFB_V1","frozen_at_utc":"2026-10-06T03:22:19Z","training_seasons":[2015,2025],"context_weight":.25,"prior_weight":.75,"prior_k":7.0,"context_features":cf,"prior_features":pf,"context_model":mc,"prior_model":mp,"sklearn_version":sklearn.__version__}
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);joblib.dump(bundle,out,compress=3)
    sha=hashlib.sha256(out.read_bytes()).hexdigest();(out.parent/"bundle_manifest.json").write_text(json.dumps({"sha256":sha,"bytes":out.stat().st_size,"version":"CFB_V1"},indent=2)+"\n");print(sha,out.stat().st_size)
if __name__=="__main__":main()
