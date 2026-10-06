"""NHL V1 development tournament.

Selection uses 2021-22 through 2024-25 only. 2025-26 is excluded from this
tournament so candidate choice cannot chase that season's outcomes.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,brier_score_loss,log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("base",HERE/"backtest_baseline.py");base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

SETS={
 "elo_only":["elo_diff","home_field"],
 "elo_rest":["elo_diff","home_field","rest_diff","home_b2b","away_b2b"],
 "elo_form":["elo_diff","home_field","win10_diff","gd10_diff","gf10_diff","ga10_diff"],
 "full":base.FEATURES,
}
def model(features,c):
 prep=ColumnTransformer([("num",Pipeline([("imp",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),features)],remainder="drop")
 return Pipeline([("prep",prep),("model",LogisticRegression(C=c,max_iter=3000))])
def met(y,p):
 return {"games":int(len(y)),"accuracy":float(accuracy_score(y,p>=.5)),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}
def main():
 d=base.load("runtime/nhl/games");x=base.build_features(d);dev=["20212022","20222023","20232024","20242025"];rows=[];preds=[]
 for name,features in SETS.items():
  for window in [2,3,99]:
   for c in [.1,.5,1.0]:
    all_y=[];all_p=[];season_metrics=[]
    for s in dev:
     prior=sorted([z for z in d.season.unique() if z<s])
     train_seasons=prior[-window:] if window<99 else prior
     tr=d.index[d.season.isin(train_seasons)];te=d.index[d.season==s]
     if not len(tr):continue
     m=model(features,c);m.fit(x.loc[tr,features],d.loc[tr,"home_win"]);p=m.predict_proba(x.loc[te,features])[:,1];y=d.loc[te,"home_win"].to_numpy();all_y.extend(y);all_p.extend(p);q=met(y,p);q["season"]=s;season_metrics.append(q)
    z=met(np.asarray(all_y),np.asarray(all_p));z.update({"candidate":name,"window":window,"C":c,"features":features,"by_season":season_metrics});rows.append(z)
 rows=sorted(rows,key=lambda z:(z["brier"],z["log_loss"],-z["accuracy"]));best=rows[0];out=Path("research/nhl/results");out.mkdir(parents=True,exist_ok=True);(out/"development_tournament.json").write_text(json.dumps({"selection_seasons":dev,"excluded_from_selection":["20252026"],"ranking":rows},indent=2)+"\n")
 lines=["# NHL V1 Development Tournament","","Selection seasons: 2021-22 through 2024-25. 2025-26 excluded from candidate selection.","","| Rank | Candidate | Window | C | Accuracy | Brier | Log loss |","|---:|---|---:|---:|---:|---:|---:|"]
 for i,r in enumerate(rows[:15],1):lines.append(f"| {i} | {r['candidate']} | {r['window']} | {r['C']} | {r['accuracy']:.2%} | {r['brier']:.4f} | {r['log_loss']:.4f} |")
 (out/"DEVELOPMENT_TOURNAMENT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
