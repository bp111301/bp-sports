import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from compare_freeze import *
import io
import subprocess
import requests

def verify_frozen(require_committed=True):
    manifest=json.loads((MODEL/'manifest.json').read_text())
    if require_committed:
        subprocess.run(['git','ls-files','--error-unmatch','model/nba/v1/manifest.json','model/nba/v1/frozen_bundle.joblib'],cwd=ROOT,check=True,capture_output=True)
    assert sha(MODEL/'frozen_bundle.joblib')==manifest['bundle_sha256']
    assert sha(HERE/'PROTOCOL.md')==manifest['protocol_sha256']
    assert sha(HERE/'compare_freeze.py')==manifest['compare_code_sha256']
    assert sha(Path(__file__))==manifest['evaluation_code_sha256']
    assert sha(ROOT/'research/nba/baseline.py')==manifest['baseline_code_sha256']
    assert source_hashes()==manifest['source_hashes']
    assert manifest['training_seasons']==list(range(2016,2026))
    assert manifest['training_last_date']<'2025-10-01'
    assert sklearn.__version__==manifest['runtime']['sklearn'] and np.__version__==manifest['runtime']['numpy']
    return manifest

def main():
    manifest=verify_frozen()
    result=OUT/'excluded_season_evaluation.json'
    if result.exists():
        saved=json.loads(result.read_text())
        assert saved['bundle_sha256']==manifest['bundle_sha256']
        print('First excluded-season evaluation preserved; no rescoring');return
    files=[]
    for kind,tag,stem in [('box','espn_nba_team_boxscores','team_box'),('schedule','espn_nba_schedules','nba_schedule')]:
        url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/{tag}/{stem}_2026.parquet'
        path=ROOT/f'data/nba/source/{kind}_2026.parquet'
        if not path.exists():
            response=requests.get(url,timeout=90);response.raise_for_status();frame=pd.read_parquet(io.BytesIO(response.content))
            assert set(pd.to_numeric(frame.season).unique())=={2026}
            path.write_bytes(response.content)
        files.append(dict(path=str(path.relative_to(ROOT)),url=url,sha256=sha(path)))
    games,audit=load_games(range(2016,2027));f=build_features(games);hold=f[f.season==2026].copy()
    assert len(hold)>0 and hold.date.min()>manifest['training_last_date']
    bundle=joblib.load(MODEL/'frozen_bundle.joblib')
    hold['selected_probability']=predict_bundle(bundle,hold)
    hold['home_frequency_probability']=bundle['home_frequency']
    scores={name:metrics(hold.y,hold[col]) for name,col in [('selected','selected_probability'),('elo','elo_probability'),('home_frequency','home_frequency_probability')]}
    a=audit[-1];excluded=a['excluded'];eligible_completed=a['schedule_regular']-sum(excluded.get(k,0) for k in ('unfinished','exhibition_non_nba_teams','cup_championship'))
    coverage=len(hold)/eligible_completed
    gates=dict(minimum_games=len(hold)>=1000,coverage_99_percent=coverage>=.99,accuracy_60_percent=scores['selected']['accuracy']>=.60,
        beats_elo_brier=scores['selected']['brier']<scores['elo']['brier'],beats_elo_log_loss=scores['selected']['log_loss']<scores['elo']['log_loss'],
        beats_home_brier=scores['selected']['brier']<scores['home_frequency']['brier'],beats_home_log_loss=scores['selected']['log_loss']<scores['home_frequency']['log_loss'])
    months=[dict(month=m,**metrics(g.y,g.selected_probability)) for m,g in hold.groupby(hold.date.str[:7])]
    calibration=[]
    for i in range(10):
        g=hold[(hold.selected_probability>=i/10)&(hold.selected_probability<(i+1)/10)]
        if len(g):calibration.append(dict(lower=i/10,games=len(g),mean_probability=float(g.selected_probability.mean()),home_win_rate=float(g.y.mean())))
    hold.to_csv(OUT/'excluded_season_predictions.csv',index=False)
    summary=dict(status='eligible_for_prospective_collection' if all(gates.values()) else 'research_only_failed_release_gate',evaluated_at=datetime.now(timezone.utc).isoformat(),selected=manifest['selected'],season=2026,weights_retrained=False,automatic_production_promotion=False,gate_passed=all(gates.values()),gates=gates,metrics=scores,coverage=coverage,source_audit=a,monthly=months,calibration=calibration,bundle_sha256=manifest['bundle_sha256'],frozen_at=manifest['created_at'],freeze_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_files=files)
    result.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
