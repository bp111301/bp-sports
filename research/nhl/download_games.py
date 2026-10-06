"""Download regular-season NHL game results from the NHL web API.

Uses team season schedules, deduplicated by game id. Market odds are not fetched.
"""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
import pandas as pd,requests

API="https://api-web.nhle.com/v1"
TEAMS=["ANA","BOS","BUF","CAR","CBJ","CGY","CHI","COL","DAL","DET","EDM","FLA","LAK","MIN","MTL","NJD","NSH","NYI","NYR","OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK","WPG","WSH","ARI"]

def text(v):
 if isinstance(v,dict):return v.get("default") or v.get("fr") or next(iter(v.values()),None)
 return v

def fetch(url):
 r=requests.get(url,timeout=30,headers={"User-Agent":"BP-Sports-Research/1.0"});r.raise_for_status();return r.json()

def main():
 ap=argparse.ArgumentParser();ap.add_argument("seasons",nargs="+");ap.add_argument("--out-dir",default="runtime/nhl/games");a=ap.parse_args();out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
 for season in a.seasons:
  dest=out/f"nhl_games_{season}.csv"
  if dest.exists():continue
  games={}
  for team in TEAMS:
   url=f"{API}/club-schedule-season/{team}/{season}"
   try:data=fetch(url)
   except requests.HTTPError as e:
    if e.response is not None and e.response.status_code in (400,404):continue
    raise
   for g in data.get("games",[]):
    if int(g.get("gameType",0))!=2:continue
    gid=g.get("id")
    if not gid:continue
    away=g.get("awayTeam",{});home=g.get("homeTeam",{});outcome=g.get("gameOutcome") or {}
    games[int(gid)]={"game_id":int(gid),"season":str(season),"game_date":g.get("gameDate"),"start_time_utc":g.get("startTimeUTC"),"game_state":g.get("gameState"),"away_id":away.get("id"),"away_team":away.get("abbrev"),"away_name":text(away.get("commonName")),"away_score":away.get("score"),"home_id":home.get("id"),"home_team":home.get("abbrev"),"home_name":text(home.get("commonName")),"home_score":home.get("score"),"last_period_type":outcome.get("lastPeriodType")}
   time.sleep(.03)
  df=pd.DataFrame(games.values()).sort_values(["game_date","game_id"])
  df.to_csv(dest,index=False);print(season,len(df),dest)
if __name__=="__main__":main()
