"""Meta walk-forward validation for CFB V2 margin candidates.

For each target season 2021-2025, choose the blend with the best Brier score
using ONLY earlier OOF seasons, then score that locked choice on the target
season. This tests whether the margin architecture survives sequential model
selection rather than benefiting only from full-period hindsight.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import brier_score_loss,log_loss
def score(y,p):
 y=np.asarray(y,int);p=np.asarray(p,float);pred=(p>=.5).astype(int)
 return {"games":int(len(y)),"accuracy":float((pred==y).mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1])),"mean_confidence":float(np.maximum(p,1-p).mean())}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--input",default="research/cfb/v2_results/margin_oof_candidates.csv");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=pd.read_csv(a.input);cands=[c for c in df if c.startswith("blend_")];folds=[];locked=[];base=[]
 for target in range(2021,2026):
  prior=df[(df.season>=2018)&(df.season<target)];test=df[df.season==target]
  ranked=sorted(cands,key=lambda c:(brier_score_loss(prior.home_win,prior[c]),log_loss(prior.home_win,prior[c],labels=[0,1])))
  chosen=ranked[0];pm=test[chosen].to_numpy();pv=test.v1.to_numpy();y=test.home_win.to_numpy()
  cm=score(y,pm);cv=score(y,pv)
  folds.append({"target_season":target,"selection_seasons":f"2018-{target-1}","chosen":chosen,"selection_brier":float(brier_score_loss(prior.home_win,prior[chosen])),"challenger":cm,"v1":cv,"delta_brier":cm["brier"]-cv["brier"]})
  locked.append(pd.DataFrame({"season":target,"y":y,"p":pm,"conference_game":test.get("conference_game",False),"week":test.get("week",np.nan)}));base.append(pd.DataFrame({"season":target,"y":y,"p":pv,"conference_game":test.get("conference_game",False),"week":test.get("week",np.nan)}))
 m=pd.concat(locked,ignore_index=True);v=pd.concat(base,ignore_index=True);overall_m=score(m.y,m.p);overall_v=score(v.y,v.p)
 def subgroup(frame,mask):return score(frame.loc[mask,"y"],frame.loc[mask,"p"])
 conf=m.conference_game.astype(str).str.lower().isin(["true","1","yes"]);vconf=v.conference_game.astype(str).str.lower().isin(["true","1","yes"])
 mid=pd.to_numeric(m.week,errors="coerce").between(7,9);vmid=pd.to_numeric(v.week,errors="coerce").between(7,9)
 payload={"protocol":"For each 2021-2025 season, candidate chosen by prior-season OOF Brier only","2026_touched":False,"folds":folds,"aggregate":{"challenger":overall_m,"v1":overall_v,"delta_brier":overall_m["brier"]-overall_v["brier"],"delta_accuracy":overall_m["accuracy"]-overall_v["accuracy"]},"subgroups":{"conference":{"challenger":subgroup(m,conf),"v1":subgroup(v,vconf)},"weeks_7_9":{"challenger":subgroup(m,mid),"v1":subgroup(v,vmid)}}}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"margin_meta_walkforward.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Margin Meta Walk-Forward","","Each target season locks the margin blend using only earlier out-of-fold seasons. No target-season result participates in that season's candidate choice; 2026 remains excluded.","","| Target | Prior selection window | Locked candidate | V1 Brier | Challenger Brier | Δ Brier |","|---|---|---|---:|---:|---:|"]
 for f in folds:lines.append(f"| {f['target_season']} | {f['selection_seasons']} | {f['chosen']} | {f['v1']['brier']:.6f} | {f['challenger']['brier']:.6f} | {f['delta_brier']:+.6f} |")
 lines+=["","## Aggregate 2021-2025","",f"- V1: {overall_v['accuracy']:.2%} accuracy, {overall_v['brier']:.6f} Brier, {overall_v['log_loss']:.6f} log loss.",f"- Sequential margin challenger: {overall_m['accuracy']:.2%} accuracy, {overall_m['brier']:.6f} Brier, {overall_m['log_loss']:.6f} log loss.",f"- Delta: {payload['aggregate']['delta_accuracy']:+.2%} accuracy, {payload['aggregate']['delta_brier']:+.6f} Brier.","","## Audited weak spots",""]
 for label in ["conference","weeks_7_9"]:
  x=payload["subgroups"][label];lines.append(f"- {label}: V1 {x['v1']['accuracy']:.2%}/{x['v1']['brier']:.4f}; challenger {x['challenger']['accuracy']:.2%}/{x['challenger']['brier']:.4f}.")
 (out/"MARGIN_META_WALKFORWARD.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
