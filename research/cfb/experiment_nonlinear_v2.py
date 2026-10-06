"""Leakage-safe nonlinear challenger for CFB V2."""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss,log_loss
from sklearn.impute import SimpleImputer
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");audit=mod("audit","deep_audit.py")
def score(y,p):
 y=np.asarray(y,int);p=np.asarray(p,float);return {"games":int(len(y)),"accuracy":float(((p>=.5).astype(int)==y).mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}
def hgb(leaf,lr):return HistGradientBoostingClassifier(loss="log_loss",learning_rate=lr,max_iter=180,max_leaf_nodes=leaf,min_samples_leaf=35,l2_regularization=2.0,early_stopping=False,random_state=42)
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);bx,cf,px,pf=audit.matrices(df);specs=[(7,.03),(7,.05),(15,.03),(15,.05)];parts={};v1parts=[];ys=[];seasons=[]
 for leaf,lr in specs:
  for w in [.15,.25,.35]:parts[f"hgb_l{leaf}_lr{int(lr*100):02d}_w{int(w*100)}"]=[]
 for season in range(2018,2026):
  tr=df.index[df.season<season];te=df.index[df.season==season];y=df.loc[te,"home_win"].to_numpy();ys.append(y);seasons.extend([season]*len(te))
  mc=base.model(cf);mp=base.model(pf);mc.fit(bx.loc[tr,cf],df.loc[tr,"home_win"]);mp.fit(px.loc[tr,pf],df.loc[tr,"home_win"]);pv=.25*mc.predict_proba(bx.loc[te,cf])[:,1]+.75*mp.predict_proba(px.loc[te,pf])[:,1];v1parts.append(pv)
  ic=SimpleImputer(strategy="median",add_indicator=True);ip=SimpleImputer(strategy="median",add_indicator=True);xc=ic.fit_transform(bx.loc[tr,cf]);tc=ic.transform(bx.loc[te,cf]);xp=ip.fit_transform(px.loc[tr,pf]);tp=ip.transform(px.loc[te,pf])
  for leaf,lr in specs:
   hc=hgb(leaf,lr);hp=hgb(leaf,lr);hc.fit(xc,df.loc[tr,"home_win"]);hp.fit(xp,df.loc[tr,"home_win"]);pn=.25*hc.predict_proba(tc)[:,1]+.75*hp.predict_proba(tp)[:,1]
   for w in [.15,.25,.35]:parts[f"hgb_l{leaf}_lr{int(lr*100):02d}_w{int(w*100)}"].append((1-w)*pv+w*pn)
 y=np.concatenate(ys);v1=np.concatenate(v1parts);sa=np.asarray(seasons);cand={"v1":v1,**{k:np.concatenate(v) for k,v in parts.items()}};res={}
 for n,p in cand.items():res[n]={"overall":score(y,p),"recent_2023_2025":score(y[sa>=2023],p[sa>=2023]),"by_season":{str(s):score(y[sa==s],p[sa==s]) for s in range(2018,2026)}}
 baseb=res["v1"]["overall"]["brier"]
 for n in res:res[n]["delta_brier"]=res[n]["overall"]["brier"]-baseb;res[n]["seasons_improved"]=sum(res[n]["by_season"][str(s)]["brier"]<res["v1"]["by_season"][str(s)]["brier"] for s in range(2018,2026))
 ranked=sorted(parts,key=lambda n:(res[n]["overall"]["brier"],res[n]["recent_2023_2025"]["brier"]));folds=[];meta_p=[];meta_y=[]
 for target in range(2021,2026):
  prior=sa<target;test=sa==target;chosen=min(parts,key=lambda n:brier_score_loss(y[prior],cand[n][prior]));p=cand[chosen][test];yy=y[test];folds.append({"season":target,"chosen":chosen,"challenger":score(yy,p),"v1":score(yy,v1[test])});meta_p.append(p);meta_y.append(yy)
 my=np.concatenate(meta_y);mp=np.concatenate(meta_p);mv=v1[sa>=2021];payload={"selection_window":"2018-2025","2026_touched":False,"market_used":False,"ranking":ranked,"candidates":res,"meta_walkforward":{"folds":folds,"challenger":score(my,mp),"v1":score(my,mv)}}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 meta=[c for c in ["game_id","season","week","conference_game","neutral_site","home_team","away_team"] if c in df.columns]
 oof=df.loc[df.season.between(2018,2025),meta].reset_index(drop=True).copy();oof["home_win"]=y
 for name,p in cand.items():oof[name]=p
 oof.to_csv(out/"nonlinear_oof_candidates.csv",index=False)
 (out/"nonlinear_challenger.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Nonlinear Challenger","","Shallow histogram gradient boosting uses only the same leakage-safe, market-free feature families as V1. Every season is trained on prior seasons only; 2026 is excluded.","","| Candidate | Accuracy | Brier | Delta Brier | Recent Brier | Seasons improved |","|---|---:|---:|---:|---:|---:|"]
 for n in ranked[:10]:
  x=res[n];lines.append(f"| {n} | {x['overall']['accuracy']:.2%} | {x['overall']['brier']:.6f} | {x['delta_brier']:+.6f} | {x['recent_2023_2025']['brier']:.6f} | {x['seasons_improved']}/8 |")
 mm=payload["meta_walkforward"];lines+=["","## Sequential configuration selection","",f"- V1 2021-2025: {mm['v1']['accuracy']:.2%} accuracy / {mm['v1']['brier']:.6f} Brier.",f"- Nonlinear challenger: {mm['challenger']['accuracy']:.2%} accuracy / {mm['challenger']['brier']:.6f} Brier.","","| Season | Chosen using prior seasons | Challenger Brier | V1 Brier |","|---|---|---:|---:|"]
 for f in folds:lines.append(f"| {f['season']} | {f['chosen']} | {f['challenger']['brier']:.6f} | {f['v1']['brier']:.6f} |")
 (out/"NONLINEAR_CHALLENGER.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
