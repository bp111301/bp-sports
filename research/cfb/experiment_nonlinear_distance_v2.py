"""Test whether leakage-safe travel distance adds to the leading nonlinear CFB V2 architecture."""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.impute import SimpleImputer
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");audit=mod("audit","deep_audit.py");nl=mod("nl","experiment_nonlinear_v2.py")
def hav(a,b,c,d):
 a=np.radians(pd.to_numeric(a,errors="coerce"));c=np.radians(pd.to_numeric(c,errors="coerce"));dl=np.radians(pd.to_numeric(d,errors="coerce")-pd.to_numeric(b,errors="coerce"));q=np.sin((c-a)/2)**2+np.cos(a)*np.cos(c)*np.sin(dl/2)**2;return 3958.761*np.arcsin(np.sqrt(np.clip(q,0,1)))
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);bx,cf,px,pf=audit.matrices(df);neutral=df.neutral_site.astype(str).str.lower().isin(["true","1","yes"]) if df.neutral_site.dtype==object else df.neutral_site.fillna(False).astype(bool);bx["travel_miles"]=hav(df.away_latitude,df.away_longitude,df.home_latitude,df.home_longitude);bx.loc[neutral,"travel_miles"]=np.nan;cdf=cf+["travel_miles"]
 parts={k:[] for k in ["v1","v1_distance","hgb","hgb_distance_signal","hgb_distance_full"]};ys=[];ss=[]
 for season in range(2018,2026):
  tr=df.index[df.season<season];te=df.index[df.season==season];y=df.loc[te,"home_win"].to_numpy();ys.append(y);ss.extend([season]*len(te))
  mp=base.model(pf);mp.fit(px.loc[tr,pf],df.loc[tr,"home_win"]);pp=mp.predict_proba(px.loc[te,pf])[:,1]
  mc=base.model(cf);mc.fit(bx.loc[tr,cf],df.loc[tr,"home_win"]);pv=.25*mc.predict_proba(bx.loc[te,cf])[:,1]+.75*pp;parts["v1"].append(pv)
  md=base.model(cdf);md.fit(bx.loc[tr,cdf],df.loc[tr,"home_win"]);pvd=.25*md.predict_proba(bx.loc[te,cdf])[:,1]+.75*pp;parts["v1_distance"].append(pvd)
  ic=SimpleImputer(strategy="median",add_indicator=True);id=SimpleImputer(strategy="median",add_indicator=True);ip=SimpleImputer(strategy="median",add_indicator=True);xc=ic.fit_transform(bx.loc[tr,cf]);tc=ic.transform(bx.loc[te,cf]);xd=id.fit_transform(bx.loc[tr,cdf]);td=id.transform(bx.loc[te,cdf]);xp=ip.fit_transform(px.loc[tr,pf]);tp=ip.transform(px.loc[te,pf])
  hc=nl.hgb(7,.03);hd=nl.hgb(7,.03);hp=nl.hgb(7,.03);hc.fit(xc,df.loc[tr,"home_win"]);hd.fit(xd,df.loc[tr,"home_win"]);hp.fit(xp,df.loc[tr,"home_win"]);pnb=.25*hc.predict_proba(tc)[:,1]+.75*hp.predict_proba(tp)[:,1];pnd=.25*hd.predict_proba(td)[:,1]+.75*hp.predict_proba(tp)[:,1]
  parts["hgb"].append(.65*pv+.35*pnb);parts["hgb_distance_signal"].append(.65*pv+.35*pnd);parts["hgb_distance_full"].append(.65*pvd+.35*pnd)
 y=np.concatenate(ys);sa=np.asarray(ss);cand={k:np.concatenate(v) for k,v in parts.items()};res={}
 for n,p in cand.items():res[n]={"overall":base.score(y,p),"recent":base.score(y[sa>=2023],p[sa>=2023]),"target_2021_2025":base.score(y[sa>=2021],p[sa>=2021]),"by_season":{str(s):base.score(y[sa==s],p[sa==s]) for s in range(2018,2026)}}
 b=res["hgb"]["target_2021_2025"]["brier"]
 for n in res:res[n]["target_delta_vs_hgb"]=res[n]["target_2021_2025"]["brier"]-b
 payload={"2026_touched":False,"market_used":False,"nonlinear_spec":"leaf7 lr0.03, 35% nonlinear blend","candidates":res};out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"nonlinear_distance.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Nonlinear + Distance","","Tests the already-selected shallow nonlinear architecture with one leakage-safe travel-distance feature. Hyperparameters remain fixed; 2026 and market data are excluded.","","| Candidate | Overall accuracy | Overall Brier | 2021-25 accuracy | 2021-25 Brier | Delta vs HGB |","|---|---:|---:|---:|---:|---:|"]
 for n in parts:
  x=res[n];lines.append(f"| {n} | {x['overall']['accuracy']:.2%} | {x['overall']['brier']:.6f} | {x['target_2021_2025']['accuracy']:.2%} | {x['target_2021_2025']['brier']:.6f} | {x['target_delta_vs_hgb']:+.6f} |")
 (out/"NONLINEAR_DISTANCE.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
