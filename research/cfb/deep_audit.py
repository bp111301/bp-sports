"""Deep audit of frozen CFB V1 using development OOF predictions only."""
from __future__ import annotations
import argparse, importlib.util, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss
HERE=Path(__file__).parent
def mod(name,file):
    s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py")
def boolish(s):
    if getattr(s,"dtype",None)==object:return s.astype(str).str.lower().isin(["true","1","yes"])
    return s.fillna(False).astype(bool)
def matrices(df):
    bx=base.build_matrix(df);cf=base.feature_sets(bx)["cfb_context"];px=pri.matrix(df,7.0)
    rem={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES}
    pf=[c for c in cf if c not in rem]+[f"blend_{f}_diff" for f in pri.BLEND_BASES]
    return bx,cf,px,pf
def frozen_oof(df):
    bx,cf,px,pf=matrices(df);parts=[]
    for season in range(2018,2026):
        tr=df.index[df.season<season];te=df.index[df.season==season]
        mc=base.model(cf);mp=base.model(pf);mc.fit(bx.loc[tr,cf],df.loc[tr,"home_win"]);mp.fit(px.loc[tr,pf],df.loc[tr,"home_win"])
        p=.25*mc.predict_proba(bx.loc[te,cf])[:,1]+.75*mp.predict_proba(px.loc[te,pf])[:,1]
        keep=[c for c in ["game_id","season","week","home_team","away_team","home_win","neutral_site","conference_game"] if c in df]
        z=df.loc[te,keep].copy();z["p_home"]=p;z["pred_home"]=(p>=.5).astype(int);z["confidence"]=np.maximum(p,1-p);z["correct"]=(z.pred_home==z.home_win).astype(int);parts.append(z)
    return pd.concat(parts,ignore_index=True)
def metrics(g):
    if len(g)==0:return {}
    y=g.home_win.to_numpy();p=g.p_home.to_numpy()
    return {"games":int(len(g)),"accuracy":float(g.correct.mean()),"mean_confidence":float(g.confidence.mean()),"calibration_gap":float(g.confidence.mean()-g.correct.mean()),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}
def wilson(k,n,z=1.96):
    if not n:return [None,None]
    ph=k/n;d=1+z*z/n;c=(ph+z*z/(2*n))/d;h=z*math.sqrt(ph*(1-ph)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]
def threshold_rows(pred):
    out=[]
    for t in [.55,.60,.65,.70,.75,.80,.85,.90,.95]:
        g=pred[pred.confidence>=t];m=metrics(g);lo,hi=wilson(int(g.correct.sum()),len(g));out.append({"threshold":t,**m,"accuracy_ci95_low":lo,"accuracy_ci95_high":hi})
    return out
def calibration_rows(pred):
    cuts=[.50,.55,.60,.65,.70,.75,.80,.85,.90,.95,1.001];out=[]
    for lo,hi in zip(cuts[:-1],cuts[1:]):
        g=pred[(pred.confidence>=lo)&(pred.confidence<hi)]
        if len(g):out.append({"bucket":f"{lo:.0%}-{min(hi,1):.0%}",**metrics(g)})
    return out
def grouped(pred,key):return [{"group":str(k),**metrics(g)} for k,g in pred.groupby(key,dropna=False,observed=False)]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
    df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);pred=frozen_oof(df)
    pred["era"]=np.where(pred.season<=2022,"2018-2022","2023-2025");wk=pd.to_numeric(pred.week,errors="coerce");pred["week_band"]=pd.cut(wk,[0,3,6,9,99],labels=["Weeks 1-3","Weeks 4-6","Weeks 7-9","Weeks 10+"])
    if "neutral_site" in pred:pred["site"]=np.where(boolish(pred.neutral_site),"Neutral","Home field")
    if "conference_game" in pred:pred["game_type"]=np.where(boolish(pred.conference_game),"Conference","Non-conference")
    overall=metrics(pred);cal=calibration_rows(pred);thresholds=threshold_rows(pred);ece=sum(r["games"]/overall["games"]*abs(r["calibration_gap"]) for r in cal);mce=max(abs(r["calibration_gap"]) for r in cal)
    payload={"version":"CFB_V1_AUDIT","selection_data":"2018-2025 OOF only","2026_used_for_selection":False,"overall":overall,"ece":ece,"max_calibration_error":mce,"calibration":cal,"confidence_thresholds":thresholds,"by_season":grouped(pred,"season"),"by_era":grouped(pred,"era"),"by_week_band":grouped(pred,"week_band")}
    if "site" in pred:payload["by_site"]=grouped(pred,"site")
    if "game_type" in pred:payload["by_game_type"]=grouped(pred,"game_type")
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);pred.to_csv(out/"cfb_v1_oof_predictions.csv",index=False);(out/"cfb_v1_deep_audit.json").write_text(json.dumps(payload,indent=2)+"\n")
    pct=lambda x:f"{x:.2%}"
    lines=["# CFB V1 Deep Audit","","Frozen V1 reconstructed out-of-fold on 2018-2025 only. No 2026 result is model-selection data.","",f"- Games: {overall['games']:,}",f"- Accuracy: {pct(overall['accuracy'])}",f"- Brier: {overall['brier']:.4f}",f"- Log loss: {overall['log_loss']:.4f}",f"- ECE: {ece:.4f}",f"- Max 5-point-bin calibration error: {mce:.4f}","","## High-confidence reliability","","| Minimum confidence | Games | Accuracy | Mean confidence | Gap | 95% accuracy interval |","|---|---:|---:|---:|---:|---:|"]
    for r in thresholds:lines.append(f"| {r['threshold']:.0%}+ | {r['games']:,} | {pct(r['accuracy'])} | {pct(r['mean_confidence'])} | {r['calibration_gap']:+.2%} | {pct(r['accuracy_ci95_low'])}–{pct(r['accuracy_ci95_high'])} |")
    lines+=["","## Calibration buckets","","| Bucket | Games | Accuracy | Mean confidence | Gap |","|---|---:|---:|---:|---:|"]
    for r in cal:lines.append(f"| {r['bucket']} | {r['games']:,} | {pct(r['accuracy'])} | {pct(r['mean_confidence'])} | {r['calibration_gap']:+.2%} |")
    for title,key in [("Era stability","by_era"),("Week stability","by_week_band"),("Site stability","by_site"),("Conference split","by_game_type")]:
        if key not in payload:continue
        lines+=["",f"## {title}","","| Group | Games | Accuracy | Brier | Mean confidence | Gap |","|---|---:|---:|---:|---:|---:|"]
        for r in payload[key]:lines.append(f"| {r['group']} | {r['games']:,} | {pct(r['accuracy'])} | {r['brier']:.4f} | {pct(r['mean_confidence'])} | {r['calibration_gap']:+.2%} |")
    (out/"CFB_V1_DEEP_AUDIT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
