"""MoneyPuck listed public team-game download for noncommercial research.

Historical xG model vintage is unverified; inputs are exploratory only.
"""
import json
from pathlib import Path
import pandas as pd
import requests
URL='https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv'
def main():
    root=Path('runtime/nhl');root.mkdir(parents=True,exist_ok=True)
    status={'available':False,'source':'MoneyPuck.com','url':URL,'historical_model_vintage_verified':False}
    try:
        r=requests.get(URL,timeout=120);r.raise_for_status()
        from io import StringIO
        q=pd.read_csv(StringIO(r.text),usecols=['season','gameId','gameDate','team','situation','xGoalsFor','xGoalsAgainst'])
        q=q[(q.season>=2018)&(q.season<=2024)&(q.situation=='all')].copy()
        # NHL regular season game IDs use game type 02.
        q=q[q.gameId.astype(str).str[4:6]=='02']
        if len(q)==0:raise ValueError('No development regular-season team-game rows')
        q.to_csv(root/'moneypuck_team_games.csv',index=False)
        status.update(available=True,rows=len(q))
    except Exception as e:
        status['reason']=f'{type(e).__name__}: {e}'
    (root/'quality_status.json').write_text(json.dumps(status,indent=2)+'\n');print(status)
if __name__=='__main__':main()
