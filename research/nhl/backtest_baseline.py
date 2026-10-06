"""Leakage-safe NHL V1 baseline using only information available before each game."""
from __future__ import annotations
import argparse,json
from collections import defaultdict,deque
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,brier_score_loss,log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES=["elo_diff","home_field","win10_diff","gd10_diff","gf10_diff","ga10_diff","rest_diff","home_b2b","away_b2b","games_played_diff"]

def load(path):
 fs=sorted(Path(path).glob("nhl_games_*.csv"));d=pd.concat([pd.read_csv(f) for f in fs],ignore_index=True);d["season"]=d.season.astype(str);d["game_date"]=pd.to_datetime(d.game_date);d["home_score"]=pd.to_numeric(d.home_score,errors="coerce");d["away_score"]=pd.to_numeric(d.away_score,errors="coerce");d=d.dropna(subset=["home_score","away_score","home_team","away_team"]).copy();d["home_win"]=(d.home_score>d.away_score).astype(int);return d.sort_values(["season","game_date","game_id"]).reset_index(drop=True)

def build_features(d):
 elo=defaultdict(lambda:1500.0);hist=defaultdict(lambda:deque(maxlen=10));last={};gp=defaultdict(int);rows=[];last_season=None
 for _,r in d.iterrows():
  s=str(r.season)
  if last_season is not None and s!=last_season:
   for t in list(elo):elo[t]=1500+.75*(elo[t]-1500)
   hist=defaultdict(lambda:deque(maxlen=10));last={};gp=defaultdict(int)
  last_season=s;h=str(r.home_team);a=str(r.away_team)
  def av(team,i):return float(np.mean([x[i] for x in hist[team]])) if hist[team] else np.nan
  hr=(r.game_date-last[h]).days if h in last else np.nan;ar=(r.game_date-last[a]).days if a in last else np.nan
  rows.append({"elo_diff":elo[h]-elo[a],"home_field":1.0,"win10_diff":av(h,0)-av(a,0),"gd10_diff":av(h,1)-av(a,1),"gf10_diff":av(h,2)-av(a,2),"ga10_diff":av(h,3)-av(a,3),"rest_diff":hr-ar if pd.notna(hr) and pd.notna(ar) else np.nan,"home_b2b":float(hr==1) if pd.notna(hr) else 0.0,"away_b2b":float(ar==1) if pd.notna(ar) else 0.0,"games_played_diff":gp[h]-gp[a]})
  y=int(r.home_win);margin=float(r.home_score-r.away_score);exp=1/(1+10**(-(elo[h]+35-elo[a])/400));k=20;elo[h]+=k*(y-exp);elo[a]-=k*(y-exp)
  hist[h].append((y,margin,float(r.home_score),float(r.away_score)));hist[a].append((1-y,-margin,float(r.away_score),float(r.home_score)));last[h]=r.game_date;last[a]=r.game_date;gp[h]+=1;gp[a]+=1
 return pd.DataFrame(rows,index=d.index)

def model():
 prep=ColumnTransformer([("num",Pipeline([("imp",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),FEATURES)],remainder="drop")
 return Pipeline([("prep",prep),("model",LogisticRegression(C=.5,max_iter=3000))])

def score(y,p):
 return {"games":int(len(y)),"accuracy":float(accuracy_score(y,p>=.5)),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/nhl/games");ap.add_argument("--out-dir",default="research/nhl/results");ap.add_argument("--first-test","default",default="20212022");a=ap.parse_args()
 d=load(a.data_dir);x=build_features(d);seasons=sorted(d.season.unique());first="20212022";parts=[];rows=[]
 for s in seasons:
  if s<first:continue
  tr=d.index[d.season<s];te=d.index[d.season==s]
  if not len(tr) or not len(te):continue
  m=model();m.fit(x.loc[tr,FEATURES],d.loc[tr,"home_win"]);p=m.predict_proba(x.loc[te,FEATURES])[:,1];y=d.loc[te,"home_win"].to_numpy();z=score(y,p);z["season"]=s;rows.append(z);q=d.loc[te,["game_id","season","game_date","away_team","home_team","home_win"]].copy();q["home_win_prob"]=p;parts.append(q)
 pred=pd.concat(parts,ignore_index=True);overall=score(pred.home_win.to_numpy(),pred.home_win_prob.to_numpy());out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);pred.to_csv(out/"baseline_oof_predictions.csv",index=False);payload={"version":"NHL_V1_RESEARCH_BASELINE","market_used":False,"features":FEATURES,"overall":overall,"by_season":rows};(out/"baseline.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# NHL V1 Baseline","","Chronological season walk-forward. Features are reconstructed strictly before each game; no betting market input.","",f"- Games: {overall['games']:,}",f"- Accuracy: {overall['accuracy']:.2%}",f"- Brier: {overall['brier']:.4f}",f"- Log loss: {overall['log_loss']:.4f}","","| Season | Games | Accuracy | Brier | Log loss |","|---|---:|---:|---:|---:|"]
 for r in rows:lines.append(f"| {r['season']} | {r['games']:,} | {r['accuracy']:.2%} | {r['brier']:.4f} | {r['log_loss']:.4f} |")
 (out/"BASELINE.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
