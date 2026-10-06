"""CFB V1 candidate tournament on historical development seasons only.

2026 is intentionally excluded. Candidate selection is based on expanding-window
2018-2025 results, preserving 2026 as a later diagnostic/forward boundary.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SPEC=importlib.util.spec_from_file_location("cfb_base",Path(__file__).with_name("backtest_baseline.py"))
base=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(base)

def linear(features:list[str], c:float)->Pipeline:
    return Pipeline([
        ("impute",SimpleImputer(strategy="median",add_indicator=True)),
        ("scale",StandardScaler()),
        ("model",LogisticRegression(C=c,max_iter=4000)),
    ])

def histgb(features:list[str], l2:float)->Pipeline:
    return Pipeline([
        ("impute",SimpleImputer(strategy="median",add_indicator=True)),
        ("model",HistGradientBoostingClassifier(
            learning_rate=0.04,max_iter=250,max_leaf_nodes=15,min_samples_leaf=35,
            l2_regularization=l2,random_state=17,
        )),
    ])

def evaluate(df:pd.DataFrame,x:pd.DataFrame,features:list[str],factory,first_test:int=2018,last_test:int=2025):
    season_rows=[]; pred_rows=[]
    for season in range(first_test,last_test+1):
        tr=df.index[df.season<season]; te=df.index[df.season==season]
        if not len(tr) or not len(te): continue
        m=factory(); m.fit(x.loc[tr,features],df.loc[tr,"home_win"])
        p=m.predict_proba(x.loc[te,features])[:,1]; y=df.loc[te,"home_win"].to_numpy()
        s=base.score(y,p); s["season"]=season; season_rows.append(s)
        z=df.loc[te,["season","home_win"]].copy(); z["home_win_prob"]=p; z["predicted_home_win"]=(p>=.5).astype(int); pred_rows.append(z)
    pred=pd.concat(pred_rows,ignore_index=True)
    overall=base.score(pred.home_win.to_numpy(),pred.home_win_prob.to_numpy())
    return pd.DataFrame(season_rows),overall,base.calibration(pred)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",default="runtime/cfb/matchup_line"); ap.add_argument("--out-dir",default="research/cfb/results")
    args=ap.parse_args()
    df=base.load_data(Path(args.data_dir)); df=df[df.season<=2025].copy().reset_index(drop=True)
    x=base.build_matrix(df)
    blocked=(base.MARKET_BLOCKLIST|base.RETROSPECTIVE_BLOCKLIST)&set(x.columns)
    if blocked: raise RuntimeError(f"blocked leakage features: {sorted(blocked)}")
    baseline_features=base.feature_sets(x)["cfb_context"]
    full=list(x.columns)
    candidates={}
    candidates["linear_context_c050"]=(baseline_features,lambda:linear(baseline_features,.50),{"family":"logistic","C":.50})
    for c in (.05,.10,.25,.50,1.0):
        name=f"linear_full_c{str(c).replace('.','')}"
        candidates[name]=(full,lambda c=c:linear(full,c),{"family":"logistic","C":c})
    for l2 in (1.0,5.0,10.0):
        name=f"histgb_full_l2_{int(l2)}"
        candidates[name]=(full,lambda l2=l2:histgb(full,l2),{"family":"hist_gradient_boosting","l2":l2})
    summary={"selection_window":"2018-2025 expanding-window; train only on prior seasons","holdout_2026_touched":False,"candidates":{}}
    season_frames=[]
    for name,(features,factory,spec) in candidates.items():
        seasons,overall,cal=evaluate(df,x,features,factory)
        seasons["candidate"]=name; season_frames.append(seasons)
        summary["candidates"][name]={"spec":spec,"n_features":len(features),"features":features,"overall":overall,"calibration":cal}
        print(name,overall)
    ranked=sorted(summary["candidates"],key=lambda n:(summary["candidates"][n]["overall"]["brier"],summary["candidates"][n]["overall"]["log_loss"],-summary["candidates"][n]["overall"]["accuracy"]))
    summary["ranking"]=ranked; summary["leader"]=ranked[0]
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    pd.concat(season_frames,ignore_index=True).to_csv(out/"candidate_tournament_by_season.csv",index=False)
    (out/"candidate_tournament.json").write_text(json.dumps(summary,indent=2)+"\n")
    lines=["# CFB V1 Candidate Tournament","",
           "Selection window: 2018-2025 expanding-window. The 2026 season is deliberately untouched by this tournament.","",
           "| Candidate | Accuracy | Brier | Log loss | Features |","|---|---:|---:|---:|---:|"]
    for name in ranked:
        v=summary["candidates"][name]; m=v["overall"]
        lines.append(f"| {name} | {m['accuracy']:.2%} | {m['brier']:.4f} | {m['log_loss']:.4f} | {v['n_features']} |")
    lines += ["",f"Historical development leader by Brier: **{ranked[0]}**.","",
              "This is still research selection, not a frozen CFB V1. Market lines and retrospective realized-QB fields remain excluded.",
              "2026 stays sealed until the feature/algorithm tournament is finished."]
    (out/"CANDIDATE_REPORT.md").write_text("\n".join(lines)+"\n")
    print("\n".join(lines))
if __name__=="__main__": main()
