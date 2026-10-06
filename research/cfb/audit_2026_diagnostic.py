"""Audit the already-opened 2026 untouched diagnostic without tuning V1."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import brier_score_loss,log_loss
def score(g):
    y=g.home_win.astype(int).to_numpy();p=g.home_win_prob.astype(float).to_numpy();c=np.maximum(p,1-p);correct=((p>=.5).astype(int)==y)
    return {"games":int(len(g)),"accuracy":float(correct.mean()),"mean_confidence":float(c.mean()),"gap":float(c.mean()-correct.mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--pred",default="research/cfb/results/holdout_2026_predictions.csv");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
    df=pd.read_csv(a.pred);df["confidence"]=np.maximum(df.home_win_prob,1-df.home_win_prob);rows=[]
    for t in [.60,.70,.80,.90]:
        g=df[df.confidence>=t]
        if len(g):rows.append({"threshold":t,**score(g)})
    payload={"classification":"untouched diagnostic; never model-selection data for CFB V1","overall":score(df),"confidence_thresholds":rows}
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"diagnostic_2026_audit.json").write_text(json.dumps(payload,indent=2)+"\n")
    lines=["# 2026 Diagnostic Confidence Audit","","Diagnostic evidence only. It cannot change frozen CFB V1.","",f"Overall: {payload['overall']['accuracy']:.2%} accuracy across {payload['overall']['games']} games; Brier {payload['overall']['brier']:.4f}.","","| Threshold | Games | Accuracy | Mean confidence | Gap |","|---|---:|---:|---:|---:|"]
    for r in rows:lines.append(f"| {r['threshold']:.0%}+ | {r['games']} | {r['accuracy']:.2%} | {r['mean_confidence']:.2%} | {r['gap']:+.2%} |")
    (out/"DIAGNOSTIC_2026_AUDIT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
