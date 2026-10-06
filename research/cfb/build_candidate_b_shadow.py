"""Create immutable prospective shadow snapshots for frozen CFB V2 Candidate B."""
from __future__ import annotations
import argparse,importlib.util,json,math
from datetime import datetime,timezone
from pathlib import Path
import joblib,numpy as np,pandas as pd
from settlement_guard import verify_bundle
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py")
def normcdf(x):
 x=np.asarray(x,float);return .5*(1+np.vectorize(math.erf)(x/np.sqrt(2)))
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--schedule",default="runtime/cfb/schedules/cfb_schedules_2026.csv.gz");ap.add_argument("--bundle",default="model/cfb/v2/candidate_b_bundle.joblib");ap.add_argument("--current",default="data/cfb/v2_shadow/current.csv");ap.add_argument("--ledger",default="data/cfb/v2_shadow/prediction_ledger.csv");ap.add_argument("--metadata",default="data/cfb/v2_shadow/metadata.json");ap.add_argument("--horizon-days",type=int,default=8);a=ap.parse_args()
 manifest=verify_bundle(a.bundle,str(Path(a.bundle).parent/"candidate_b_manifest.json"))
 b=joblib.load(a.bundle)
 if b.get("version")!="CFB_V2_CANDIDATE_B" or b.get("status")!="PROSPECTIVE_SHADOW_ONLY":raise RuntimeError("Candidate B bundle identity/status mismatch")
 raw=pd.read_csv(Path(a.data_dir)/"cfb_matchup_line_2026.csv",low_memory=False);raw["season"]=pd.to_numeric(raw.season,errors="coerce");raw["week"]=pd.to_numeric(raw.week,errors="coerce");raw["game_id"]=pd.to_numeric(raw.game_id,errors="coerce")
 sch=pd.read_csv(a.schedule,low_memory=False);sch["game_id"]=pd.to_numeric(sch.game_id,errors="coerce");sch["kickoff"]=pd.to_datetime(sch.start_date,errors="coerce",utc=True);raw=raw.merge(sch[["game_id","kickoff","start_time_tbd"]].drop_duplicates("game_id"),on="game_id",how="left")
 now=pd.Timestamp.now(tz="UTC");f=raw[(raw.season==2026)&raw.kickoff.notna()&(raw.kickoff>now)&(raw.kickoff<=now+pd.Timedelta(days=a.horizon_days))].copy().reset_index(drop=True)
 if f.empty:raise SystemExit("No future 2026 games in shadow horizon")
 bx=base.build_matrix(f);px=pri.matrix(f,float(b["prior_k"]));cf=list(b["context_features"]);pf=list(b["prior_features"])
 pc=b["v1_context_model"].predict_proba(bx[cf])[:,1];pp=b["v1_prior_model"].predict_proba(px[pf])[:,1];pv=float(b["v1_context_weight"])*pc+float(b["v1_prior_weight"])*pp
 pred_margin=b["margin_model"].predict(bx[cf]);pm=normcdf(pred_margin/max(float(b["margin_sigma"]),1e-9));p=float(b["candidate_b_v1_weight"])*pv+float(b["candidate_b_margin_weight"])*pm
 created=datetime.now(timezone.utc).isoformat();out=pd.DataFrame({"prediction_id":["CFBV2B_2026_"+str(x) for x in f.game_id],"model_version":"CFB_V2_CANDIDATE_B","snapshot_created_utc":created,"game_id":f.game_id,"season":2026,"week":f.week.astype("Int64"),"kickoff_utc":f.kickoff.astype(str),"away_team":f.away_team,"home_team":f.home_team,"predicted_winner":np.where(p>=.5,f.home_team,f.away_team),"home_win_prob":p,"confidence":np.maximum(p,1-p),"v1_home_win_prob":pv,"margin_home_win_prob":pm,"market_used_for_pick":False,"status":"PREGAME_SHADOW"}).sort_values(["kickoff_utc","game_id"])
 cur=Path(a.current);cur.parent.mkdir(parents=True,exist_ok=True);out.to_csv(cur,index=False);led=Path(a.ledger)
 if led.exists():
  old=pd.read_csv(led);ids=set(old.prediction_id.astype(str));add=out[~out.prediction_id.astype(str).isin(ids)];combined=pd.concat([old,add],ignore_index=True)
 else:combined=out.copy()
 if not led.exists():combined.to_csv(led,index=False)
 # Preserve the legacy first snapshots; the verified record starts after the committed freeze.
 verified=led.parent/'verified_prediction_ledger.csv';locked=out.copy();locked['bundle_sha256']=manifest['sha256'];locked['bundle_frozen_at_utc']=manifest['created_utc']
 locked=locked[pd.to_datetime(locked.snapshot_created_utc,utc=True).ge(pd.Timestamp(manifest['created_utc'])) & pd.to_datetime(locked.snapshot_created_utc,utc=True).lt(pd.to_datetime(locked.kickoff_utc,utc=True))]
 if verified.exists():
  old_verified=pd.read_csv(verified);known=set(old_verified.prediction_id.astype(str));locked=pd.concat([old_verified,locked[~locked.prediction_id.astype(str).isin(known)]],ignore_index=True)
 for column,value in [('actual_winner',None),('correct',None),('settled',False)]:
  if column not in locked:locked[column]=value
 locked.to_csv(verified,index=False)
 Path(a.metadata).write_text(json.dumps({"model_version":"CFB_V2_CANDIDATE_B","status":"PROSPECTIVE_SHADOW_ONLY","generated_at_utc":created,"games":int(len(out)),"ledger_rows":int(len(locked)),"ledger_source":"verified_prediction_ledger.csv","legacy_ledger_preserved":True,"market_used_for_pick":False},indent=2)+"\n");print(f"Candidate B current={len(out)} ledger={len(combined)}")
if __name__=="__main__":main()
