"""Targeted CFB V2 reliability experiments derived from the frozen V1 audit.

All candidate selection uses 2018-2025 OOF predictions only. 2026 is excluded.
The experiment changes probability magnitude only; winner direction is preserved.
"""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import brier_score_loss,log_loss
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
audit=mod("audit","deep_audit.py");base=audit.base
def expit(z):return 1/(1+np.exp(-z))
def scale_prob(p,s):
 p=np.clip(np.asarray(p,float),1e-6,1-1e-6);return expit(s*np.log(p/(1-p)))
def score(df,p):
 y=df.home_win.to_numpy();pred=(p>=.5).astype(int)
 return {"games":int(len(y)),"accuracy":float((pred==y).mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1])),"mean_confidence":float(np.maximum(p,1-p).mean())}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);pred=audit.frozen_oof(df);raw=pred.p_home.to_numpy()
 conf=pred["conference_game"].astype(str).str.lower().isin(["true","1","yes"]).to_numpy() if "conference_game" in pred else np.zeros(len(pred),bool)
 neutral=pred["neutral_site"].astype(str).str.lower().isin(["true","1","yes"]).to_numpy() if "neutral_site" in pred else np.zeros(len(pred),bool)
 week=pd.to_numeric(pred.week,errors="coerce").fillna(0).to_numpy();mid=(week>=7)&(week<=9)
 candidates={"v1_raw":raw}
 for s in [.90,.925,.95,.975]:
  candidates[f"global_{s:.3f}"]=scale_prob(raw,s)
 for s in [.90,.925,.95,.975]:
  for label,mask in [("conference",conf),("neutral",neutral),("weeks7_9",mid)]:
   q=raw.copy();q[mask]=scale_prob(q[mask],s);candidates[f"{label}_{s:.3f}"]=q
 for s in [.925,.95,.975]:
  q=raw.copy()
  # apply one shrink only when any audited weak-context flag is present
  mask=conf|neutral|mid;q[mask]=scale_prob(q[mask],s);candidates[f"weak_context_{s:.3f}"]=q
 result={}
 for name,p in candidates.items():
  by=[]
  for season in range(2018,2026):
   mask=pred.season.to_numpy()==season;z=score(pred.loc[mask],p[mask]);z["season"]=season;by.append(z)
  recent=pred.season.to_numpy()>=2023
  result[name]={"overall":score(pred,p),"recent_2023_2025":score(pred.loc[recent],p[recent]),"by_season":by}
 base_b=result["v1_raw"]["overall"]["brier"];base_r=result["v1_raw"]["recent_2023_2025"]["brier"]
 for n,v in result.items():
  v["delta_brier"]=v["overall"]["brier"]-base_b;v["recent_delta_brier"]=v["recent_2023_2025"]["brier"]-base_r
  v["seasons_brier_better_than_v1"]=sum(x["brier"]<y["brier"] for x,y in zip(v["by_season"],result["v1_raw"]["by_season"]))
 ranked=sorted(result,key=lambda n:(result[n]["overall"]["brier"],result[n]["recent_2023_2025"]["brier"]))
 payload={"selection_window":"2018-2025 OOF only","2026_touched":False,"winner_direction_preserved":True,"ranking":ranked,"candidates":result}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"reliability_adjustments.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Reliability Adjustment Experiment","","Probability-only stress test on frozen V1 OOF predictions. 2026 excluded; no candidate can flip a winner.","","| Candidate | Brier | Δ Brier | Recent Brier | Recent Δ | Seasons improved |","|---|---:|---:|---:|---:|---:|"]
 for n in ranked:
  v=result[n];lines.append(f"| {n} | {v['overall']['brier']:.6f} | {v['delta_brier']:+.6f} | {v['recent_2023_2025']['brier']:.6f} | {v['recent_delta_brier']:+.6f} | {v['seasons_brier_better_than_v1']}/8 |")
 (out/"RELIABILITY_ADJUSTMENTS.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
