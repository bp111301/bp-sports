"""Registered QB-count research only. Never writes production models or forecasts."""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT/'runtime/cfb_qb_repair_20261028/raw'
OUT = ROOT/'runtime/cfb_qb_repair_20261028/results'

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

cfb = module('qb_cfb', HERE.parent/'challengers_20261028/cfb.py')
audit = module('qb_audit', ROOT/'confidence_audit.py')
COUNTS = ['Comp','Att','Yds','Pass_TD','Int','Sck']
PASS_COLS = ['pos_team_id','pos_team','passer_player_name','game_id','season']+COUNTS
SCHEDULE_COLS = ['game_id','season','start_date','home_id','away_id','completed']
RATE_NAMES = ['completion','yards_per_attempt','td_per_attempt','int_per_attempt','sack_rate']
FEATURES = [f'qb_{window}_{rate}_diff' for window in ['last','recent3','incumbent3'] for rate in RATE_NAMES]+[f'qb_{f}_diff' for f in ['continuity','changed','attempt_share','prior_games','days_since']]

def download():
    RAW.mkdir(parents=True, exist_ok=True)
    def one(item):
        year, kind = item
        stem, group, suffix = ('adv_passing','espn_cfb_adv_passing','csv') if kind=='passing' else ('cfb_schedules','cfb_schedules','csv.gz')
        url = f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/{group}/{stem}_{year}.{suffix}'
        p = RAW/f'{stem}_{year}.{suffix}'
        if not p.exists():
            with urlopen(Request(url, headers={'User-Agent':'BP-Sports-Research/1.0'}), timeout=60) as r:
                p.write_bytes(r.read())
        raw = p.read_bytes()
        return {'path':str(p.relative_to(ROOT)), 'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(one,[(year,kind) for year in range(2015,2026) for kind in ['passing','schedule']]))
    (RAW.parent/'source_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    print('Downloaded', len(receipts), 'historical QB sources',flush=True)


def join_sources(passing, schedule):
    """Identity validation happens before any feature construction or fitting."""
    p = passing[PASS_COLS].copy()
    s = schedule[SCHEDULE_COLS].copy()
    for f in ['game_id','season','pos_team_id']+COUNTS:
        p[f] = pd.to_numeric(p[f],errors='coerce')
    for f in ['game_id','season','home_id','away_id']:
        s[f] = pd.to_numeric(s[f],errors='coerce')
    if s.duplicated(['season','game_id']).any():
        raise ValueError('Duplicate schedule identity')
    if s.season.dropna().gt(2025).any() or p.season.dropna().gt(2025).any():
        raise ValueError('Live seasons forbidden')
    s['source_date'] = pd.to_datetime(s.start_date,utc=True,errors='coerce').dt.normalize()
    valid = np.isfinite(p[['game_id','season','pos_team_id']+COUNTS].to_numpy(float)).all(axis=1)
    valid &= p.passer_player_name.notna() & p.passer_player_name.astype(str).str.strip().ne('')
    valid &= p.Att.gt(0) & p.Comp.ge(0) & p.Comp.le(p.Att) & p.Pass_TD.ge(0) & p.Int.ge(0) & p.Sck.ge(0)
    invalid = int((~valid).sum())
    p = p.loc[valid].copy()
    if p.duplicated(['season','game_id','pos_team_id','passer_player_name']).any():
        raise ValueError('Duplicate player/team/game')
    merged = p.merge(s,on=['season','game_id'],how='left',validate='many_to_one',indicator=True)
    matched = merged._merge.eq('both') & (merged.pos_team_id.eq(merged.home_id)|merged.pos_team_id.eq(merged.away_id)) & merged.source_date.notna()
    retention = float(matched.mean())
    if retention < .99:
        raise ValueError(f'Identity retention below99%: {retention}')
    completed = merged.completed.astype(str).str.lower().isin(['true','1'])
    report = {'raw_rows':len(passing),'structurally_invalid_rows':invalid,'valid_rows':len(p),'unmatched_identity_rows':int((~matched).sum()),'identity_retention':retention,'incomplete_rows':int((matched&~completed).sum())}
    return merged.loc[matched&completed].drop(columns='_merge').reset_index(drop=True),report


def rates(frame):
    sums = frame[COUNTS].sum()
    att = sums.Att
    return np.array([sums.Comp/att,sums.Yds/att,sums.Pass_TD/att,sums.Int/att,sums.Sck/(att+sums.Sck)],float)


def features(d, joined):
    groups = {(int(s),int(t)):g.sort_values(['source_date','game_id','Att','passer_player_name'],ascending=[True,True,False,True]) for (s,t),g in joined.groupby(['season','pos_team_id'])}
    x = pd.DataFrame(index=d.index,columns=FEATURES,dtype=float)
    covered = []; boundaries = []
    for i,row in d.iterrows():
        date = pd.to_datetime(row.start_date,utc=True).normalize()
        sides = []; side_dates = []
        for side in ['home','away']:
            g = groups.get((int(row.season),int(row[f'{side}_team_id'])))
            if g is None:
                sides.append(np.full(20,np.nan));side_dates.append(None);continue
            g = g[g.source_date.le(date-pd.Timedelta(days=2))]
            if g.empty:
                sides.append(np.full(20,np.nan));side_dates.append(None);continue
            primary = g.drop_duplicates('game_id',keep='first')
            last = primary.iloc[-1]
            recent = primary.tail(3)
            incumbent = g[g.passer_player_name.eq(last.passer_player_name)].tail(3)
            names = primary.passer_player_name.tolist()
            continuity = 0
            for name in reversed(names):
                if name!=names[-1]:break
                continuity += 1
            changed = float(names[-1]!=names[-2]) if len(names)>1 else np.nan
            total_att = g.loc[g.game_id.eq(last.game_id),'Att'].sum()
            z = np.r_[rates(primary.tail(1)),rates(recent),rates(incumbent),continuity,changed,last.Att/total_att,len(primary),(date-last.source_date).days]
            sides.append(z);side_dates.append(str(last.source_date))
        x.loc[i] = sides[0]-sides[1]
        covered.append(bool(np.isfinite(sides[0][0]) and np.isfinite(sides[1][0])))
        boundaries.append({'game_id':int(row.game_id),'season':int(row.season),'target_date':str(date),'home_source_max_date':side_dates[0],'away_source_max_date':side_dates[1]})
    evalmask = d.season.between(2019,2025)
    coverage = float(np.asarray(covered)[evalmask].mean())
    if coverage < .70:
        raise ValueError('Both-team prior QB coverage below70%')
    return x,{'both_team_prior_completion_coverage':coverage,'no_prior_on_one_or_both_teams':int((~np.asarray(covered)[evalmask]).sum())},boundaries


def learner(core):
    prep = ColumnTransformer([
        ('core',SimpleImputer(strategy='median',add_indicator=True),core),
        ('qb',SimpleImputer(strategy='median',keep_empty_features=True),FEATURES)],remainder='drop')
    return Pipeline([('prep',prep),('scale',StandardScaler()),('model',LogisticRegression(C=.5,max_iter=3000))])


def offset_fit(train_x, p, y):
    prep = Pipeline([('impute',SimpleImputer(strategy='median',keep_empty_features=True)),('scale',StandardScaler())])
    z = prep.fit_transform(train_x)
    z = np.column_stack([np.ones(len(z)),z])
    off = logit(np.clip(p,1e-6,1-1e-6))
    def objective(beta):
        eta = off+z@beta
        return float(np.sum(np.logaddexp(0,eta)-y*eta)+5*np.dot(beta,beta)), z.T@(expit(eta)-y)+10*beta
    fit = minimize(objective,np.zeros(z.shape[1]),jac=True,method='L-BFGS-B',tol=1e-9,options={'maxiter':2000})
    if not fit.success:
        raise ValueError('Offset optimization failed: '+fit.message)
    return prep,fit.x


def evaluate_predictions(pred):
    scores = {}
    for name,g in pred.groupby('candidate'):
        scores[name] = {'overall':audit.summarize(g.probability,g.home_win),'by_season':[{'season':int(s),**audit.summarize(q.probability,q.home_win)} for s,q in g.groupby('season')],'recent':audit.summarize(g[g.season.ge(2023)].probability,g[g.season.ge(2023)].home_win)}
    pivot = pred.pivot(index='game_id',columns='candidate',values='probability')
    meta = pred[pred.candidate.eq('control')].set_index('game_id').loc[pivot.index]
    correct = (pivot.to_numpy()>=.5)==meta.home_win.to_numpy()[:,None]
    b = pd.DataFrame(correct.astype(int),columns=pivot.columns);b['block']=meta.block.to_numpy()
    totals = b.groupby('block')[list(pivot.columns)].sum().to_numpy();counts = b.groupby('block').size().to_numpy()
    rng = np.random.default_rng(20261028);ix = rng.integers(0,len(counts),size=(2000,len(counts)))
    samples = totals[ix].sum(axis=1)/counts[ix].sum(axis=1)[:,None];control_index=list(pivot.columns).index('control')
    decisions = {}; c=scores['control']
    for j,name in enumerate(pivot.columns):
        if name=='control':continue
        a=scores[name];am=a['overall']['overall'];cm=c['overall']['overall'];ar=a['recent']['overall'];cr=c['recent']['overall']
        improved=sum(q['overall']['brier']<r['overall']['brier'] for q,r in zip(a['by_season'],c['by_season']))
        checks={'accuracy_gain':am['accuracy']>=cm['accuracy']+.005,'brier':am['brier']<cm['brier'],'log_loss':am['log_loss']<cm['log_loss'],'ece':a['overall']['ece']<=c['overall']['ece'],'season_consistency':improved>=5,'recent_accuracy':ar['accuracy']>=cr['accuracy'],'recent_brier':ar['brier']<=cr['brier'],'recent_log_loss':ar['log_loss']<=cr['log_loss']}
        decisions[name]={'research_eligible':bool(all(checks.values())),'checks':{k:bool(v) for k,v in checks.items()},'seasons_brier_improved':improved,'accuracy_difference':float(correct[:,j].mean()-correct[:,control_index].mean()),'paired_block_bootstrap_95pct':np.quantile(samples[:,j]-samples[:,control_index],[.025,.975]).tolist(),'production_promoted':False}
    return scores,decisions


def run():
    d = cfb.guarded_data(ROOT/'runtime/challengers_20261028/cfb/matchup_line')
    passing = pd.concat([pd.read_csv(RAW/f'adv_passing_{s}.csv',usecols=PASS_COLS) for s in range(2015,2026)],ignore_index=True)
    schedule = pd.concat([pd.read_csv(RAW/f'cfb_schedules_{s}.csv.gz',usecols=SCHEDULE_COLS) for s in range(2015,2026)],ignore_index=True)
    joined,coverage = join_sources(passing,schedule)
    extra,coverage2,boundaries = features(d,joined);coverage.update(coverage2)
    x,px,cf,pf=cfb.matrices(d);z=x.join(extra);pz=px.join(extra)
    controls={};rows=[];folds=[]
    for season in range(2018,2026):
        tr=cfb.training_index(d,season);te=d.index[d.season.eq(season)]
        p=cfb.ensemble(cfb.fit_parts(d,x,px,cf,pf,tr),x,px,cf,pf,te)
        controls[season]=pd.Series(p,index=te)
        if season<2019:continue
        models=[learner(cf),learner(pf)]
        models[0].fit(z.loc[tr],d.loc[tr,'home_win']);models[1].fit(pz.loc[tr],d.loc[tr,'home_win'])
        q=.25*models[0].predict_proba(z.loc[te])[:,1]+.75*models[1].predict_proba(pz.loc[te])[:,1]
        years=sorted(s for s in controls if s<season)[-3:];oof=pd.concat([controls[s] for s in years]);oi=oof.index
        if len(oi)<200 or not d.loc[oi,'season'].lt(season).all():raise ValueError('Invalid offset training')
        prep,beta=offset_fit(extra.loc[oi],oof.to_numpy(),d.loc[oi,'home_win'].to_numpy())
        zx=prep.transform(extra.loc[te]);op=expit(logit(np.clip(p,1e-6,1-1e-6))+beta[0]+zx@beta[1:])
        for name,prob in [('control',p),('qb_counts_augmented',q),('qb_counts_halfblend',.5*p+.5*q),('qb_offset_correction',op)]:
            for i,v in zip(te,prob):rows.append({'game_id':int(d.at[i,'game_id']),'season':season,'candidate':name,'block':f'{season}:{d.at[i,"week"]}','home_win':int(d.at[i,'home_win']),'probability':float(v),'training_max_season':int(d.loc[tr,'season'].max())})
        folds.append({'test_season':season,'training_max_season':int(d.loc[tr,'season'].max()),'offset_oof_seasons':years,'offset_rows':len(oi)})
        print('QB fold',season,'complete',flush=True)
    pred=pd.DataFrame(rows)
    if len(pred[pred.candidate.eq('control')])!=4999:raise ValueError('Common evaluation cohort changed')
    archive=pd.read_csv(ROOT/'research/strength_challengers_20261028/results/cfb/development_predictions.csv.gz')
    reference=archive[archive.candidate.eq('control')&archive.season.ge(2019)].set_index('game_id').sort_index()
    actual=pred[pred.candidate.eq('control')].set_index('game_id').sort_index()
    if not actual.index.equals(reference.index) or not np.array_equal(actual.home_win,reference.home_win) or not np.allclose(actual.probability,reference.probability,atol=1e-12,rtol=0):raise ValueError('Archived original control parity failed')
    scores,decisions=evaluate_predictions(pred)
    result={'status':'reused_historical_development_only','live_labels_used':False,'protocol_sha256':hashlib.sha256((HERE/'PROTOCOL.md').read_bytes()).hexdigest(),'coverage':coverage,'scores':scores,'decisions':decisions,'features':FEATURES,'fold_boundaries':folds,'control_reproduction_tolerance':1e-12,'missingness':{f:float(extra.loc[d.season.between(2019,2025),f].isna().mean()) for f in FEATURES}}
    OUT.mkdir(parents=True,exist_ok=True);pred.to_csv(OUT/'predictions.csv',index=False);extra.join(d[['game_id','season']]).to_csv(OUT/'features.csv',index=False)
    (OUT/'temporal_boundaries.json').write_text(json.dumps(boundaries,indent=2)+'\n');(OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'coverage':coverage,'scores':{k:v['overall']['overall'] for k,v in scores.items()},'decisions':decisions},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');args=parser.parse_args()
    if args.download:download()
    else:run()
