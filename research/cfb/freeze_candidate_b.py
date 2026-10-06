"""Fit the already-locked CFB V2 Candidate B on 2015-2025 only."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json
from datetime import datetime,timezone
from pathlib import Path
import joblib,numpy as np,sklearn
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py");margin=mod("margin","experiment_margin_v2.py")
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out",default="model/cfb/v2/candidate_b_bundle.joblib");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True)
 bx=base.build_matrix(df);cf=base.feature_sets(bx)["cfb_context"];px=pri.matrix(df,7.0);rem={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES};pf=[c for c in cf if c not in rem]+[f"blend_{f}_diff" for f in pri.BLEND_BASES]
 mc=base.model(cf);mp=base.model(pf);mc.fit(bx[cf],df.home_win);mp.fit(px[pf],df.home_win)
 ymargin=(df.home_points-df.away_points).to_numpy();mm=margin.margin_model(cf,100.0);mm.fit(bx[cf],ymargin);fit=mm.predict(bx[cf]);sigma=float(np.std(ymargin-fit,ddof=1))
 frozen=datetime.now(timezone.utc).isoformat();bundle={"version":"CFB_V2_CANDIDATE_B","status":"PROSPECTIVE_SHADOW_ONLY","frozen_bundle_created_utc":frozen,"selection_cutoff_season":2025,"training_seasons":[2015,2025],"v1_context_weight":.25,"v1_prior_weight":.75,"prior_k":7.0,"candidate_b_v1_weight":.65,"candidate_b_margin_weight":.35,"margin_alpha":100.0,"margin_sigma":sigma,"context_features":cf,"prior_features":pf,"v1_context_model":mc,"v1_prior_model":mp,"margin_model":mm,"market_used":False,"sklearn_version":sklearn.__version__}
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);joblib.dump(bundle,out,compress=3);sha=hashlib.sha256(out.read_bytes()).hexdigest();manifest={"version":bundle["version"],"status":bundle["status"],"sha256":sha,"bytes":out.stat().st_size,"created_utc":frozen,"selection_cutoff_season":2025,"market_used":False};(out.parent/"candidate_b_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n");print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
