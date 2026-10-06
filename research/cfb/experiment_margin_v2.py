"""CFB V2 score-margin challenger.

Train Ridge margin models chronologically, convert predicted margin to a win
probability using the training residual distribution, and test whether blending
that independent signal with frozen V1 improves 2018-2025 OOF probability quality.
2026 is excluded.
"""
from __future__ import annotations
import argparse,importlib.util,json,math
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
HERE=Path(__file__).parent
def mod(name,file):
 s=importlib.util.spec_from_file_location(name,HERE/file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("base","backtest_baseline.py");pri=mod("pri","experiment_priors.py")
def margin_model(features,alpha):
 prep=ColumnTransformer([("num",Pipeline([("impute",SimpleImputer(strategy="median",add_indicator=True)),("scale",StandardScaler())]),features)],remainder="drop")
 return Pipeline([("prep",prep),("model",Ridge(alpha=alpha))])
def normcdf(x):
 x=np.asarray(x,float);return .5*(1+np.vectorize(math.erf)(x/np.sqrt(2)))
def matrices(df):
 bx=base.build_matrix(df);cf=base.feature_sets(bx)["cfb_context"];px=pri.matrix(df,7.0);rem={f"{f}_diff" for f in pri.BLEND_BASES}|{f"prev_{f}_diff" for f in pri.BLEND_BASES};pf=[c for c in cf if c not in rem]+[f"blend_{f}_diff" for f in pri.BLEND_BASES];return bx,cf,px,pf
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data-dir",default="runtime/cfb/matchup_line");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
 df=base.load_data(Path(a.data_dir));df=df[df.season<=2025].copy().reset_index(drop=True);df["margin"]=pd.to_numeric(df.home_points)-pd.to_numeric(df.away_points);bx,cf,px,pf=matrices(df)
 store={};specs=[]
 for matrix,features,label in [(bx,cf,"context"),(px,pf,"prior")]:
  for alpha in [1.0,10.0,100.0]:specs.append((matrix,features,label,alpha))
 # frozen V1 and every margin candidate are generated on identical season folds
 v1parts=[];marginparts={f"{label}_a{int(alpha)}":[] for _,_,label,alpha in specs};ys=[];seasons=[]
 for season in range(2018,2026):
  tr=df.index[df.season<season];te=df.index[df.season==season];y=df.loc[te,"home_win"].to_numpy();ys.append(y);seasons.extend([season]*len(te))
  mc=base.model(cf);mp=base.model(pf);mc.fit(bx.loc[tr,cf],df.loc[tr,"home_win"]);mp.fit(px.loc[tr,pf],df.loc[tr,"home_win"]);v1parts.append(.25*mc.predict_proba(bx.loc[te,cf])[:,1]+.75*mp.predict_proba(px.loc[te,pf])[:,1])
  for matrix,features,label,alpha in specs:
   m=margin_model(features,alpha);m.fit(matrix.loc[tr,features],df.loc[tr,"margin"]);fit=m.predict(matrix.loc[tr,features]);sigma=float(np.std(df.loc[tr,"margin"].to_numpy()-fit,ddof=1));pred=m.predict(matrix.loc[te,features]);marginparts[f"{label}_a{int(alpha)}"].append(normcdf(pred/max(sigma,1e-6)))
 v1=np.concatenate(v1parts);y=np.concatenate(ys);season_arr=np.asarray(seasons);candidates={"v1":v1}
 for n,parts in marginparts.items():
  pm=np.concatenate(parts);candidates["margin_"+n]=pm
  for w in [.15,.25,.35,.50]:candidates[f"blend_{n}_w{int(w*100)}"]=(1-w)*v1+w*pm
 result={}
 for n,p in candidates.items():
  overall=base.score(y,p);recent=season_arr>=2023
  by=[]
  for s in range(2018,2026):
   z=season_arr==s;m=base.score(y[z],p[z]);m["season"]=s;by.append(m)
  result[n]={"overall":overall,"recent_2023_2025":base.score(y[recent],p[recent]),"by_season":by}
 b=result["v1"]["overall"]["brier"];br=result["v1"]["recent_2023_2025"]["brier"]
 for n,v in result.items():
  v["delta_brier"]=v["overall"]["brier"]-b;v["recent_delta_brier"]=v["recent_2023_2025"]["brier"]-br;v["seasons_improved"]=sum(a["brier"]<bb["brier"] for a,bb in zip(v["by_season"],result["v1"]["by_season"]))
 ranked=sorted(result,key=lambda n:(result[n]["overall"]["brier"],result[n]["recent_2023_2025"]["brier"]))
 payload={"selection_window":"2018-2025","2026_touched":False,"ranking":ranked,"candidates":result};out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"margin_challenger.json").write_text(json.dumps(payload,indent=2)+"\n")
 lines=["# CFB V2 Margin Challenger","","Ridge score-margin models are trained only on prior seasons. Their predicted margins are converted to win probabilities using training residual variance. 2026 is excluded.","","| Candidate | Accuracy | Brier | Δ Brier | Recent Brier | Recent Δ | Seasons improved |","|---|---:|---:|---:|---:|---:|---:|"]
 for n in ranked[:15]:
  v=result[n];lines.append(f"| {n} | {v['overall']['accuracy']:.2%} | {v['overall']['brier']:.6f} | {v['delta_brier']:+.6f} | {v['recent_2023_2025']['brier']:.6f} | {v['recent_delta_brier']:+.6f} | {v['seasons_improved']}/8 |")
 (out/"MARGIN_CHALLENGER.md").write_text("\n".join(lines)+"\n");print("\n".join(lines))
if __name__=="__main__":main()
