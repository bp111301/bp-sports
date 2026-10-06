"""Read-only feature-source diagnosis, including failed season; no fitting."""
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from experiment_goalies import base,adv,DEV

def main():
    train=base.load('runtime/nhl/v2/games');failed=base.load('runtime/nhl/v2/audit_games')
    if (train.season>DEV[-1]).any() or set(failed.season)!={'20252026'}:raise ValueError('Unexpected source audit boundary')
    d=pd.concat([train,failed],ignore_index=True).sort_values(['season','game_date','game_id']).reset_index(drop=True)
    t=pd.concat([adv.load_team_stats('runtime/nhl/v2/team_stats'),adv.load_team_stats('runtime/nhl/v2/audit_team_stats')],ignore_index=True)
    x,af=adv.attach(d,base.build_features(d),t,20);features=base.FEATURES+af
    keys=pd.concat([d[['game_id','home_id']].rename(columns={'home_id':'teamId'}),d[['game_id','away_id']].rename(columns={'away_id':'teamId'})]).rename(columns={'game_id':'gameId'})
    joined=keys.merge(t[['gameId','teamId']],on=['gameId','teamId'],how='left',indicator=True,validate='one_to_one')
    coverage=float(joined._merge.eq('both').mean())
    rows=[];warnings=[]
    for feature in features:
        old=x.loc[d.season.isin(DEV),feature];new=x.loc[d.season=='20252026',feature]
        valid=old.dropna();current=new.dropna();sd=float(valid.std()) if len(valid)>1 else 0.
        shifted=(float(current.mean())-float(valid.mean()))/sd if sd>0 and len(current) else None
        edges=np.unique(valid.quantile(np.linspace(0,1,11)).to_numpy())
        psi=None
        if len(edges)>2 and len(current):
            edges[0]=-np.inf;edges[-1]=np.inf
            a=np.histogram(valid,edges)[0]/len(valid);b=np.histogram(current,edges)[0]/len(current);a=np.clip(a,1e-6,1);b=np.clip(b,1e-6,1)
            psi=float(np.sum((b-a)*np.log(b/a)))
        r={'feature':feature,'development_missing':float(old.isna().mean()),'failed_season_missing':float(new.isna().mean()),'development_mean':float(valid.mean()) if len(valid) else None,'failed_season_mean':float(current.mean()) if len(current) else None,'mean_shift_in_development_sd':shifted,'population_stability_index':psi}
        if r['failed_season_missing']-r['development_missing']>.1:warnings.append(feature+': increased missingness >10 percentage points')
        rows.append(r)
    domains={}
    for season,z in t.groupby('season'):
        domains[str(season)]={c:{'rows':len(z),'missing':int(z[c].isna().sum()),'negative':int((z[c]<0).sum()),'over_one':int((z[c]>1).sum()) if c in ['shoot_pct','save_pct','faceoff_pct','pp_rate','pk_rate'] else None} for c in adv.RAW}
    report={'scope':'read-only failed-season feature audit; no candidate scored or fitted on failed season','team_game_join_coverage':coverage,'features':rows,'raw_stat_domains':domains,'missingness_warnings':warnings,'interpretation':'PSI and mean shifts are descriptive; no thresholds are tuned against 2025-26. Identical joins alone do not prove features are equally predictive.'}
    out=Path('research/nhl/v2/results');out.mkdir(parents=True,exist_ok=True);(out/'failed_season_feature_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# NHL Feature Consistency Audit','','Read-only source diagnosis; excluded-season labels never train or select V2 candidates.',f'Team-game join coverage: {coverage:.2%}.',f'Missingness warnings: {warnings}.','','| Feature | Development missing | Failed-season missing | Mean shift (SD) | PSI |','|---|---:|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['feature']} | {r['development_missing']:.2%} | {r['failed_season_missing']:.2%} | {r['mean_shift_in_development_sd'] if r['mean_shift_in_development_sd'] is not None else '—'} | {r['population_stability_index'] if r['population_stability_index'] is not None else '—'} |")
    lines+=['',report['interpretation']];(out/'FEATURE_CONSISTENCY.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
    if coverage!=1. or warnings:raise ValueError('Feature source audit requires investigation before model tournament')
if __name__=='__main__':main()
