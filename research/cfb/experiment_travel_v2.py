"""Leakage-safe travel/geography experiment for CFB V2."""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import brier_score_loss
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");audit=mod("audit","deep_audit.py")
TZ={"America/New_York":-5,"America/Detroit":-5,"America/Indiana/Indianapolis":-5,"America/Kentucky/Louisville":-5,"America/Chicago":-6,"America/Denver":-7,"America/Phoenix":-7,"America/Los_Angeles":-8,"America/Anchorage":-9,"Pacific/Honolulu":-10}
def hav(a,b,c,d):
 a=np.radians(pd.to_numeric(a,errors="coerce"));c=np.radians(pd.to_numeric(c,errors="coerce"));dl=np.radians(pd.to_numeric(d,errors="coerce")-pd.to_numeric(b,errors="coerce"));q=np.sin((c-a)/2)**2+np.cos(a)*np.cos(c)*np.sin(dl/2)**2;return 3958.761*np.arcsin(np.sqrt(np.clip(q,0,1)))
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);bx,cf,px,pf=audit.matrices(df)
 neutral=df.neutral_site.astype(str).str.lower().isin(["true","1","yes"]) if df.neutral_site.dtype==object else df.neutral_site.fillna(False).astype(bool)
 bx["travel_miles"]=hav(df.away_latitude,df.away_longitude,df.home_latitude,df.home_longitude);bx["tz_shift"]=df.home_timezone.map(TZ)-df.away_timezone.map(TZ);bx["elevation_gain"]=pd.to_numeric(df.home_elevation,errors="coerce")-pd.to_numeric(df.away_elevation,errors="coerce")
 for c in ["travel_miles","tz_shift","elevation_gain"]:bx.loc[neutral,c]=np.nan
 specs={"v1":[],"distance":["travel_miles"],"timezone":["tz_shift"],"elevation":["elevation_gain"],"all_travel":["travel_miles","tz_shift","elevation_gain"]};parts={k:[] for k in specs};ys=[];ss=[]
 for season in range(2018,2026):
  tr=df.index[df.season<season];te=df.index[df.season==season];y=df.loc[te,"home_win"].to_numpy();ys.append(y);ss.extend([season]*len(te));mp=base.model(pf);mp.fit(px.loc[tr,pf],df.loc[tr,"home_win"]);pp=mp.predict_proba(px.loc[te,pf])[:,1]
  for name,extra in specs.items():
   f=cf+extra;mc=base.model(f);mc.fit(bx.loc[tr,f],df.loc[tr,"home_win"]);parts[name].append(.25*mc.predict_proba(bx.loc[te,f])[:,1]+.75*pp)
 y=np.concatenate(ys);sa=np.asarray(ss);cand={k:np.concatenate(v) for k,v in parts.items()};res={}
 for n,p in cand.items():res[n]={"overall":base.score(y,p),"recent":base.score(y[sa>=2023],p[sa>=2023])}
 b=res["v1"]["overall"]["brier"]
 for n in res:res[n]["delta_brier"]=res[n]["overall"]["brier"]-b
 opts=[k for k in specs if k!="v1"];folds=[];pp=[];yy=[]
 for target in range(2021,2026):
  prior=sa<target;test=sa==target;chosen=min(opts,key=lambda k:brier_score_loss(y[prior],cand[k][prior]));folds.append({"season":target,"chosen":chosen,"challenger":base.score(y[test],cand[chosen][test]),"v1":base.score(y[test],cand["v1"][test])});pp.append(cand[chosen][test]);yy.append(y[test])
 payload={"2026_touched":False,"market_used":False,"neutral_travel_missing":True,"candidates":res,"meta_walkforward":{"folds":folds,"challenger":base.score(np.concatenate(yy),np.concatenate(pp)),"v1":base.score(y[sa>=2021],cand["v1"][sa>=2021])}}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"travel_experiment.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Travel / Geography","","Campus-to-campus travel is used only for non-neutral games; neutral-site travel is left missing. Static geography is known pregame. Market and 2026 data are excluded.","","| Candidate | Accuracy | Brier | Delta | Recent Brier |","|---|---:|---:|---:|---:|"]
 for n in specs:
  x=res[n];lines.append(f"| {n} | {x['overall']['accuracy']:.2%} | {x['overall']['brier']:.6f} | {x['delta_brier']:+.6f} | {x['recent']['brier']:.6f} |")
 mm=payload["meta_walkforward"];lines+=["",f"Sequential 2021-25: V1 {mm['v1']['brier']:.6f}; selected travel {mm['challenger']['brier']:.6f}."]
 (out/"TRAVEL_EXPERIMENT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
