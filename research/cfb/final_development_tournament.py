"""Final CFB V1 development tournament before opening the 2026 diagnostic holdout.

All model/ensemble/calibration choices are evaluated on 2018-2025 only.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

HERE=Path(__file__).parent
def loadmod(name,file):
    spec=importlib.util.spec_from_file_location(name,HERE/file); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
base=loadmod("base","backtest_baseline.py"); pri=loadmod("pri","experiment_priors.py"); cal=loadmod("cal","experiment_calibration.py")

def logit(p):
    p=np.clip(np.asarray(p,float),1e-5,1-1e-5); return np.log(p/(1-p)).reshape(-1,1)

def features_for(df,k=7.0):
    x=pri.matrix(df,k)
    context=base.feature_sets(base.build_matrix(df))["cfb_context"]
    removable={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES}
    feats=[c for c in context if c not in removable]+[f"blend_{f}_diff" for f in pri.BLEND_BASES]
    return x,feats

def raw_oof(df,x,features,season):
    tr=df.index[df.season<season]; te=df.index[df.season==season]
    m=base.model(features); m.fit(x.loc[tr,features],df.loc[tr,"home_win"])
    return m.predict_proba(x.loc[te,features])[:,1]

def prior_calibration_data(df,x,features,target,window=1):
    parts=[]
    for s in range(max(int(df.season.min())+1,target-window),target):
        tr=df.index[df.season<s]; te=df.index[df.season==s]
        if not len(tr) or not len(te): continue
        m=base.model(features); m.fit(x.loc[tr,features],df.loc[tr,"home_win"])
        parts.append((m.predict_proba(x.loc[te,features])[:,1],df.loc[te,"home_win"].to_numpy()))
    if not parts:return None,None
    return np.concatenate([a for a,b in parts]),np.concatenate([b for a,b in parts])

def evaluate(df):
    bx=base.build_matrix(df); context=base.feature_sets(bx)["cfb_context"]
    px,pfeat=features_for(df,7.0)
    store={n:{"p":[],"y":[],"seasons":[]} for n in ["context_raw","prior_k7_raw","prior_k7_platt1","blend_context_prior_25","blend_context_prior_50"]}
    for season in range(2018,2026):
        te=df.index[df.season==season]; y=df.loc[te,"home_win"].to_numpy()
        pc=raw_oof(df,bx,context,season); pp=raw_oof(df,px,pfeat,season)
        cp,cy=prior_calibration_data(df,px,pfeat,season,1)
        pcal=pp
        if cp is not None and len(np.unique(cy))==2:
            z=LogisticRegression(C=100,max_iter=2000); z.fit(logit(cp),cy); pcal=z.predict_proba(logit(pp))[:,1]
        vals={
            "context_raw":pc,"prior_k7_raw":pp,"prior_k7_platt1":pcal,
            "blend_context_prior_25":.25*pc+.75*pp,
            "blend_context_prior_50":.50*pc+.50*pp,
        }
        for n,p in vals.items():
            s=base.score(y,p); s["season"]=season; store[n]["seasons"].append(s); store[n]["p"].append(p); store[n]["y"].append(y)
    result={}
    for n,v in store.items():
        p=np.concatenate(v["p"]); y=np.concatenate(v["y"])
        result[n]={"overall":base.score(y,p),"recent_2023_2025":base.score(np.concatenate(v["y"][-3:]),np.concatenate(v["p"][-3:])),
                   "calibration":base.calibration(pd.DataFrame({"home_win":y,"home_win_prob":p,"predicted_home_win":(p>=.5).astype(int)})),
                   "by_season":v["seasons"]}
    return result,pfeat

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/results");args=ap.parse_args()
    df=base.load_data(Path(args.data_dir)); df=df[df.season<=2025].copy().reset_index(drop=True)
    result,features=evaluate(df)
    ranked=sorted(result,key=lambda n:(result[n]["overall"]["brier"],result[n]["overall"]["log_loss"],-result[n]["recent_2023_2025"]["accuracy"]))
    payload={"selection_window":"2018-2025","2026_touched":False,"ranking":ranked,"leader":ranked[0],"prior_k":7.0,"leader_features":features,"candidates":result}
    out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"final_development_tournament.json").write_text(json.dumps(payload,indent=2)+"\n")
    lines=["# CFB V1 Final Development Tournament","",
           "No 2026 games were used. Ranking is by walk-forward Brier score, then log loss, with 2023-2025 shown as a stability check.","",
           "| Candidate | Accuracy | Brier | Log loss | 2023-25 acc | 2023-25 Brier |","|---|---:|---:|---:|---:|---:|"]
    for n in ranked:
        a=result[n]["overall"]; r=result[n]["recent_2023_2025"]; lines.append(f"| {n} | {a['accuracy']:.2%} | {a['brier']:.4f} | {a['log_loss']:.4f} | {r['accuracy']:.2%} | {r['brier']:.4f} |")
    lines += ["",f"Prefreeze leader: **{ranked[0]}**.","","The next step after this report is to lock the CFB V1 specification before opening the 2026 diagnostic holdout."]
    (out/"FINAL_DEVELOPMENT_REPORT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
