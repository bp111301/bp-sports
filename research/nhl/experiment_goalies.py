"""Leakage-safe NHL goalie layer.

The historical model never receives the realized starter before prediction.
It infers a likely starter from prior team starts, then uses only that goalie's
prior appearances, workload and rest. Actual starter data updates state only
after each game.
"""
from __future__ import annotations
import importlib.util,json
from collections import Counter,defaultdict,deque
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,brier_score_loss,log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

HERE=Path(__file__).parent
def loadmod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=loadmod("base","backtest_baseline.py");adv=loadmod("adv","experiment_team_stats.py")
DEV=["20212022","20222023","20232024","20242025"]

def load_goalies(root="runtime/nhl/goalie_game_stats"):
 parts=[]
 for f in sorted(Path(root).glob("goalie_summary_*.csv")):
  z=pd.read_csv(f);z["season"]=f.stem.split("_")[-1];z["gameDate"]=pd.to_datetime(z.gameDate);parts.append(z)
 return pd.concat(parts,ignore_index=True)

def goalie_features(d,g):
 bygame={(int(k[0]),str(k[1])):v.copy() for k,v in g.groupby(["gameId","teamAbbrev"])}
 team_starts=defaultdict(lambda:deque(maxlen=10));apps=defaultdict(lambda:deque(maxlen=20));last={};season_seen=None;rows=[]
 def probable(team):
  h=team_starts[team]
  if not h:return None
  counts=Counter(h);best=max(counts.values())
  for pid in reversed(h):
   if counts[pid]==best:return pid
 def info(team,date):
  pid=probable(team)
  if pid is None:return (np.nan,np.nan,np.nan,0.0)
  a=list(apps[(team,pid)])
  sv10=float(np.mean([x[1] for x in a[-10:] if pd.notna(x[1])])) if any(pd.notna(x[1]) for x in a[-10:]) else np.nan
  sv20=float(np.mean([x[1] for x in a if pd.notna(x[1])])) if any(pd.notna(x[1]) for x in a) else np.nan
  rest=float((date-last[(team,pid)]).days) if (team,pid) in last else np.nan
  share=float(sum(x==pid for x in team_starts[team])/len(team_starts[team])) if team_starts[team] else 0.0
  return sv10,sv20,rest,share
 for _,r in d.sort_values(["season","game_date","game_id"]).iterrows():
  s=str(r.season)
  if season_seen is not None and s!=season_seen:
   team_starts=defaultdict(lambda:deque(maxlen=10));apps=defaultdict(lambda:deque(maxlen=20));last={}
  season_seen=s;date=r.game_date;h=str(r.home_team);a=str(r.away_team)
  hi=info(h,date);ai=info(a,date)
  rows.append({"game_id":int(r.game_id),"goalie_sv10_diff":hi[0]-ai[0],"goalie_sv20_diff":hi[1]-ai[1],"goalie_rest_diff":hi[2]-ai[2] if pd.notna(hi[2]) and pd.notna(ai[2]) else np.nan,"goalie_start_share_diff":hi[3]-ai[3]})
  for team in [h,a]:
   z=bygame.get((int(r.game_id),team))
   if z is None or z.empty:continue
   for _,q in z.iterrows():
    pid=int(q.playerId);sv=pd.to_numeric(q.savePct,errors="coerce");started=float(pd.to_numeric(q.gamesStarted,errors="coerce") or 0)>0
    apps[(team,pid)].append((date,sv));last[(team,pid)]=date
    if started:team_starts[team].append(pid)
 return pd.DataFrame(rows).set_index(d.sort_values(["season","game_date","game_id"]).index).sort_index()

def model(features):
 prep=ColumnTransformer([("num",Pipeline([("imp",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),features)],remainder="drop")
 return Pipeline([("prep",prep),("model",LogisticRegression(C=.5,max_iter=3000))])
def met(y,p):return {"games":int(len(y)),"accuracy":float(accuracy_score(y,p>=.5)),"brier":float(brier_score_loss(y,p)),"log_loss":float(log_loss(y,p,labels=[0,1]))}
def eval_model(d,x,features):
 ys=[];ps=[];by=[]
 for s in DEV:
  tr=d.index[d.season<s];te=d.index[d.season==s];m=model(features);m.fit(x.loc[tr,features],d.loc[tr,"home_win"]);p=m.predict_proba(x.loc[te,features])[:,1];y=d.loc[te,"home_win"].to_numpy();ys.extend(y);ps.extend(p);q=met(y,p);q["season"]=s;by.append(q)
 z=met(np.asarray(ys),np.asarray(ps));z["by_season"]=by;return z
def main():
 d=base.load("runtime/nhl/games");bx=base.build_features(d);team=adv.load_team_stats();ax,af=adv.attach(d,bx,team,20);g=load_goalies();gx=goalie_features(d,g)
 for c in gx.columns:ax[c]=gx[c]
 leader=base.FEATURES+af;gf=list(gx.columns);results=[]
 for name,features in [("advanced_all_w20",leader),("advanced_plus_goalie",leader+gf),("baseline_plus_goalie",base.FEATURES+gf)]:
  results.append({"candidate":name,"features":features,**eval_model(d,ax,features)})
 results=sorted(results,key=lambda r:(r["brier"],r["log_loss"],-r["accuracy"]))
 out=Path("research/nhl/results");(out/"goalie_tournament.json").write_text(json.dumps({"selection_seasons":DEV,"excluded_from_selection":["20252026"],"starter_rule":"inferred from prior 10 team starts only","ranking":results},indent=2)+"\n")
 lines=["# NHL Goalie Tournament","","Historical starter is never exposed before prediction. Likely starter is inferred from the prior 10 team starts only. 2025-26 remains excluded from selection.","","| Rank | Candidate | Accuracy | Brier | Log loss |","|---:|---|---:|---:|---:|"]
 for i,r in enumerate(results,1):lines.append(f"| {i} | {r['candidate']} | {r['accuracy']:.2%} | {r['brier']:.4f} | {r['log_loss']:.4f} |")
 (out/"GOALIE_TOURNAMENT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
