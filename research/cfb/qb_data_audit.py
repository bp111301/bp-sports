"""Diagnose why the historical advanced-passing feed did not map into matchup rows."""
from pathlib import Path
import argparse,json
import pandas as pd
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--matchup-dir",default="runtime/cfb/matchup_line");ap.add_argument("--passing-dir",default="runtime/cfb/adv_passing");ap.add_argument("--out-dir",default="research/cfb/v2_results");a=ap.parse_args()
    mf=sorted(Path(a.matchup_dir).glob("cfb_matchup_line_*.csv"));pf=sorted(Path(a.passing_dir).glob("adv_passing_*.csv"))
    m=pd.concat([pd.read_csv(x,low_memory=False) for x in mf],ignore_index=True);p=pd.concat([pd.read_csv(x,low_memory=False) for x in pf],ignore_index=True)
    home_col="home_team_id" if "home_team_id" in m else "home_id";away_col="away_team_id" if "away_team_id" in m else "away_id"
    mids=set(pd.to_numeric(m.game_id,errors="coerce").dropna().astype("int64"));pids=set(pd.to_numeric(p.game_id,errors="coerce").dropna().astype("int64"))
    mteams=set(pd.concat([pd.to_numeric(m[home_col],errors="coerce"),pd.to_numeric(m[away_col],errors="coerce")]).dropna().astype("int64"))
    pteams=set(pd.to_numeric(p.pos_team,errors="coerce").dropna().astype("int64"))
    joined=m[["game_id","season","week",home_col,away_col,"home_team","away_team"]].merge(p[["game_id","pos_team","passer_player_name","Att"]],on="game_id",how="inner")
    joined["matches_home"]=pd.to_numeric(joined.pos_team,errors="coerce")==pd.to_numeric(joined[home_col],errors="coerce")
    joined["matches_away"]=pd.to_numeric(joined.pos_team,errors="coerce")==pd.to_numeric(joined[away_col],errors="coerce")
    payload={"matchup_team_id_columns":[home_col,away_col],"matchup_games":len(mids),"passing_games":len(pids),"game_id_overlap":len(mids&pids),"matchup_team_ids":len(mteams),"passing_team_ids":len(pteams),"team_id_overlap":len(mteams&pteams),"joined_passer_rows":int(len(joined)),"joined_rows_matching_home_or_away_id":int((joined.matches_home|joined.matches_away).sum()),"sample":joined.head(12).fillna("").to_dict("records")}
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True);(out/"qb_data_mapping_audit.json").write_text(json.dumps(payload,indent=2,default=str)+"\n");print(json.dumps(payload,indent=2,default=str))
if __name__=="__main__":main()
