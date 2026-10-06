"""Audit B.P. disagreement with the opening CFB spread."""
from __future__ import annotations
import argparse,importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");audit=mod("audit","deep_audit.py")
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);v=audit.frozen_oof(df)[["game_id","season","home_win","p_home"]];rows=[]
 for season in range(2018,2026):
  tr=df[(df.season<season)&pd.to_numeric(df.spread_open,errors="coerce").notna()].copy();te=df[(df.season==season)&pd.to_numeric(df.spread_open,errors="coerce").notna()].copy()
  if len(tr)<200 or te.empty:continue
  m=LogisticRegression(C=1e6,max_iter=2000);m.fit(pd.to_numeric(tr.spread_open,errors="coerce").to_numpy().reshape(-1,1),tr.home_win);pm=m.predict_proba(pd.to_numeric(te.spread_open,errors="coerce").to_numpy().reshape(-1,1))[:,1]
  z=te[["game_id","season","home_win","spread_open"]].copy();z["market_p_home"]=pm;rows.append(z)
 x=pd.concat(rows,ignore_index=True).merge(v[["game_id","p_home"]],on="game_id",how="inner");x["diff"]=x.p_home-x.market_p_home;x["abs_diff"]=x["diff"].abs();x["bp_side_home"]=x["diff"]>0;x["bp_side_won"]=np.where(x.bp_side_home,x.home_win,1-x.home_win);x["market_prob_bp_side"]=np.where(x.bp_side_home,x.market_p_home,1-x.market_p_home)
 bands=[0,.025,.05,.075,.10,.15,1.0];bandrows=[]
 for lo,hi in zip(bands[:-1],bands[1:]):
  g=x[(x.abs_diff>=lo)&(x.abs_diff<hi)]
  if len(g):bandrows.append({"band":f"{lo:.1%}-{hi:.1%}","games":int(len(g)),"bp_side_win_rate":float(g.bp_side_won.mean()),"market_expected":float(g.market_prob_bp_side.mean()),"excess_vs_market":float(g.bp_side_won.mean()-g.market_prob_bp_side.mean()),"v1_brier":float(brier_score_loss(g.home_win,g.p_home)),"market_brier":float(brier_score_loss(g.home_win,g.market_p_home))})
 thresholds=[]
 for t in [.025,.05,.075,.10,.15]:
  g=x[x.abs_diff>=t];thresholds.append({"min_disagreement":t,"games":int(len(g)),"bp_side_win_rate":float(g.bp_side_won.mean()),"market_expected":float(g.market_prob_bp_side.mean()),"excess_vs_market":float(g.bp_side_won.mean()-g.market_prob_bp_side.mean()),"v1_brier":float(brier_score_loss(g.home_win,g.p_home)),"market_brier":float(brier_score_loss(g.home_win,g.market_p_home))})
 payload={"market_firewall":True,"2026_touched":False,"games":int(len(x)),"bands":bandrows,"thresholds":thresholds};out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"opening_market_disagreement.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB Opening-Market Disagreement Audit","","The opening spread is benchmark-only. It never enters B.P.'s winner model. Market probabilities are calibrated using prior seasons only; 2026 is excluded.","","| B.P. vs opening-market probability gap | Games | B.P.-lean side win rate | Market expected | Excess | V1 Brier | Market Brier |","|---|---:|---:|---:|---:|---:|---:|"]
 for r in bandrows:lines.append(f"| {r['band']} | {r['games']:,} | {r['bp_side_win_rate']:.2%} | {r['market_expected']:.2%} | {r['excess_vs_market']:+.2%} | {r['v1_brier']:.4f} | {r['market_brier']:.4f} |")
 lines+=["","## Cumulative disagreement thresholds","","| Minimum gap | Games | B.P.-lean win rate | Market expected | Excess |","|---|---:|---:|---:|---:|"]
 for r in thresholds:lines.append(f"| {r['min_disagreement']:.1%}+ | {r['games']:,} | {r['bp_side_win_rate']:.2%} | {r['market_expected']:.2%} | {r['excess_vs_market']:+.2%} |")
 (out/"OPENING_MARKET_DISAGREEMENT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
