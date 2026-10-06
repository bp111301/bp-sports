"""External market benchmark for CFB V1/V2 research.

Point spreads are NEVER fed into the B.P. winner model. This script fits a
spread-only logistic mapping on prior seasons and uses it solely as a benchmark
for how much information the independent model is capturing.
"""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss,log_loss
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");audit=mod("audit","deep_audit.py")
def score(y,p):
 y=np.asarray(y,int);p=np.asarray(p,float);pred=(p>=.5).astype(int)
 return {"games":int(len(y)),"accuracy":float((pred==y).mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1])),"mean_confidence":float(np.maximum(p,1-p).mean())}
def market_oof(df,col):
 out=[]
 for season in range(2018,2026):
  tr=df[(df.season<season)&pd.to_numeric(df[col],errors="coerce").notna()]
  te=df[(df.season==season)&pd.to_numeric(df[col],errors="coerce").notna()]
  if tr.empty or te.empty:continue
  xtr=pd.to_numeric(tr[col],errors="coerce").to_numpy().reshape(-1,1);xte=pd.to_numeric(te[col],errors="coerce").to_numpy().reshape(-1,1)
  m=LogisticRegression(C=1e6,max_iter=2000);m.fit(xtr,tr.home_win);p=m.predict_proba(xte)[:,1]
  z=te[["game_id","season","home_win"]].copy();z["market_p_home"]=p;z["line"]=xte[:,0];out.append(z)
 return pd.concat(out,ignore_index=True)
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);v1=audit.frozen_oof(df)[["game_id","p_home"]].rename(columns={"p_home":"v1_p_home"})
 result={}
 for col in ["spread_open","spread"]:
  if col not in df:continue
  m=market_oof(df,col).merge(v1,on="game_id",how="inner");y=m.home_win.to_numpy();pm=m.market_p_home.to_numpy();pv=m.v1_p_home.to_numpy()
  nz=m.line!=0;fav=np.where(m.loc[nz,"line"].to_numpy()<0,1,0)
  result[col]={"coverage_games":int(len(m)),"market":score(y,pm),"v1_same_games":score(y,pv),"market_minus_v1_brier":float(brier_score_loss(y,pm)-brier_score_loss(y,pv)),"spread_favorite_accuracy_ex_pk":float((fav==m.loc[nz,"home_win"].to_numpy()).mean()) if nz.any() else None}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"market_benchmark.json").write_text(json.dumps({"market_firewall":True,"2026_touched":False,"method":"spread-only logistic fit on prior seasons; benchmark only", "benchmarks":result},indent=2)+"\n")
 lines=["# CFB External Market Benchmark","","The point spread remains outside the B.P. winner model. This is a benchmark only: each season's spread-to-win-probability mapping is fit using prior seasons, then evaluated on that season.","","| Benchmark | Games | Market accuracy | V1 accuracy | Market Brier | V1 Brier | Market − V1 Brier |","|---|---:|---:|---:|---:|---:|---:|"]
 for col,x in result.items():lines.append(f"| {col} | {x['coverage_games']:,} | {x['market']['accuracy']:.2%} | {x['v1_same_games']['accuracy']:.2%} | {x['market']['brier']:.4f} | {x['v1_same_games']['brier']:.4f} | {x['market_minus_v1_brier']:+.4f} |")
 lines+=["","This benchmark is deliberately difficult. Historical betting spreads aggregate information from many participants and are widely documented as strong predictors of college-football outcomes. Beating V1 is not enough for V2; the long-term goal is to identify independent information the market does not already contain."]
 (out/"MARKET_BENCHMARK.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
