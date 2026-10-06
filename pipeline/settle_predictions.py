"""Settle immutable B.P. Sports prediction snapshots and write tracking metrics."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd

def prob_home(row,pick_col,conf_col): return float(row[conf_col]) if row[pick_col]==row.home_team else 1-float(row[conf_col])
def metrics(frame,pick_col,conf_col):
    if frame.empty: return {'games':0,'correct':0,'accuracy':None,'brier':None,'log_loss':None}
    y=(frame.actual_home_score>frame.actual_away_score).astype(int).to_numpy(); p=np.array([prob_home(r,pick_col,conf_col) for _,r in frame.iterrows()]); pred=np.where(p>=.5,frame.home_team,frame.away_team); actual=np.where(y==1,frame.home_team,frame.away_team)
    p=np.clip(p,.001,.999); return {'games':len(frame),'correct':int(np.sum(pred==actual)),'accuracy':float(np.mean(pred==actual)),'brier':float(np.mean((p-y)**2)),'log_loss':float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p)))}
def main():
    p=argparse.ArgumentParser(); p.add_argument('--ledger',default='data/ledger/prediction_ledger.csv'); p.add_argument('--schedules',default='data/current/schedules.csv'); a=p.parse_args(); lp=Path(a.ledger)
    ledger=pd.read_csv(lp); sched=pd.read_csv(a.schedules); finals=sched[sched.home_score.notna()&sched.away_score.notna()].set_index('game_id'); out=ledger.copy()
    for i,r in out.iterrows():
        if str(r.get('settlement_status','pending'))!='pending' or r.game_id not in finals.index: continue
        f=finals.loc[r.game_id]; out.loc[i,'actual_home_score']=f.home_score; out.loc[i,'actual_away_score']=f.away_score; out.loc[i,'settlement_status']='tie' if f.home_score==f.away_score else 'final'; out.loc[i,'scored_at_utc']=pd.Timestamp.now(tz='UTC').isoformat()
    locked=[c for c in ledger.columns if c not in ['actual_home_score','actual_away_score','settlement_status','scored_at_utc']]; pd.testing.assert_frame_equal(ledger[locked],out[locked],check_dtype=False)
    tmp=lp.with_suffix('.csv.partial'); out.to_csv(tmp,index=False); tmp.replace(lp)
    first=out.sort_values('captured_at_utc').drop_duplicates('game_id',keep='first'); final=first[first.settlement_status.eq('final')].copy()
    summary={'evaluation_rule':'First captured pregame snapshot per game; ties excluded','unique_games':int(first.game_id.nunique()),'settled_games':len(final),'pending_games':int(first.settlement_status.eq('pending').sum()),'v3':metrics(final,'v3_pick','v3_confidence'),'v4_core':metrics(final,'v4_pick','v4_core_confidence'),'v4_adjusted':metrics(final,'v4_pick','v4_adjusted_confidence')}
    (lp.parent/'summary.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
