"""Corrected leakage-safe CFB QB-room experiment for V2.

The current adv_passing release stores pos_team as a display-name string despite
older schema docs describing an integer ID. We map each passer row to the
matchup side by game_id + team-name prefix, then use ONLY games from earlier
weeks. No realized current-game QB identity enters a prediction.
"""
from __future__ import annotations
import argparse,importlib.util,json,re
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py")
QB=["qb_last_epa","qb_last_sr","qb_last_ypa","qb_epa_3","qb_sr_3","qb_ypa_3","qb_continuity","qb_last_att_share","qb_incumbent_epa_3","qb_incumbent_games_3"]
def norm(x):return re.sub(r"[^a-z0-9]","",str(x).lower())
def load_passing(path):
 fs=sorted(Path(path).glob("adv_passing_*.csv"));p=pd.concat([pd.read_csv(f,low_memory=False) for f in fs],ignore_index=True)
 for c in ["season","week","game_id","Att","EPA_per_Play","SR","YPA"]:p[c]=pd.to_numeric(p[c],errors="coerce")
 return p[p.passer_player_name.notna()&(p.passer_player_name.astype(str)!="TEAM")].copy()
def map_team_ids(p,df):
 hc="home_team_id" if "home_team_id" in df else "home_id";ac="away_team_id" if "away_team_id" in df else "away_id"
 games=df[["game_id",hc,ac,"home_team","away_team"]].drop_duplicates("game_id")
 z=p.merge(games,on="game_id",how="inner");pt=z.pos_team.map(norm);hn=z.home_team.map(norm);an=z.away_team.map(norm)
 hm=np.array([a.startswith(b) or b.startswith(a) for a,b in zip(pt,hn)]);am=np.array([a.startswith(b) or b.startswith(a) for a,b in zip(pt,an)])
 z["team_id"]=np.where(hm,pd.to_numeric(z[hc],errors="coerce"),np.where(am,pd.to_numeric(z[ac],errors="coerce"),np.nan))
 return z[z.team_id.notna()].copy(),{"passer_rows":int(len(z)),"mapped_rows":int(z.team_id.notna().sum()),"coverage":float(z.team_id.notna().mean())}
def weighted(g,col):
 v=pd.to_numeric(g[col],errors="coerce");w=pd.to_numeric(g.Att,errors="coerce").fillna(0);ok=v.notna()&(w>0)
 return float(np.average(v[ok],weights=w[ok])) if ok.any() else np.nan
def histories(p):
 p=p.sort_values(["season","team_id","week","game_id","Att"],ascending=[1,1,1,1,0]);prim=p.groupby(["season","team_id","game_id"],as_index=False).first()
 totals=p.groupby(["season","team_id","game_id"],as_index=False).Att.sum().rename(columns={"Att":"team_Att"});prim=prim.merge(totals,on=["season","team_id","game_id"]);prim["att_share"]=prim.Att/prim.team_Att.replace(0,np.nan)
 return {(int(s),int(t)):g.sort_values(["week","game_id"]).reset_index(drop=True) for (s,t),g in prim.groupby(["season","team_id"])},{(int(s),int(t)):g.sort_values(["week","game_id"]).reset_index(drop=True) for (s,t),g in p.groupby(["season","team_id"])}
def snap(pg,ag,season,team,week):
 h=pg.get((int(season),int(team)))
 if h is None:return {k:np.nan for k in QB}
 h=h[h.week<week]
 if h.empty:return {k:np.nan for k in QB}
 last=h.iloc[-1];recent=h.tail(3);inc=str(last.passer_player_name);names=h.passer_player_name.astype(str).tolist();cont=0
 for n in reversed(names):
  if n==inc:cont+=1
  else:break
 ap=ag.get((int(season),int(team)));ig=ap[(ap.week<week)&(ap.passer_player_name.astype(str)==inc)].tail(3) if ap is not None else pd.DataFrame()
 return {"qb_last_epa":float(last.EPA_per_Play),"qb_last_sr":float(last.SR),"qb_last_ypa":float(last.YPA),"qb_epa_3":weighted(recent,"EPA_per_Play"),"qb_sr_3":weighted(recent,"SR"),"qb_ypa_3":weighted(recent,"YPA"),"qb_continuity":float(cont),"qb_last_att_share":float(last.att_share),"qb_incumbent_epa_3":weighted(ig,"EPA_per_Play") if len(ig) else np.nan,"qb_incumbent_games_3":float(ig.game_id.nunique()) if len(ig) else 0.0}
