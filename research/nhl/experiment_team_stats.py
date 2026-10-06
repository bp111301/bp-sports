"""Test leakage-safe rolling NHL team-stat features against the V1 baseline.

All rolling team statistics are shifted one game before calculation. Candidate
selection uses 2021-22 through 2024-25 only; 2025-26 remains untouched.
"""
from __future__ import annotations
import importlib.util,json
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,brier_score_loss,log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("base",HERE/"backtest_baseline.py");base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
DEV=["20212022","20222023","20232024","20242025"]
BASE=base.FEATURES

def load_team_stats(root="runtime/nhl/team_game_stats"):
 parts=[]
 for f in sorted(Path(root).glob("summary_*.csv")):
  season=f.stem.split("_")[-1];s=pd.read_csv(f)
  pp=pd.read_csv(Path(root)/f"powerplay_{season}.csv")
  pk=pd.read_csv(Path(root)/f"penaltykill_{season}.csv")
  keep_pp=[c for c in ["gameId","teamId","powerPlayGoalsFor","ppOpportunities"] if c in pp]
  keep_pk=[c for c in ["gameId","teamId","ppGoalsAgainst","timesShorthanded"] if c in pk]
  t=s.merge(pp[keep_pp],on=["gameId","teamId"],how="left").merge(pk[keep_pk],on=["gameId","teamId"],how="left")
  t["season"]=season;t["gameDate"]=pd.to_datetime(t.gameDate)
  t["shots_for"]=pd.to_numeric(t.shotsForPerGame,errors="coerce")
  t["shots_against"]=pd.to_numeric(t.shotsAgainstPerGame,errors="coerce")
  t["goals_for"]=pd.to_numeric(t.goalsFor,errors="coerce")
  t["goals_against"]=pd.to_numeric(t.goalsAgainst,errors="coerce")
  t["shot_diff"]=t.shots_for-t.shots_against
  t["shoot_pct"]=np.where(t.shots_for>0,t.goals_for/t.shots_for,np.nan)
  t["save_pct"]=np.where(t.shots_against>0,1-t.goals_against/t.shots_against,np.nan)
  t["faceoff_pct"]=pd.to_numeric(t.faceoffWinPct,errors="coerce")
  t["pp_rate"]=np.where(pd.to_numeric(t.ppOpportunities,errors="coerce")>0,pd.to_numeric(t.powerPlayGoalsFor,errors="coerce")/pd.to_numeric(t.ppOpportunities,errors="coerce"),np.nan)
  t["pk_rate"]=np.where(pd.to_numeric(t.timesShorthanded,errors="coerce")>0,1-pd.to_numeric(t.ppGoalsAgainst,errors="coerce")/pd.to_numeric(t.timesShorthanded,errors="coerce"),np.nan)
  parts.append(t)
 return pd.concat(parts,ignore_index=True)

RAW=["shots_for","shots_against","shot_diff","shoot_pct","save_pct","faceoff_pct","pp_rate","pk_rate"]

def rolling_table(t,window):
 t=t.sort_values(["season","teamId","gameDate","gameId"]).copy()
 for c in RAW:
  t[f"{c}_{window}"]=t.groupby(["season","teamId"],sort=False)[c].transform(lambda x:x.shift(1).rolling(window,min_periods=3).mean())
 return t[["gameId","teamId"]+[f"{c}_{window}" for c in RAW]]

def attach(d,x,t,window):
 roll=rolling_table(t,window);cols=[f"{c}_{window}" for c in RAW]
 h=roll.rename(columns={"gameId":"game_id","teamId":"home_id",**{c:f"home_{c}" for c in cols}})
 a=roll.rename(columns={"gameId":"game_id","teamId":"away_id",**{c:f"away_{c}" for c in cols}})
 z=d[["game_id","home_id","away_id"]].merge(h,on=["game_id","home_id"],how="left").merge(a,on=["game_id","away_id"],how="left")
 out=x.copy()
 adv=[]
 for c in cols:
  name=f"{c}_diff";out[name]=pd.to_numeric(z[f"home_{c}"],errors="coerce")-pd.to_numeric(z[f"away_{c}"],errors="coerce");adv.append(name)
 return out,adv

def model(features):
 prep=ColumnTransformer([("num",Pipeline([("imp",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),features)],remainder="drop")
 return Pipeline([("prep",prep),("model",LogisticRegression(C=.5,max_iter=3000))])

def metrics(y,p):
 return {"games":int(len(y)),"accuracy":float(accuracy_score(y,p>=.5)),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}

def evaluate(d,x,features):
 ys=[];ps=[];by=[]
 for s in DEV:
  tr=d.index[d.season<s];te=d.index[d.season==s];m=model(features);m.fit(x.loc[tr,features],d.loc[tr,"home_win"]);p=m.predict_proba(x.loc[te,features])[:,1];y=d.loc[te,"home_win"].to_numpy();ys.extend(y);ps.extend(p);q=metrics(y,p);q["season"]=s;by.append(q)
 z=metrics(np.asarray(ys),np.asarray(ps));z["by_season"]=by;return z

def main():
 d=base.load("runtime/nhl/games");bx=base.build_features(d);t=load_team_stats();results=[]
 b=evaluate(d,bx,BASE);results.append({"candidate":"baseline","features":BASE,**b})
 for w in [5,10,20]:
  ax,adv=attach(d,bx,t,w)
  for subset in ["possession","percentages","all"]:
   if subset=="possession":use=[x for x in adv if any(k in x for k in ["shots_for","shots_against","shot_diff","faceoff"])]
   elif subset=="percentages":use=[x for x in adv if any(k in x for k in ["shoot_pct","save_pct","pp_rate","pk_rate"])]
   else:use=adv
   z=evaluate(d,ax,BASE+use);results.append({"candidate":f"advanced_{subset}_w{w}","features":BASE+use,**z})
 results=sorted(results,key=lambda r:(r["brier"],r["log_loss"],-r["accuracy"]))
 out=Path("research/nhl/results");(out/"advanced_team_stats.json").write_text(json.dumps({"selection_seasons":DEV,"excluded_from_selection":["20252026"],"ranking":results},indent=2)+"\n")
 lines=["# NHL Advanced Team-Stats Tournament","","Every rolling statistic is shifted one game. 2025-26 is excluded from selection.","","| Rank | Candidate | Accuracy | Brier | Log loss |","|---:|---|---:|---:|---:|"]
 for i,r in enumerate(results,1):lines.append(f"| {i} | {r['candidate']} | {r['accuracy']:.2%} | {r['brier']:.4f} | {r['log_loss']:.4f} |")
 (out/"ADVANCED_TEAM_STATS.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
