"""Sequential test of whether B.P. model probabilities add information beyond spreads.

This is diagnostic only. Market data remains firewalled from production winner
selection. For each target season, a margin architecture is chosen using only
earlier OOF seasons; then market-only and market+model logistic meta-models are
fit on earlier seasons and scored on the target season.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss,log_loss
def logit(p):
 p=np.clip(np.asarray(p,float),1e-5,1-1e-5);return np.log(p/(1-p))
def score(y,p):
 y=np.asarray(y,int);p=np.asarray(p,float);return {"games":int(len(y)),"accuracy":float(((p>=.5).astype(int)==y).mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}
def fitpred(tr,te,cols):
 m=LogisticRegression(C=1e6,max_iter=3000);m.fit(tr[cols],tr.home_win);return m.predict_proba(te[cols])[:,1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--oof",default="research/cfb/v2_results/margin_oof_candidates.csv");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 raw=pd.concat([pd.read_csv(f,low_memory=False) for f in sorted(Path(a.data_dir).glob("cfb_matchup_line_*.csv"))],ignore_index=True)
 market=raw[["game_id","spread_open","spread"]].drop_duplicates("game_id");oof=pd.read_csv(a.oof).merge(market,on="game_id",how="left");blends=[c for c in oof if c.startswith("blend_")];results={}
 for line in ["spread_open","spread"]:
  folds=[];allrows=[]
  for target in range(2020,2026):
   prior=oof[(oof.season>=2018)&(oof.season<target)].copy();test=oof[oof.season==target].copy()
   ranked=sorted(blends,key=lambda c:brier_score_loss(prior.home_win,prior[c]));chosen=ranked[0]
   prior["model_logit"]=logit(prior.v1);test["model_logit"]=logit(test.v1);prior["margin_logit"]=logit(prior[chosen]);test["margin_logit"]=logit(test[chosen])
   prior[line]=pd.to_numeric(prior[line],errors="coerce");test[line]=pd.to_numeric(test[line],errors="coerce");tr=prior.dropna(subset=[line]);te=test.dropna(subset=[line])
   if len(tr)<200 or te.empty:continue
   pm=fitpred(tr,te,[line]);pv=fitpred(tr,te,[line,"model_logit"]);px=fitpred(tr,te,[line,"model_logit","margin_logit"]);y=te.home_win.to_numpy()
   folds.append({"season":target,"chosen_margin":chosen,"games":int(len(te)),"market":score(y,pm),"market_plus_v1":score(y,pv),"market_plus_v1_margin":score(y,px)})
   z=pd.DataFrame({"y":y,"market":pm,"market_plus_v1":pv,"market_plus_v1_margin":px});allrows.append(z)
  if not allrows:continue
  z=pd.concat(allrows,ignore_index=True);agg={k:score(z.y,z[k]) for k in ["market","market_plus_v1","market_plus_v1_margin"]}
  agg["v1_brier_gain_vs_market"]=agg["market_plus_v1"]["brier"]-agg["market"]["brier"];agg["v1_margin_brier_gain_vs_market"]=agg["market_plus_v1_margin"]["brier"]-agg["market"]["brier"]
  results[line]={"folds":folds,"aggregate":agg}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"market_incremental_information.json").write_text(json.dumps({"market_firewall":True,"2026_touched":False,"results":results},indent=2)+"\n")
 lines=["# CFB Incremental Information vs Market","","Diagnostic only. Market prices remain excluded from the B.P. production winner model. Each target season uses only earlier seasons for meta-model fitting and margin-candidate selection.","","| Line | Games | Market Brier | Market + V1 | Market + V1 + margin | Best Δ vs market |","|---|---:|---:|---:|---:|---:|"]
 for line,x in results.items():
  a=x["aggregate"];best=min(a["market_plus_v1"]["brier"],a["market_plus_v1_margin"]["brier"]);lines.append(f"| {line} | {a['market']['games']:,} | {a['market']['brier']:.6f} | {a['market_plus_v1']['brier']:.6f} | {a['market_plus_v1_margin']['brier']:.6f} | {best-a['market']['brier']:+.6f} |")
 lines+=["","A negative delta means the independent B.P. signal improved the spread-only benchmark out of sample. A positive delta means the market already subsumed the tested model information."]
 (out/"MARKET_INCREMENTAL_INFORMATION.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