def add_qb(df,x,p):
 pg,ag=histories(p);hc="home_team_id" if "home_team_id" in df else "home_id";ac="away_team_id" if "away_team_id" in df else "away_id";hs=[];aws=[]
 for r in df[["season","week",hc,ac]].itertuples(index=False,name=None):
  s,w,h,a=r;hs.append(snap(pg,ag,s,h,w));aws.append(snap(pg,ag,s,a,w))
 h=pd.DataFrame(hs,index=df.index);a=pd.DataFrame(aws,index=df.index)
 for c in QB:x[c+"_diff"]=h[c]-a[c]
 return x
def matrices(df):
 bx=base.build_matrix(df);cf=base.feature_sets(bx)["cfb_context"];px=pri.matrix(df,7.0);rem={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES};pf=[c for c in cf if c not in rem]+[f"blend_{f}_diff" for f in pri.BLEND_BASES];return bx,cf,px,pf
def evaluate(df,p):
 bx,cf,px,pf=matrices(df);bx=add_qb(df,bx,p);px=add_qb(df,px,p);qf=[c+"_diff" for c in QB];store={n:[] for n in ["v1","v1_qb"]}
 for season in range(2018,2026):
  tr=df.index[df.season<season];te=df.index[df.season==season];y=df.loc[te,"home_win"].to_numpy()
  for name,useqb in [("v1",False),("v1_qb",True)]:
   cfeat=cf+(qf if useqb else []);pfeat=pf+(qf if useqb else [])
   mc=base.model(cfeat);mp=base.model(pfeat);mc.fit(bx.loc[tr,cfeat],df.loc[tr,"home_win"]);mp.fit(px.loc[tr,pfeat],df.loc[tr,"home_win"])
   prob=.25*mc.predict_proba(bx.loc[te,cfeat])[:,1]+.75*mp.predict_proba(px.loc[te,pfeat])[:,1];m=base.score(y,prob);m["season"]=season;store[name].append((prob,y,m))
 out={}
 for n,v in store.items():
  pp=np.concatenate([x[0] for x in v]);yy=np.concatenate([x[1] for x in v]);out[n]={"overall":base.score(yy,pp),"by_season":[x[2] for x in v],"recent_2023_2025":base.score(np.concatenate([x[1] for x in v[-3:]]),np.concatenate([x[0] for x in v[-3:]]))}
 return out,{c:float(bx[c+"_diff"].notna().mean()) for c in QB}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--passing-dir",default="runtime/cfb/adv_passing");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);raw=load_passing(a.passing_dir);p,mapstats=map_team_ids(raw,df);res,cov=evaluate(df,p)
 b=res["v1"]["overall"];q=res["v1_qb"]["overall"];payload={"selection_window":"2018-2025","2026_touched":False,"mapping":mapstats,"feature_coverage":cov,"candidates":res,"delta":{"accuracy":q["accuracy"]-b["accuracy"],"brier":q["brier"]-b["brier"],"log_loss":q["log_loss"]-b["log_loss"]}}
 out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"qb_v2_experiment.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Corrected QB-Room Experiment","",f"Mapped {mapstats['mapped_rows']:,}/{mapstats['passer_rows']:,} passer rows ({mapstats['coverage']:.2%}) using game + team-name identity. Only earlier-week games feed QB features; 2026 is excluded.","","| Candidate | Accuracy | Brier | Log loss | Recent accuracy | Recent Brier |","|---|---:|---:|---:|---:|---:|"]
 for n in ["v1","v1_qb"]:
  x=res[n]["overall"];r=res[n]["recent_2023_2025"];lines.append(f"| {n} | {x['accuracy']:.2%} | {x['brier']:.4f} | {x['log_loss']:.4f} | {r['accuracy']:.2%} | {r['brier']:.4f} |")
 lines+=["",f"QB delta: accuracy {payload['delta']['accuracy']:+.3%}, Brier {payload['delta']['brier']:+.6f}, log loss {payload['delta']['log_loss']:+.6f}.","", "This is a V2 research result only. Frozen CFB V1 is unchanged."]
 (out/"QB_V2_REPORT.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
