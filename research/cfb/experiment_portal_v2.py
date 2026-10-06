"""CFB V2 transfer-portal / roster-churn feature experiment.

Uses SportsDataverse season-level roster diffs (available 2015+) as preseason
context. This is research only. Because the release is reconstructed from
season rosters, any promotion requires a separate point-in-time timing audit.
2026 is excluded from selection.
"""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py")
PF=["roster_n","transfers_in_n","transfers_out_n","portal_share","transfer_talent_in","transfer_talent_out","net_transfer_talent"]
def load_portal(path):
 fs=sorted(Path(path).glob("cfb_team_portal_*.parquet"));return pd.concat([pd.read_parquet(f) for f in fs],ignore_index=True)
def add_portal(df,x,p):
 hc="home_team_id" if "home_team_id" in df else "home_id";ac="away_team_id" if "away_team_id" in df else "away_id"
 cols=["season","team_id"]+PF;q=p[cols].copy();q["season"]=pd.to_numeric(q.season,errors="coerce");q["team_id"]=pd.to_numeric(q.team_id,errors="coerce")
 h=q.rename(columns={"team_id":hc,**{c:"home_"+c for c in PF}});a=q.rename(columns={"team_id":ac,**{c:"away_"+c for c in PF}})
 z=df[["season",hc,ac]].merge(h,on=["season",hc],how="left").merge(a,on=["season",ac],how="left")
 for c in PF:x["portal_"+c+"_diff"]=pd.to_numeric(z["home_"+c],errors="coerce").to_numpy()-pd.to_numeric(z["away_"+c],errors="coerce").to_numpy()
 return x
def matrices(df,p):
 bx=base.build_matrix(df);cf=base.feature_sets(bx)["cfb_context"];px=pri.matrix(df,7.0);rem={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES};pf=[c for c in cf if c not in rem]+[f"blend_{f}_diff" for f in pri.BLEND_BASES]
 bx=add_portal(df,bx,p);px=add_portal(df,px,p);qf=["portal_"+c+"_diff" for c in PF];return bx,cf,px,pf,qf
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--portal-dir",default="runtime/cfb/team_portal");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);p=load_portal(a.portal_dir);bx,cf,px,pf,qf=matrices(df,p)
 variants={"v1":(False,False),"portal_context":(True,False),"portal_prior":(False,True),"portal_both":(True,True)};parts={k:[] for k in variants};ys=[];ss=[];weeks=[]
 for season in range(2018,2026):
  tr=df.index[df.season<season];te=df.index[df.season==season];y=df.loc[te,"home_win"].to_numpy();ys.append(y);ss.extend([season]*len(te));weeks.extend(df.loc[te,"week"].tolist())
  for name,(cq,pq) in variants.items():
   cfeat=cf+(qf if cq else []);pfeat=pf+(qf if pq else []);mc=base.model(cfeat);mp=base.model(pfeat);mc.fit(bx.loc[tr,cfeat],df.loc[tr,"home_win"]);mp.fit(px.loc[tr,pfeat],df.loc[tr,"home_win"]);parts[name].append(.25*mc.predict_proba(bx.loc[te,cfeat])[:,1]+.75*mp.predict_proba(px.loc[te,pfeat])[:,1])
 y=np.concatenate(ys);season=np.asarray(ss);week=pd.to_numeric(pd.Series(weeks),errors="coerce").to_numpy();res={}
 for n,v in parts.items():
  prob=np.concatenate(v);recent=season>=2023;early=week<=3;res[n]={"overall":base.score(y,prob),"recent_2023_2025":base.score(y[recent],prob[recent]),"weeks_1_3":base.score(y[early],prob[early])}
 b=res["v1"]["overall"]["brier"]
 for n in res:res[n]["delta_brier"]=res[n]["overall"]["brier"]-b
 coverage={c:float(bx["portal_"+c+"_diff"].notna().mean()) for c in PF}
 ranked=sorted(res,key=lambda n:res[n]["overall"]["brier"]);payload={"selection_window":"2018-2025","2026_touched":False,"timing_status":"requires point-in-time audit before promotion","coverage":coverage,"ranking":ranked,"candidates":res}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"portal_experiment.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Transfer / Roster-Churn Experiment","","Season-level roster-diff features are tested as preseason context. 2026 is excluded. These features cannot be promoted until their historical point-in-time semantics pass a separate timing audit.","","| Candidate | Accuracy | Brier | Δ Brier | Recent Brier | Weeks 1-3 Brier |","|---|---:|---:|---:|---:|---:|"]
 for n in ranked:
  x=res[n];lines.append(f"| {n} | {x['overall']['accuracy']:.2%} | {x['overall']['brier']:.6f} | {x['delta_brier']:+.6f} | {x['recent_2023_2025']['brier']:.6f} | {x['weeks_1_3']['brier']:.6f} |")
 lines+=["","Feature coverage: "+", ".join(f"{k} {v:.1%}" for k,v in coverage.items())+"."]
 (out/"PORTAL_EXPERIMENT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
