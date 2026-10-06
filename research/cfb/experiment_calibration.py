"""Leakage-safe probability calibration experiment for CFB V1.

Platt calibration is trained only on prior-season out-of-sample predictions.
No target-season result participates in its own calibrator.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

SPEC=importlib.util.spec_from_file_location("cfb_base",Path(__file__).with_name("backtest_baseline.py"))
base=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(base)

def logit(p):
    p=np.clip(np.asarray(p,dtype=float),1e-5,1-1e-5)
    return np.log(p/(1-p)).reshape(-1,1)

def raw_model(features,c):
    return base.model(features) if c==.5 else _custom(features,c)

def _custom(features,c):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    prep=ColumnTransformer([("num",Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),features)],remainder="drop")
    return Pipeline([("prep",prep),("model",LogisticRegression(C=c,max_iter=4000))])

def prior_oof(df,x,features,c,target_season,n_seasons):
    parts=[]
    start=max(int(df.season.min())+1,target_season-n_seasons)
    for season in range(start,target_season):
        tr=df.index[df.season<season]; te=df.index[df.season==season]
        if not len(tr) or not len(te): continue
        m=raw_model(features,c); m.fit(x.loc[tr,features],df.loc[tr,"home_win"])
        p=m.predict_proba(x.loc[te,features])[:,1]
        parts.append((p,df.loc[te,"home_win"].to_numpy()))
    if not parts: return None,None
    return np.concatenate([z[0] for z in parts]),np.concatenate([z[1] for z in parts])

def evaluate(df,x,features,c,cal_window):
    rows=[]; allp=[]; ally=[]
    for season in range(2018,2026):
        tr=df.index[df.season<season]; te=df.index[df.season==season]
        m=raw_model(features,c); m.fit(x.loc[tr,features],df.loc[tr,"home_win"])
        p=m.predict_proba(x.loc[te,features])[:,1]
        if cal_window:
            cp,cy=prior_oof(df,x,features,c,season,cal_window)
            if cp is not None and len(np.unique(cy))==2:
                calibrator=LogisticRegression(C=100,max_iter=2000)
                calibrator.fit(logit(cp),cy)
                p=calibrator.predict_proba(logit(p))[:,1]
        y=df.loc[te,"home_win"].to_numpy(); s=base.score(y,p); s["season"]=season; rows.append(s); allp.append(p); ally.append(y)
    p=np.concatenate(allp); y=np.concatenate(ally)
    return base.score(y,p),pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",default="runtime/cfb/matchup_line"); ap.add_argument("--out-dir",default="research/cfb/results"); args=ap.parse_args()
    df=base.load_data(Path(args.data_dir)); df=df[df.season<=2025].copy().reset_index(drop=True); x=base.build_matrix(df)
    context=base.feature_sets(x)["cfb_context"]; full=list(x.columns)
    specs={
        "context_raw":(context,.5,0),
        "context_platt_1":(context,.5,1),
        "context_platt_3":(context,.5,3),
        "full_c005_raw":(full,.05,0),
        "full_c005_platt_3":(full,.05,3),
    }
    result={"selection_window":"2018-2025","method":"Platt calibration uses only prior-season OOF probabilities","candidates":{}}
    frames=[]
    for name,(features,c,window) in specs.items():
        overall,seasons=evaluate(df,x,features,c,window); seasons["candidate"]=name; frames.append(seasons)
        result["candidates"][name]={"C":c,"calibration_window_seasons":window,"n_features":len(features),"overall":overall}
    ranked=sorted(result["candidates"],key=lambda n:(result["candidates"][n]["overall"]["brier"],result["candidates"][n]["overall"]["log_loss"]))
    result["ranking"]=ranked; result["leader"]=ranked[0]
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    pd.concat(frames,ignore_index=True).to_csv(out/"calibration_by_season.csv",index=False)
    (out/"calibration_experiment.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# CFB V1 Calibration Experiment","",
           "All calibration mappings are trained only on out-of-sample probabilities from seasons before the season being predicted.","",
           "| Candidate | Accuracy | Brier | Log loss |","|---|---:|---:|---:|"]
    for name in ranked:
        m=result["candidates"][name]["overall"]; lines.append(f"| {name} | {m['accuracy']:.2%} | {m['brier']:.4f} | {m['log_loss']:.4f} |")
    lines += ["",f"Leader by Brier: **{ranked[0]}**.","","2026 remains untouched."]
    (out/"CALIBRATION_REPORT.md").write_text("\n".join(lines)+"\n"); print("\n".join(lines))
if __name__=="__main__": main()
