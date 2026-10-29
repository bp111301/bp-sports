import importlib.util,json,copy
from pathlib import Path
import pandas as pd
import pytest
s=importlib.util.spec_from_file_location('official_counts',Path(__file__).with_name('nhl_game_counts.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def fixture():return json.loads(next((Path(__file__).parent/'fixtures').glob('nhl_*.json')).read_text())
def test_five_actual_official_games_match_primary_stat_inputs():
 files=list((Path(__file__).parent/'fixtures').glob('nhl_*.json'));assert len(files)==5
 for p in files:
  f=json.loads(p.read_text());assert m.parity(pd.DataFrame(f['primary']),m.completed_rows(f['landing'],f['rail']))
def test_shootout_award_removed_only_from_winner_raw_goals():
 f=fixture();l=f['landing'];l['periodDescriptor']['periodType']='SO';l['homeTeam']['score']=3;l['awayTeam']['score']=2
 r=m.completed_rows(l,f['rail']);h=r[r.homeRoad.eq('H')].iloc[0];a=r[r.homeRoad.eq('R')].iloc[0]
 assert h.goalsFor==a.goalsFor==2 and h.winsInShootout==1 and a.winsInShootout==0
 l['homeTeam']['score']=4
 with pytest.raises(ValueError,match='shootout'):m.completed_rows(l,f['rail'])
def test_incomplete_or_conflicting_game_counts_rejected():
 f=fixture();l=copy.deepcopy(f['landing']);l['gameState']='LIVE'
 with pytest.raises(ValueError,match='final'):m.completed_rows(l,f['rail'])
 l=copy.deepcopy(f['landing']);l['homeTeam']['sog']+=1
 with pytest.raises(ValueError,match='shot'):m.completed_rows(l,f['rail'])
 p=pd.DataFrame(f['primary']);p.loc[0,'goalsFor']+=1
 with pytest.raises(ValueError,match='disagree'):m.parity(p,m.completed_rows(f['landing'],f['rail']))
