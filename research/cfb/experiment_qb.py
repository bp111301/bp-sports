"""Leakage-safe CFB quarterback layer experiment.

QB identity is inferred only from games in earlier weeks. We never use the
matchup-line table's realized season-leader QB fields.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).parent
def loadmod(name,file):
    s=importlib.util.spec_from_file_location(name,ROOT/file); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
base=loadmod("cfb_base","backtest_baseline.py"); priors=loadmod("cfb_priors","experiment_priors.py")

QB_METRICS=["qb_last_epa","qb_last_sr","qb_last_ypa","qb_epa_3","qb_sr_3","qb_ypa_3","qb_continuity","qb_changed","qb_last_att_share","qb_incumbent_epa_3","qb_incumbent_games_3"]

def load_passing(path:Path):
    fs=sorted(path.glob("adv_passing_*.csv"))
    if not fs: raise FileNotFoundError(path)
    p=pd.concat([pd.read_csv(f,low_memory=False) for f in fs],ignore_index=True)
    for c in ["season","week","game_id","pos_team","Att","EPA","EPA_per_Play","SR","YPA"]:
        if c in p: p[c]=pd.to_numeric(p[c],errors="coerce")
    p=p[p["passer_player_name"].notna() & (p["passer_player_name"].astype(str)!="TEAM") & p["pos_team"].notna()].copy()
    return p

def weighted(g,col,w="Att"):
    v=pd.to_numeric(g[col],errors="coerce"); wt=pd.to_numeric(g[w],errors="coerce").fillna(0)
    ok=v.notna()&(wt>0)
    return float(np.average(v[ok],weights=wt[ok])) if ok.any() else np.nan

def build_team_qb_history(p):
    # Primary passer = most attempts for that team in that game.
    p=p.sort_values(["season","pos_team","week","game_id","Att"],ascending=[True,True,True,True,False])
    prim=p.groupby(["season","pos_team","game_id"],as_index=False).first()
    totals=p.groupby(["season","pos_team","game_id"],as_index=False)["Att"].sum().rename(columns={"Att":"team_Att"})
    prim=prim.merge(totals,on=["season","pos_team","game_id"],how="left")
    prim["att_share"]=prim["Att"]/prim["team_Att"].replace(0,np.nan)
    groups={(int(s),int(t)):g.sort_values(["week","game_id"]).reset_index(drop=True) for (s,t),g in prim.groupby(["season","pos_team"])}
    all_groups={(int(s),int(t)):g.sort_values(["week","game_id"]).reset_index(drop=True) for (s,t),g in p.groupby(["season","pos_team"])}
    return groups,all_groups

def snapshot(primary,allpass,season,team,week):
    g=primary.get((int(season),int(team)))
    if g is None: return {k:np.nan for k in QB_METRICS}
    h=g[g.week<week]
    if h.empty: return {k:np.nan for k in QB_METRICS}
    last=h.iloc[-1]; recent=h.tail(3)
    names=list(h["passer_player_name"].astype(str)); incumbent=names[-1]
    continuity=0
    for n in reversed(names):
        if n==incumbent: continuity+=1
        else: break
    changed=float(len(names)>=2 and names[-1]!=names[-2])
    ap=allpass.get((int(season),int(team)))
    inc=ap[(ap.week<week)&(ap.passer_player_name.astype(str)==incumbent)].tail(3) if ap is not None else pd.DataFrame()
    return {
        "qb_last_epa":float(last.EPA_per_Play) if pd.notna(last.EPA_per_Play) else np.nan,
        "qb_last_sr":float(last.SR) if pd.notna(last.SR) else np.nan,
        "qb_last_ypa":float(last.YPA) if pd.notna(last.YPA) else np.nan,
        "qb_epa_3":weighted(recent,"EPA_per_Play"),
        "qb_sr_3":weighted(recent,"SR"),
        "qb_ypa_3":weighted(recent,"YPA"),
        "qb_continuity":float(continuity),
        "qb_changed":changed,
        "qb_last_att_share":float(last.att_share) if pd.notna(last.att_share) else np.nan,
        "qb_incumbent_epa_3":weighted(inc,"EPA_per_Play") if len(inc) else np.nan,
        "qb_incumbent_games_3":float(inc.game_id.nunique()) if len(inc) else 0.0,
    }

def add_qb(df,x,p):
    primary,allpass=build_team_qb_history(p)
    home=[]; away=[]
    for r in df[["season","week","home_team_id","away_team_id"]].itertuples(index=False):
        home.append(snapshot(primary,allpass,r.season,r.home_team_id,r.week))
        away.append(snapshot(primary,allpass,r.season,r.away_team_id,r.week))
    h=pd.DataFrame(home,index=df.index); a=pd.DataFrame(away,index=df.index)
    for c in QB_METRICS: x[f"{c}_diff"]=h[c]-a[c]
    x["home_qb_changed"]=h["qb_changed"]; x["away_qb_changed"]=a["qb_changed"]
    return x

def eval_model(df,x,features):
    rows=[]; ps=[]; ys=[]
    for season in range(2018,2026):
        tr=df.index[df.season<season]; te=df.index[df.season==season]
        m=base.model(features); m.fit(x.loc[tr,features],df.loc[tr,"home_win"])
        p=m.predict_proba(x.loc[te,features])[:,1]; y=df.loc[te,"home_win"].to_numpy()
        z=base.score(y,p); z["season"]=season; rows.append(z); ps.append(p); ys.append(y)
    return base.score(np.concatenate(ys),np.concatenate(ps)),pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-dir",default="runtime/cfb/matchup_line"); ap.add_argument("--passing-dir",default="runtime/cfb/adv_passing"); ap.add_argument("--out-dir",default="research/cfb/results"); a=ap.parse_args()
    df=base.load_data(Path(a.data_dir)); df=df[df.season<=2025].copy().reset_index(drop=True); p=load_passing(Path(a.passing_dir))
    raw=base.build_matrix(df); context=base.feature_sets(raw)["cfb_context"]
    blend=priors.matrix(df,3.0); blend_features=[c for c in context if c not in ({f"{f}_diff" for f in priors.BLEND_BASES}|{f"prev_{f}_diff" for f in priors.BLEND_BASES})]+[f"blend_{f}_diff" for f in priors.BLEND_BASES]
    raw=add_qb(df,raw,p); blend=add_qb(df,blend,p); qb=[c for c in raw if c.startswith("qb_") or c in ("home_qb_changed","away_qb_changed")]
    specs={"context_raw":(raw,context),"context_qb":(raw,context+qb),"blend_k3":(blend,blend_features),"blend_k3_qb":(blend,blend_features+qb)}
    coverage={col:float(raw[col].notna().mean()) for col in qb}\n    result={"selection_window":"2018-2025","qb_rule":"prior-week games only; primary passer=max attempts","2026_touched":False,"qb_feature_coverage":coverage,"candidates":{}}; frames=[]
    for n,(x,f) in specs.items():
        overall,seasons=eval_model(df,x,f); result["candidates"][n]={"overall":overall,"n_features":len(f)}; seasons["candidate"]=n; frames.append(seasons)
    ranked=sorted(result["candidates"],key=lambda n:(result["candidates"][n]["overall"]["brier"],result["candidates"][n]["overall"]["log_loss"])); result["ranking"]=ranked; result["leader"]=ranked[0]
    out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True); pd.concat(frames).to_csv(out/"qb_layer_by_season.csv",index=False); (out/"qb_layer_experiment.json").write_text(json.dumps(result,indent=2)+"\n")
    lines=["# CFB V1 QB Layer Experiment","","QB information comes only from games in earlier weeks; realized season-leader QB fields are never used.","","| Candidate | Accuracy | Brier | Log loss |","|---|---:|---:|---:|"]
    for n in ranked:
        m=result["candidates"][n]["overall"]; lines.append(f"| {n} | {m['accuracy']:.2%} | {m['brier']:.4f} | {m['log_loss']:.4f} |")
    lines+=["",f"Leader by Brier: **{ranked[0]}**.","","2026 remains untouched."]
    (out/"QB_LAYER_REPORT.md").write_text("\n".join(lines)+"\n"); print("\n".join(lines))
if __name__=="__main__": main()
