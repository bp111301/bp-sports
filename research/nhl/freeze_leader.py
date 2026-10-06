"""Fit frozen weights using training-only downloads before final evaluation."""
import hashlib,json,platform
from pathlib import Path
import joblib
import sklearn
from experiment_goalies import base,adv,model

def checksum(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    root=Path('model/nhl/v1');config=json.loads((root/'config.json').read_text())
    if config['calibrator']['method']!='raw':raise ValueError('Unexpected calibration change')
    d=base.load('runtime/nhl/freeze_training_games')
    if set(d.season)!=set(config['training_seasons']):raise ValueError('Unexpected training seasons')
    x,af=adv.attach(d,base.build_features(d),adv.load_team_stats('runtime/nhl/freeze_training_team_stats'),20)
    features=base.FEATURES+af
    if features!=config['features']:raise ValueError('Frozen feature order changed')
    m=model(features);m.fit(x[features],d.home_win)
    joblib.dump({'model':m,'config':config},root/'frozen_bundle.joblib',compress=3)
    sources={str(p):checksum(p) for folder in ['runtime/nhl/freeze_training_games','runtime/nhl/freeze_training_team_stats'] for p in sorted(Path(folder).glob('*.csv'))}
    manifest={'version':config['version'],'training_seasons':sorted(d.season.unique().tolist()),'training_games':len(d),'last_training_game_date':str(d.game_date.max().date()),'features':features,'config_sha256':checksum(root/'config.json'),'bundle_sha256':checksum(root/'frozen_bundle.joblib'),'source_sha256':sources,'feature_code_sha256':{str(p):checksum(p) for p in [Path('research/nhl/backtest_baseline.py'),Path('research/nhl/experiment_team_stats.py'),Path('research/nhl/experiment_goalies.py')]},'python':platform.python_version(),'sklearn':sklearn.__version__,'pandas':__import__('pandas').__version__,'numpy':__import__('numpy').__version__,'status':'research freeze; no production activation'}
    (root/'bundle_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
