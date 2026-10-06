"""One-shot 2026 diagnostic for locked CFB V2 Candidate A. Do not tune from this result."""
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
 df=base.load_data(Path(a.data_dir));tr=df.index[df.season<=2025];te=df.index[df.season==2026]
 if not len(te):raise RuntimeError("No completed 2026 games")
 bx,cf,px,pf=audit.matrices(df);neutral=df.neutral_site.astype(str).str.lower().isin(["true","1","yes"]) if df.neutral_site.dtype==object else df.neutral_site.fillna(False).astype(bool);bx["travel_miles"]=hav(df.away_latitude,df.away_longitude,df.home_latitude,df.home_longitude);bx.loc[neutral,"travel_miles"]=np.nan;cdf=cf+["travel_miles"];ytr=df.loc[tr,"home_win"];y=df.loc[te,"home_win"].to_numpy()
 # Frozen-style V1 reconstruction.
 mc=base.model(cf);mp=base.model(pf);mc.fit(bx.loc[tr,cf],ytr);mp.fit(px.loc[tr,pf],ytr);pv=.25*mc.predict_proba(bx.loc[te,cf])[:,1]+.75*mp.predict_proba(px.loc[te,pf])[:,1]
 # Candidate A logistic distance branch.
 md=base.model(cdf);md.fit(bx.loc[tr,cdf],ytr);pl=.25*md.predict_proba(bx.loc[te,cdf])[:,1]+.75*mp.predict_proba(px.loc[te,pf])[:,1]
 # Candidate A nonlinear distance branch.
 ic=SimpleImputer(strategy="median",add_indicator=True);ip=SimpleImputer(strategy="median",add_indicator=True);xc=ic.fit_transform(bx.loc[tr,cdf]);tc=ic.transform(bx.loc[te,cdf]);xp=ip.fit_transform(px.loc[tr,pf]);tp=ip.transform(px.loc[te,pf]);hc=nl.hgb(7,.03);hp=nl.hgb(7,.03);hc.fit(xc,ytr);hp.fit(xp,ytr);pn=.25*hc.predict_proba(tc)[:,1]+.75*hp.predict_proba(tp)[:,1];pa=.65*pl+.35*pn
 result={"classification":"one-shot 2026 diagnostic opened after Candidate A spec lock","candidate_locked_before_2026":True,"games":int(len(te)),"v1":base.score(y,pv),"candidate_a":base.score(y,pa)}
 result["delta"]={"accuracy":result["candidate_a"]["accuracy"]-result["v1"]["accuracy"],"brier":result["candidate_a"]["brier"]-result["v1"]["brier"],"log_loss":result["candidate_a"]["log_loss"]-result["v1"]["log_loss"]}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"candidate_a_2026.json").write_text(json.dumps(result,indent=2)+"\n")
 z=df.loc[te,["game_id","season","week","home_team","away_team","home_win"]].copy();z["v1_p_home"]=pv;z["candidate_a_p_home"]=pa;z.to_csv(out/"candidate_a_2026_predictions.csv",index=False)
 lines=["# CFB V2 Candidate A — One-Shot 2026 Diagnostic","","Candidate A was committed and locked before this result was opened. This result cannot be used to modify Candidate A.","",f"- Games: {len(te):,}",f"- V1: {result['v1']['accuracy']:.2%} accuracy, {result['v1']['brier']:.6f} Brier, {result['v1']['log_loss']:.6f} log loss.",f"- Candidate A: {result['candidate_a']['accuracy']:.2%} accuracy, {result['candidate_a']['brier']:.6f} Brier, {result['candidate_a']['log_loss']:.6f} log loss.",f"- Delta: {result['delta']['accuracy']:+.2%} accuracy, {result['delta']['brier']:+.6f} Brier, {result['delta']['log_loss']:+.6f} log loss.","","Any future tuning creates a new candidate and forfeits 2026 as untouched evidence for that new candidate."]
 (out/"CANDIDATE_A_2026.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
