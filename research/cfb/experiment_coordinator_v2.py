"""Leakage-safe coordinator-continuity experiment for CFB V2."""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np
from sklearn.metrics import brier_score_loss
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");audit=mod("audit","deep_audit.py")
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);bx,cf,px,pf=audit.matrices(df)
 bx["oc_cont_diff"]=df.home_oc_cont-df.away_oc_cont;bx["dc_cont_diff"]=df.home_dc_cont-df.away_dc_cont
 variants={"v1":[],"oc_cont":[],"dc_cont":[],"both_cont":[]};ys=[];ss=[];weeks=[]
 for season in range(2018,2026):
  tr=df.index[df.season<season];te=df.index[df.season==season];y=df.loc[te,"home_win"].to_numpy();ys.append(y);ss.extend([season]*len(te));weeks.extend(df.loc[te,"week"].tolist())
  mp=base.model(pf);mp.fit(px.loc[tr,pf],df.loc[tr,"home_win"]);pp=mp.predict_proba(px.loc[te,pf])[:,1]
  for name,extra in [("v1",[]),("oc_cont",["oc_cont_diff"]),("dc_cont",["dc_cont_diff"]),("both_cont",["oc_cont_diff","dc_cont_diff"])]:
   f=cf+extra;mc=base.model(f);mc.fit(bx.loc[tr,f],df.loc[tr,"home_win"]);variants[name].append(.25*mc.predict_proba(bx.loc[te,f])[:,1]+.75*pp)
 y=np.concatenate(ys);sa=np.asarray(ss);wk=np.asarray(weeks,float);cand={k:np.concatenate(v) for k,v in variants.items()};res={}
 for n,p in cand.items():res[n]={"overall":base.score(y,p),"recent":base.score(y[sa>=2023],p[sa>=2023]),"weeks_1_3":base.score(y[wk<=3],p[wk<=3])}
 b=res["v1"]["overall"]["brier"]
 for n in res:res[n]["delta_brier"]=res[n]["overall"]["brier"]-b
 opts=["oc_cont","dc_cont","both_cont"];folds=[];pp=[];yy=[]
 for target in range(2021,2026):
  prior=sa<target;test=sa==target;chosen=min(opts,key=lambda k:brier_score_loss(y[prior],cand[k][prior]));folds.append({"season":target,"chosen":chosen,"challenger":base.score(y[test],cand[chosen][test]),"v1":base.score(y[test],cand["v1"][test])});pp.append(cand[chosen][test]);yy.append(y[test])
 payload={"2026_touched":False,"market_used":False,"candidates":res,"meta_walkforward":{"folds":folds,"challenger":base.score(np.concatenate(yy),np.concatenate(pp)),"v1":base.score(y[sa>=2021],cand["v1"][sa>=2021])}}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"coordinator_continuity.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Coordinator Continuity","","Preseason OC/DC continuity is leakage-safe and market-free. 2026 is excluded.","","| Candidate | Accuracy | Brier | Delta | Recent Brier | Weeks 1-3 |","|---|---:|---:|---:|---:|---:|"]
 for n in variants:
  x=res[n];lines.append(f"| {n} | {x['overall']['accuracy']:.2%} | {x['overall']['brier']:.6f} | {x['delta_brier']:+.6f} | {x['recent']['brier']:.6f} | {x['weeks_1_3']['brier']:.6f} |")
 mm=payload["meta_walkforward"];lines+=["",f"Sequential 2021-25: V1 {mm['v1']['brier']:.6f}; selected continuity {mm['challenger']['brier']:.6f}."]
 (out/"COORDINATOR_CONTINUITY.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
