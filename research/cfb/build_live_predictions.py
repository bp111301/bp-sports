"""Build frozen CFB V1 predictions for future 2026 games and append immutable first snapshots."""
from __future__ import annotations
import argparse, importlib.util, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
HERE=Path(__file__).parent
def mod(name,file):
    s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py")
def matrices(df):
    bx=base.build_matrix(df);context=base.feature_sets(bx)["cfb_context"];px=pri.matrix(df,7.0)
    rem={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES}
    pf=[c for c in context if c not in rem]+[f"blend_{f}_diff" for f in pri.BLEND_BASES]
    return bx,context,px,pf
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--current-dir",default="data/cfb/current");ap.add_argument("--ledger",default="data/cfb/ledger/prediction_ledger.csv");ap.add_argument("--schedule",default="runtime/cfb/schedules/cfb_schedules_2026.csv.gz");ap.add_argument("--bundle",default="model/cfb/v1/frozen_bundle.joblib");ap.add_argument("--horizon-days",type=int,default=8);a=ap.parse_args()
    bundle=joblib.load(a.bundle)
    if bundle.get("version") != "CFB_V1":
        raise RuntimeError(f"Unexpected frozen bundle version: {bundle.get('version')}")
    raw=pd.read_csv(Path(a.data_dir)/"cfb_matchup_line_2026.csv",low_memory=False);raw["season"]=pd.to_numeric(raw.season,errors="coerce");raw["week"]=pd.to_numeric(raw.week,errors="coerce")
    schedule=pd.read_csv(a.schedule,low_memory=False)
    schedule["game_id"]=pd.to_numeric(schedule["game_id"],errors="coerce")
    schedule["exact_kickoff_utc"]=pd.to_datetime(schedule["start_date"],errors="coerce",utc=True)
    schedule=schedule[["game_id","exact_kickoff_utc","start_time_tbd","status","completed"]].drop_duplicates("game_id")
    raw["game_id"]=pd.to_numeric(raw["game_id"],errors="coerce")
    raw=raw.merge(schedule,on="game_id",how="left")
    raw["start_dt"]=raw["exact_kickoff_utc"]
    now=pd.Timestamp.now(tz="UTC");future=raw[(raw.season==2026)&raw.start_dt.notna()&(raw.start_dt>now)&(raw.start_dt<=now+pd.Timedelta(days=a.horizon_days))].copy().reset_index(drop=True)
    if future.empty: raise SystemExit("No future 2026 games found in source horizon.")
    fx=base.build_matrix(future)
    fpx=pri.matrix(future,float(bundle["prior_k"]))
    cf=list(bundle["context_features"]);pf=list(bundle["prior_features"])
    missing_context=[x for x in cf if x not in fx.columns]
    missing_prior=[x for x in pf if x not in fpx.columns]
    if missing_context or missing_prior:
        raise RuntimeError(f"Frozen feature mismatch: context={missing_context}, prior={missing_prior}")
    mc=bundle["context_model"];mp=bundle["prior_model"]
    pc=mc.predict_proba(fx[cf])[:,1];pp=mp.predict_proba(fpx[pf])[:,1]
    p=float(bundle["context_weight"])*pc+float(bundle["prior_weight"])*pp
    generated=datetime.now(timezone.utc).isoformat()
    out=pd.DataFrame({"prediction_id":["CFBV1_2026_"+str(x) for x in future.game_id],"model_version":"CFB_V1","snapshot_created_utc":generated,"game_id":future.game_id,"season":2026,"week":future.week.astype("Int64"),"kickoff_utc":future.start_dt.astype(str),"kickoff_time_tbd":future["start_time_tbd"],"away_team":future.away_team,"home_team":future.home_team,"predicted_winner":np.where(p>=.5,future.home_team,future.away_team),"home_win_prob":p,"confidence":np.maximum(p,1-p),"market_used_for_pick":False,"status":"PREGAME_SNAPSHOT"}).sort_values(["kickoff_utc","game_id"])
    cur=Path(a.current_dir);cur.mkdir(parents=True,exist_ok=True);out.to_csv(cur/"predictions.csv",index=False);(cur/"metadata.json").write_text(json.dumps({"model_version":"CFB_V1","generated_at_utc":generated,"games":int(len(out)),"horizon_days":a.horizon_days,"market_used_for_pick":False},indent=2)+"\n")
    ledger=Path(a.ledger);ledger.parent.mkdir(parents=True,exist_ok=True)
    if ledger.exists():
        old=pd.read_csv(ledger);existing=set(old.prediction_id.astype(str));add=out[~out.prediction_id.astype(str).isin(existing)];combined=pd.concat([old,add],ignore_index=True)
    else:combined=out.copy()
    combined.to_csv(ledger,index=False);print(f"current slate: {len(out)}; immutable ledger rows: {len(combined)}")
if __name__=="__main__":main()
