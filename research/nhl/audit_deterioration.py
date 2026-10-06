"""Read-only result/source audit; no fitting, tuning or evaluation rerun."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from download_team_game_stats import fetch

def main():
    out=Path('research/nhl/results')
    saved=pd.read_csv(out/'excluded_season_predictions.csv',dtype={'season':str})
    dev=pd.read_csv(out/'factor_oof_predictions.csv',dtype={'season':str});dev=dev[dev.candidate=='advanced_all_w20']
    games=pd.read_csv('runtime/nhl/audit_games/nhl_games_20252026.csv',dtype={'season':str})
    stats=pd.DataFrame(fetch('summary','20252026'))
    home=stats.rename(columns={c:'stat_'+c for c in stats.columns})
    z=games.merge(home,left_on=['game_id','home_id'],right_on=['stat_gameId','stat_teamId'],how='left',validate='one_to_one')
    a=games.merge(stats,left_on=['game_id','away_id'],right_on=['gameId','teamId'],how='left',validate='one_to_one')
    actual=(games.home_score>games.away_score).astype(int)
    joined=games.merge(saved,on='game_id',suffixes=('_source','_saved'),validate='one_to_one')
    source_checks={'schedule_games':len(games),'schedule_duplicate_ids':int(games.game_id.duplicated().sum()),'tied_final_scores':int((games.home_score==games.away_score).sum()),'game_state_counts':games.game_state.value_counts().to_dict(),'team_stat_rows':len(stats),'team_stat_duplicate_keys':int(stats.duplicated(['gameId','teamId']).sum()),'home_team_stats_matched':int(z.stat_gameId.notna().sum()),'away_team_stats_matched':int(a.gameId.notna().sum()),'home_win_label_disagreements_vs_stats':int((actual!=z.stat_wins).sum()),'away_win_label_disagreements_vs_stats':int(((1-actual)!=a.wins).sum()),'noncomplementary_stats_winners':int(((z.stat_wins+a.wins)!=1).sum()),'saved_label_disagreements_vs_new_schedule':int((joined.home_win!=(joined.home_score>joined.away_score).astype(int)).sum()),'saved_home_team_disagreements':int((joined.home_team_source!=joined.home_team_saved).sum()),'saved_away_team_disagreements':int((joined.away_team_source!=joined.away_team_saved).sum()),'stat_home_road_values':stats.homeRoad.value_counts().to_dict(),'home_score_disagreements_vs_stats':int((games.home_score!=z.stat_goalsFor).sum()),'away_score_disagreements_vs_stats':int((games.away_score!=a.goalsFor).sum())}
    season_rows=[]
    for season,q in pd.concat([dev.rename(columns={'home_win_prob':'calibrated_prob'}),saved],ignore_index=True).groupby('season'):
        p=q.calibrated_prob;correct=(p>=.5)==q.home_win
        season_rows.append({'season':season,'games':len(q),'accuracy':float(correct.mean()),'home_win_rate':float(q.home_win.mean()),'home_pick_rate':float((p>=.5).mean()),'mean_pick_confidence':float(np.maximum(p,1-p).mean()),'probability_outcome_correlation':float(p.corr(q.home_win))})
    before=dev.assign(correct=(dev.home_win_prob>=.5)==dev.home_win)
    after=saved.assign(correct=(saved.calibrated_prob>=.5)==saved.home_win)
    teams=[]
    for team,q in after.groupby('home_team'):
        earlier=before[before.home_team==team]
        teams.append({'home_team':team,'evaluation_games':len(q),'evaluation_accuracy':float(q.correct.mean()),'development_home_games':len(earlier),'development_accuracy':float(earlier.correct.mean()) if len(earlier) else None})
    result={'scope':'read-only source and saved-prediction diagnosis; frozen weights/config unchanged','source_checks':source_checks,'by_season':season_rows,'home_team_accuracy':teams,'leader_baseline_pick_disagreements':int(((saved.calibrated_prob>=.5)!=(saved.baseline_prob>=.5)).sum()),'limitations':'Descriptive diagnostics cannot uniquely attribute deterioration to roster changes, injuries, parity, or model overfitting. No alternative candidate is scored on the excluded season.'}
    (out/'deterioration_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# NHL Deterioration Audit','','Read-only audit. No model fitting, tuning, release, or excluded-season rerun.','','| Season | Accuracy | Home win rate | Home pick rate | Mean confidence |','|---|---:|---:|---:|---:|']
    for r in season_rows:lines.append(f"| {r['season']} | {r['accuracy']:.2%} | {r['home_win_rate']:.2%} | {r['home_pick_rate']:.2%} | {r['mean_pick_confidence']:.2%} |")
    lines+=['','## Independent NHL schedule/stat-summary agreement','','```json',json.dumps(source_checks,indent=2),'```','',result['limitations']]
    (out/'DETERIORATION_AUDIT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
if __name__=='__main__':main()
