"""Nested sequential ensemble test for the two leading CFB V2 families.

For each target season, choose the best score-margin candidate, nonlinear
candidate, and blend weight using ONLY earlier OOF seasons. Then lock those
choices and score the target season. No market data or 2026 data are used.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import brier_score_loss,log_loss
def score(y,p):
 y=np.asarray(y,int);p=np.asarray(p,float);return {"games":int(len(y)),"accuracy":float(((p>=.5).astype(int)==y).mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--margin",default="research/cfb/v2_results/margin_oof_candidates.csv");ap.add_argument("--nonlinear",default="research/cfb/v2_results/nonlinear_oof_candidates.csv");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 m=pd.read_csv(a.margin);n=pd.read_csv(a.nonlinear);keep=["game_id","season","home_win"]+[c for c in n if c=="v1" or c.startswith("hgb_")];d=m.merge(n[keep],on=["game_id","season","home_win"],how="inner",suffixes=("","_n"));mcols=[c for c in d if c.startswith("blend_")];ncols=[c for c in d if c.startswith("hgb_")];weights=[0,.25,.5,.75,1.0];folds=[];store={"combo":[],"margin":[],"nonlinear":[],"v1":[],"y":[]}
 for target in range(2021,2026):
  tr=d[(d.season>=2018)&(d.season<target)];te=d[d.season==target];ytr=tr.home_win.to_numpy();y=te.home_win.to_numpy()
  mc=min(mcols,key=lambda c:brier_score_loss(ytr,tr[c]));nc=min(ncols,key=lambda c:brier_score_loss(ytr,tr[c]))
  w=min(weights,key=lambda q:brier_score_loss(ytr,(1-q)*tr[mc]+q*tr[nc]));pc=(1-w)*te[mc].to_numpy()+w*te[nc].to_numpy();pm=te[mc].to_numpy();pn=te[nc].to_numpy();pv=te.v1.to_numpy()
  folds.append({"season":target,"margin_candidate":mc,"nonlinear_candidate":nc,"nonlinear_weight":w,"combo":score(y,pc),"margin":score(y,pm),"nonlinear":score(y,pn),"v1":score(y,pv)})
  for k,p in [("combo",pc),("margin",pm),("nonlinear",pn),("v1",pv)]:store[k].append(p)
  store["y"].append(y)
 y=np.concatenate(store["y"]);agg={k:score(y,np.concatenate(store[k])) for k in ["v1","margin","nonlinear","combo"]}
 payload={"protocol":"nested sequential selection using earlier OOF seasons only","2026_touched":False,"market_used":False,"folds":folds,"aggregate":agg};out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"combined_challenger.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Combined Challenger","","For each target season, the margin configuration, nonlinear configuration, and their blend weight are chosen using only earlier out-of-fold seasons. The target season is untouched until scoring. No market or 2026 data enters selection.","","| Model | 2021-25 accuracy | Brier | Log loss |","|---|---:|---:|---:|"]
 for k in ["v1","margin","nonlinear","combo"]:
  x=agg[k];lines.append(f"| {k} | {x['accuracy']:.2%} | {x['brier']:.6f} | {x['log_loss']:.6f} |")
 lines+=["","## Locked season-by-season choices","","| Season | Margin | Nonlinear | Nonlinear weight | Combo Brier | V1 Brier |","|---|---|---|---:|---:|---:|"]
 for f in folds:lines.append(f"| {f['season']} | {f['margin_candidate']} | {f['nonlinear_candidate']} | {f['nonlinear_weight']:.0%} | {f['combo']['brier']:.6f} | {f['v1']['brier']:.6f} |")
 (out/"COMBINED_CHALLENGER.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
