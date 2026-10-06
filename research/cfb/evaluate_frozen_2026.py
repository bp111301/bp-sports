"""Evaluate frozen CFB V1 on completed 2026 games."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).parent
def mod(name,file):
    s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py"); pri=mod("pri","experiment_priors.py")
def matrices(df):
    bx=base.build_matrix(df); context=base.feature_sets(bx)["cfb_context"]; px=pri.matrix(df,7.0)
    rem={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES}
    pf=[c for c in context if c not in rem]+[f"blend_{f}_diff" for f in pri.BLEND_BASES]
    return bx,context,px,pf
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/results");a=ap.parse_args()
    df=base.load_data(Path(a.data_dir));train=df[df.season<=2025].copy().reset_index(drop=True);test=df[df.season==2026].copy().reset_index(drop=True)
    if test.empty: raise SystemExit("No completed 2026 games in source snapshot.")
    bx,cf,px,pf=matrices(train);tbx,_,tpx,_=matrices(test)
    mc=base.model(cf);mp=base.model(pf);mc.fit(bx[cf],train.home_win);mp.fit(px[pf],train.home_win)
    pc=mc.predict_proba(tbx[cf])[:,1];pp=mp.predict_proba(tpx[pf])[:,1];p=.25*pc+.75*pp
    overall=base.score(test.home_win.to_numpy(),p);rows=[]
    for week,g in test.assign(prob=p).groupby("week"):rows.append({"week":int(week),**base.score(g.home_win.to_numpy(),g.prob.to_numpy())})
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    pred=test[["game_id","season","week","home_team","away_team","home_points","away_points","home_win"]].copy();pred["home_win_prob"]=p;pred["predicted_winner"]=np.where(p>=.5,pred.home_team,pred.away_team);pred.to_csv(out/"holdout_2026_predictions.csv",index=False)
    payload={"frozen_before_opening_2026":True,"classification":"untouched diagnostic for pre-freeze completed games","overall":overall,"by_week":rows};(out/"holdout_2026.json").write_text(json.dumps(payload,indent=2)+"\n")
    lines=["# CFB V1 — 2026 Untouched Diagnostic","","CFB V1 was frozen before this result was opened. Games completed before the freeze are untouched holdout diagnostics, not prospective predictions.","",f"- Games: {overall['games']:,}",f"- Accuracy: {overall['accuracy']:.2%}",f"- Brier: {overall['brier']:.4f}",f"- Log loss: {overall['log_loss']:.4f}","","These results cannot change CFB V1."]
    (out/"HOLDOUT_2026_REPORT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
