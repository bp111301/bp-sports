"""Equivalent official game-center count adapter for delayed team-stat reports."""
import numpy as np
import pandas as pd

def pair(value):
 a,b=str(value).split('/');a=int(a);b=int(b)
 if a<0 or b<0 or a>b:raise ValueError('Invalid official opportunity counts')
 return a,b

def completed_rows(landing,rail):
 if landing['gameState'] not in ['FINAL','OFF'] or int(landing['gameType'])!=2 or landing.get('gameScheduleState','OK')!='OK':raise ValueError('Official NHL final required for fallback')
 stats={v['category']:v for v in rail['teamGameStats']}
 if len(stats)!=len(rail['teamGameStats']):raise ValueError('Duplicate official game stat category')
 h=landing['homeTeam'];a=landing['awayTeam'];hs=int(h['score']);aws=int(a['score'])
 if hs==aws or min(hs,aws)<0:raise ValueError('Invalid official normalized final score')
 period=landing['periodDescriptor']['periodType']
 if period not in ['REG','OT','SO']:raise ValueError('Unknown final period type')
 if period=='SO' and abs(hs-aws)!=1:raise ValueError('Invalid shootout score normalization')
 gf={'home':hs-int(period=='SO' and hs>aws),'away':aws-int(period=='SO' and aws>hs)}
 opportunities={side:pair(stats['powerPlay'][side+'Value']) for side in ['home','away']}
 result=[]
 for side,other,team,opponent,winner in [('home','away',h,a,hs>aws),('away','home',a,h,aws>hs)]:
  sf=int(stats['sog'][side+'Value']);sa=int(stats['sog'][other+'Value'])
  if sf!=int(team['sog']) or sa!=int(opponent['sog']) or sf<gf[side] or sa<gf[other]:raise ValueError('Official shot totals disagree')
  fw,ft=pair(stats['faceoffWins'][side+'Value']);faceoff=float(stats['faceoffWinningPctg'][side+'Value'])
  if ft<=0 or not 0<=faceoff<=1 or abs(faceoff-fw/ft)>1e-6+1e-12:raise ValueError('Invalid official faceoff counts')
  # The stats REST schema truncates this fraction to six decimal places.
  faceoff=(fw*1000000//ft)/1000000
  pp,opp=opportunities[side];pga,short=opportunities[other]
  row={'gameId':int(landing['id']),'season':str(landing['season']),'gameDate':pd.Timestamp(landing['gameDate']),'teamId':int(team['id']),'opponentTeamAbbrev':opponent['abbrev'],'homeRoad':'H' if side=='home' else 'R','gamesPlayed':1,'wins':int(winner),'winsInShootout':int(period=='SO' and winner),'goalsFor':gf[side],'goalsAgainst':gf[other],'shotsForPerGame':sf,'shotsAgainstPerGame':sa,'faceoffWinPct':faceoff,'powerPlayGoalsFor':pp,'ppOpportunities':opp,'ppGoalsAgainst':pga,'timesShorthanded':short}
  row.update(shots_for=float(sf),shots_against=float(sa),goals_for=float(gf[side]),goals_against=float(gf[other]),shot_diff=float(sf-sa),shoot_pct=gf[side]/sf if sf>0 else np.nan,save_pct=1-gf[other]/sa if sa>0 else np.nan,faceoff_pct=faceoff,pp_rate=pp/opp if opp>0 else np.nan,pk_rate=1-pga/short if short>0 else np.nan)
  result.append(row)
 return pd.DataFrame(result)

COUNT_COLUMNS=['goalsFor','goalsAgainst','shotsForPerGame','shotsAgainstPerGame','faceoffWinPct','powerPlayGoalsFor','ppOpportunities','ppGoalsAgainst','timesShorthanded']
def parity(primary,adapter):
 for row in primary.to_dict('records'):
  match=adapter[adapter.teamId.eq(int(row['teamId']))]
  if len(match)!=1:raise ValueError('Official stat adapter team mismatch')
  for column in COUNT_COLUMNS:
   if not np.isclose(float(row[column]),float(match.iloc[0][column]),atol=1e-12 if column=='faceoffWinPct' else 0,rtol=0,equal_nan=True):raise ValueError('Official stat feeds disagree: '+column)
 return True
