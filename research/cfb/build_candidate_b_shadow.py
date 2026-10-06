"""Build frozen CFB V2 Candidate B shadow predictions.

Candidate B never changes the public V1 feed. It blends 65% frozen V1 winner
probability with 35% leakage-safe context score-margin probability and writes
an independent immutable prospective ledger.
"""
from __future__ import annotations
import argparse,importlib.util,json,math
from datetime import datetime,timezone
from pathlib import Path
import joblib,numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py")
def margin_model(features):
 prep=ColumnTransformer([("num",Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),features)],remainder="drop")
 return Pipeline([("prep",prep),("model",Ridge(alpha=100.0))])
def normcdf(x):return .5*(1+np.vectorize(math.erf)(np.asarray(x,float)/np.sqrt(2)))
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--schedule",default="runtime/cfb/schedules/cfb_schedules_2026.csv.gz");ap.add_argument("--bundle",default="model/cfb/v1/frozen_bundle.joblib");ap.add_argument("--current-dir",default="data/cfb/shadow");ap.add_argument("--ledger",default="data/cfb/shadow/candidate_b_ledger.csv");ap.add_argument("--horizon-days",type=int,default=8);a=ap.parse_args()
 bundle=joblib.load(a.bundle)
 if bundle.get("version")!="CFB_V1":raise RuntimeError("Frozen V1 bundle required")
 hist=base.load_data(Path(a.data_dir));train=hist[hist.season<=2025].copy().reset_index(drop=True);tx=base.build_matrix(train);cf=list(bundle["context_features"]);train["margin"]=train.home_points-train.away_points
 mm=margin_model(cf);mm.fit(tx[cf],train.margin);fit=mm.predict(tx[cf]);sigma=float(np.std(train.margin.to_numpy()-fit,ddof=1))
 raw=pd.read_csv(Path(a.data_dir)/"cfb_matchup_line_2026.csv",low_memory=False);raw["season"]=pd.to_numeric(raw.season,errors="coerce");raw["week"]=pd.to_numeric(raw.week,errors="coerce");raw["game_id"]=pd.to_numeric(raw.game_id,errors="coerce")
 sch=pd.read_csv(a.schedule,low_memory=False);sch["game_id"]=pd.to_numeric(sch.game_id,errors="coerce");sch["kickoff"]=pd.to_datetime(sch.start_date,errors="coerce",utc=True);sch=sch[["game_id","kickoff","start_time_tbd"]].drop_duplicates("game_id");raw=raw.merge(sch,on="game_id",how="left")
 now=pd.Timestamp.now(tz="UTC");future=raw[(raw.season==2026)&raw.kickoff.notna()&(raw.kickoff>now)&(raw.kickoff<=now+pd.Timedelta(days=a.horizon_days))].copy().reset_index(drop=True)
 if future.empty:raise SystemExit("No future games in Candidate B horizon")
 fx=base.build_matrix(future);fpx=pri.matrix(future,float(bundle["prior_k"]));pf=list(bundle["prior_features"]);mc=bundle["context_model"];mp=bundle["prior_model"];pv=float(bundle["context_weight"])*mc.predict_proba(fx[cf])[:,1]+float(bundle["prior_weight"])*mp.predict_proba(fpx[pf])[:,1]
 pm=normcdf(mm.predict(fx[cf])/max(sigma,1e-6));pb=.65*pv+.35*pm;generated=datetime.now(timezone.utc).isoformat()
 out=pd.DataFrame({"prediction_id":["CFBV2B_2026_"+str(x) for x in future.game_id],"model_version":"CFB_V2_CANDIDATE_B","snapshot_created_utc":generated,"game_id":future.game_id,"season":2026,"week":future.week.astype("Int64"),"kickoff_utc":future.kickoff.astype(str),"kickoff_time_tbd":future.start_time_tbd,"away_team":future.away_team,"home_team":future.home_team,"predicted_winner":np.where(pb>=.5,future.home_team,future.away_team),"home_win_prob":pb,"confidence":np.maximum(pb,1-pb),"v1_home_win_prob":pv,"v1_predicted_winner":np.where(pv>=.5,future.home_team,future.away_team),"margin_home_win_prob":pm,"disagrees_with_v1":(pb>=.5)!=(pv>=.5),"market_used_for_pick":False,"status":"PREGAME_SNAPSHOT"}).sort_values(["kickoff_utc","game_id"])
 cur=Path(a.current_dir);cur.mkdir(parents=True,exist_ok=True);out.to_csv(cur/"candidate_b_predictions.csv",index=False);(cur/"candidate_b_metadata.json").write_text(json.dumps({"model_version":"CFB_V2_CANDIDATE_B","generated_at_utc":generated,"games":int(len(out)),"horizon_days":a.horizon_days,"market_used_for_pick":False,"prospective_shadow":True},indent=2)+"\n")
 led=Path(a.ledger);led.parent.mkdir(parents=True,exist_ok=True)
 if led.exists():
  old=pd.read_csv(led);existing=set(old.prediction_id.astype(str));add=out[~out.prediction_id.astype(str).isin(existing)];combined=pd.concat([old,add],ignore_index=True)
 else:combined=out.copy()
 combined.to_csv(led,index=False);print(json.dumps({"current_games":len(out),"ledger_rows":len(combined),"v1_disagreements":int(out.disagrees_with_v1.sum())},indent=2))
if __name__=="__main__":main()
