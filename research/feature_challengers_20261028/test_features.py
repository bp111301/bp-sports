import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('new_features',Path(__file__).with_name('experiment.py'))
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


class FeatureSafety(unittest.TestCase):
    def cfb(self):
        d=pd.DataFrame({'game_id':[1,2],'season':[2020,2021],'week':[1,8],
            'home_points':[10,21],'away_points':[20,10],'neutral_site':[False,False]})
        features=set(e.EXTRA_BASES)|set(e.cfb.pri.BLEND_BASES)
        for f in features:
            for side,n in [('home',.3),('away',.1)]:
                d[f'{side}_{f}']=n+.1;d[f'prev_{side}_{f}']=n
        return d

    def nhl(self):
        d=pd.DataFrame({'game_id':range(1,9),'season':['20212022']*8,
            'game_date':pd.date_range('2021-10-01',periods=8),'home_id':[1]*8,'away_id':[2]*8})
        rows=[]
        for g in d.itertuples():
            for team in [1,2]:
                rows.append({'gameId':g.game_id,'gameDate':g.game_date,'season':g.season,'teamId':team,
                    'goalsFor':2.,'shotsForPerGame':20.,'goalsAgainst':1.,'shotsAgainstPerGame':20.,
                    'powerPlayGoalsFor':1. if team==1 and g.game_id==1 else 0.,
                    'ppOpportunities':1. if g.game_id==1 else 10.,'ppGoalsAgainst':0.,'timesShorthanded':5.})
        return d,pd.DataFrame(rows)

    def test_cfb_future_labels_player_and_market_fields_do_not_enter_features(self):
        d=self.cfb();*_,before=e.expanded_cfb(d)
        changed=d.copy();changed['home_points']=999;changed['away_points']=0
        changed['spread']=-100;changed['home_qb_name']='Future realized QB';changed['home_athlete_id']=99999
        *_,after=e.expanded_cfb(changed)
        pd.testing.assert_frame_equal(before,after)

    def test_cfb_side_swap_and_prior_week_boundary(self):
        d=self.cfb();*_,before=e.expanded_cfb(d)
        swapped=d.copy()
        for c in d:
            if c.startswith('home_') and 'away_'+c[5:] in d:swapped[c]=d['away_'+c[5:]]
            elif c.startswith('away_') and 'home_'+c[5:] in d:swapped[c]=d['home_'+c[5:]]
            elif c.startswith('prev_home_'):swapped[c]=d[c.replace('prev_home_','prev_away_')]
            elif c.startswith('prev_away_'):swapped[c]=d[c.replace('prev_away_','prev_home_')]
        *_,after=e.expanded_cfb(swapped)
        np.testing.assert_allclose(before.to_numpy(),-after.to_numpy(),equal_nan=True)
        self.assertAlmostEqual(before.iloc[0]['blend_off_wepa_diff'],.2)
        missing=d.copy();missing.loc[0,'home_off_wepa']=np.nan;missing.loc[0,'prev_home_off_wepa']=np.nan
        *_,out=e.expanded_cfb(missing);self.assertTrue(pd.isna(out.iloc[0]['blend_off_wepa_diff']))

    def test_nhl_target_previous_day_future_labels_cannot_change_earlier_features(self):
        d,t=self.nhl();before,_=e.pooled_rates(d,t)
        changed=t.copy();changed.loc[changed.gameId.ge(4),'powerPlayGoalsFor']=10.
        after,_=e.pooled_rates(d,changed)
        pd.testing.assert_frame_equal(before.iloc[:5],after.iloc[:5])
        self.assertNotEqual(before.iloc[6].pooled_pp20_diff,after.iloc[6].pooled_pp20_diff)

    def test_nhl_counts_are_aggregated_not_equal_weight_percentages(self):
        d,t=self.nhl();x,b=e.pooled_rates(d,t)
        # On day 6, four source games through day 4. League PP prior = 1/62.
        prior=1/62
        home=(1+20*prior)/(31+20);away=(0+20*prior)/(31+20)
        self.assertAlmostEqual(x.iloc[5].pooled_pp20_diff,home-away)
        self.assertLess(x.iloc[5].pooled_pp20_diff,1/4)
        for item in b:
            if item['source_max_date']:
                self.assertGreaterEqual((pd.Timestamp(item['target_date'])-pd.Timestamp(item['source_max_date'])).days,2)

    def test_nhl_missing_values_are_not_zero_and_zero_opportunities_are_valid(self):
        d,t=self.nhl();t.loc[t.teamId.eq(1),'ppOpportunities']=0.;t.loc[t.teamId.eq(1),'powerPlayGoalsFor']=0.
        zero,_=e.pooled_rates(d,t);self.assertTrue(np.isfinite(zero.iloc[5].pooled_pp20_diff))
        t.loc[t.teamId.eq(1),'ppOpportunities']=np.nan
        missing,_=e.pooled_rates(d,t);self.assertTrue(pd.isna(missing.iloc[5].pooled_pp20_diff))

    def test_nhl_duplicate_rows_rejected_and_order_invariant(self):
        d,t=self.nhl();a,_=e.pooled_rates(d,t);b,_=e.pooled_rates(d,t.sample(frac=1,random_state=9))
        pd.testing.assert_frame_equal(a,b)
        with self.assertRaises(ValueError):e.pooled_rates(d,pd.concat([t,t.iloc[[0]]]))

    def test_postseason_correction_uses_current_efficiency_without_mutating_source(self):
        spec=importlib.util.spec_from_file_location('test_postseason',Path(__file__).with_name('postseason.py'))
        p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
        d=self.cfb();d['season_type']=['regular','postseason'];d['week']=1;original=d.copy(deep=True)
        fixed=p.prior_input(d)
        values=e.cfb.pri.blend_side(fixed,'home','off_epa',7.)
        self.assertEqual(values.iloc[0],d.iloc[0].prev_home_off_epa)
        self.assertEqual(values.iloc[1],d.iloc[1].home_off_epa)
        pd.testing.assert_frame_equal(d,original)
        bad=d.copy();bad['season_type']='unknown'
        with self.assertRaises(ValueError):p.prior_input(bad)


if __name__=='__main__':unittest.main()
