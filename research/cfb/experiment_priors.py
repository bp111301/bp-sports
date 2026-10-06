"""Test dynamic current-season/prior-season blending for CFB.

The blend is week-aware and uses only values already available before kickoff.
2026 remains excluded.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

SPEC=importlib.util.spec_from_file_location("cfb_base",Path(__file__).with_name("backtest_baseline.py"))
base=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(base)

BLEND_BASES=["off_epa","def_epa","off_pass_epa","def_pass_epa","off_rush_epa","def_rush_epa","off_success_rate","def_success_rate"]

def blend_side(df,side,feature,k):
    cur=pd.to_numeric(df.get(f"{side}_{feature}"),errors="coerce")
    prev=pd.to_numeric(df.get(f"prev_{side}_{feature}"),errors="coerce")
    w=np.minimum(1.0,np.maximum(0.0,(pd.to_numeric(df["week"],errors="coerce").fillna(1)-1)/k))
    z=w*cur+(1-w)*prev
    return z.where(cur.notna()&prev.notna(),cur.combine_first(prev))

def matrix(df,k):
    x=base.build_matrix(df)
    for f in BLEND_BASES:
        x[f"blend_{f}_diff"]=blend_side(df,"home",f,k)-blend_side(df,"away",f,k)
    return x

def evaluate(df,x,features):
    rows=[]; ps=[]; ys=[]
    for season in range(2018,2026):
        tr=df.index[df.season<season]; te=df.index[df.season==season]
        m=base.model(features); m.fit(x.loc[tr,features],df.loc[tr,"home_win"])
        p=m.predict_proba(x.loc[te,features])[:,1]; y=df.loc[te,"home_win"].to_numpy()
        s=base.score(y,p); s["season"]=season; rows.append(s); ps.append(p); ys.append(y)
    return base.score(np.concatenate(ys),np.concatenate(ps)),pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",default="runtime/cfb/matchup_line"); ap.add_argument("--out-dir",default="research/cfb/results"); args=ap.parse_args()
    df=base.load_data(Path(args.data_dir)); df=df[df.season<=2025].copy().reset_index(drop=True)
    base_x=base.build_matrix(df); context=base.feature_sets(base_x)["cfb_context"]
    result={"selection_window":"2018-2025","candidates":{},"2026_touched":False}; frames=[]
    raw,raws=evaluate(df,base_x,context); result["candidates"]["context_raw"]={"overall":raw}; raws["candidate"]="context_raw"; frames.append(raws)
    removable={f"{f}_diff" for f in BLEND_BASES}|{f"prev_{f}_diff" for f in BLEND_BASES}
    for k in (3.0,5.0,7.0):
        x=matrix(df,k); blends=[f"blend_{f}_diff" for f in BLEND_BASES]
        for mode in ("add","replace"):
            features=context+blends if mode=="add" else [c for c in context if c not in removable]+blends
            name=f"blend_{mode}_k{int(k)}"; overall,seasons=evaluate(df,x,features)
            result["candidates"][name]={"k":k,"mode":mode,"n_features":len(features),"overall":overall}
            seasons["candidate"]=name; frames.append(seasons)
    ranked=sorted(result["candidates"],key=lambda n:(result["candidates"][n]["overall"]["brier"],result["candidates"][n]["overall"]["log_loss"]))
    result["ranking"]=ranked; result["leader"]=ranked[0]
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    pd.concat(frames,ignore_index=True).to_csv(out/"prior_blend_by_season.csv",index=False)
    (out/"prior_blend_experiment.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# CFB V1 Dynamic Prior Experiment","",
           "Current-season efficiency is blended with prior-season efficiency using only pregame information. 2026 is excluded.","",
           "| Candidate | Accuracy | Brier | Log loss |","|---|---:|---:|---:|"]
    for n in ranked:
        m=result["candidates"][n]["overall"]; lines.append(f"| {n} | {m['accuracy']:.2%} | {m['brier']:.4f} | {m['log_loss']:.4f} |")
    lines+=["",f"Leader by Brier: **{ranked[0]}**."]
    (out/"PRIOR_BLEND_REPORT.md").write_text("\n".join(lines)+"\n"); print("\n".join(lines))
if __name__=="__main__": main()
