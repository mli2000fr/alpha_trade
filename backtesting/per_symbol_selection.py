"""Run-local, configurable rankings from verified archived branch probabilities.

Never modifies trained contracts, serving selections, or SQL. A collision is
resolved by the larger calibrated profitability score; exact ties abstain.
There is no refill after collision resolution or later risk/holdings vetoes.
"""
from dataclasses import asdict,dataclass
import math
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerSymbolSelection:
    oracle_top_n: int = 20
    allow_long: bool = True
    allow_short: bool = False
    long_top_n: int = 5
    short_top_n: int = 5
    min_long_probability: float | None = None  # None preserves previous replay/CLI selections.

    def __post_init__(self):
        if type(self.allow_long) is not bool or type(self.allow_short) is not bool:
            raise ValueError('LONG/SHORT doivent être des booléens')
        if not self.allow_long and not self.allow_short:
            raise ValueError('Cocher au moins LONG ou SHORT pour la sélection per-symbol')
        for k in ['oracle_top_n','long_top_n','short_top_n']:
            if type(getattr(self,k)) is not int or getattr(self,k)<1:
                raise ValueError(k+' : entier positif requis')
        if ((self.allow_long and self.long_top_n>self.oracle_top_n) or
                (self.allow_short and self.short_top_n>self.oracle_top_n)):
            raise ValueError('TOP LONG/SHORT ne peut pas dépasser le TOP Oracle')
        value=self.min_long_probability
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1):
            raise ValueError('Seuil LONG : nombre fini entre 0 et 1 requis')

    def snapshot(self):return asdict(self)

    def describe(self):
        branches=[]
        if self.allow_long:
            branch=f'TOP{self.long_top_n} LONG'
            if self.min_long_probability is not None:branch+=f' (score > {self.min_long_probability:g})'
            branches.append(branch)
        if self.allow_short:branches.append(f'TOP{self.short_top_n} SHORT')
        return f'TOP{self.oracle_top_n} Oracle -> '+ ' + '.join(branches)+' per-symbol'


def select_per_symbol(verified,settings):
    """Independent branch rankings INSIDE the same fixed Oracle TOP-N."""
    a=verified.copy().rename(columns={'trade_date':'date'})
    a['date']=pd.to_datetime(a.date).dt.normalize()
    a['proba_extreme']=pd.to_numeric(a.proba_extreme,errors='coerce')
    if (a.empty or a.date.isna().any() or a.symbol.isna().any() or
            a.duplicated(['date','symbol']).any() or not a.proba_extreme.between(0,1).all()):
        raise ValueError('Scores Oracle absents, dupliqués ou invalides')
    a=a.drop(columns=['oracle_rank','long_rank','short_rank','selected','reason','rank','side'],errors='ignore')
    a=a.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True])
    a['oracle_rank']=a.groupby('date').cumcount()+1
    for side,allowed,count in [('long',settings.allow_long,settings.long_top_n),('short',settings.allow_short,settings.short_top_n)]:
        column=side+'_probability'
        p=pd.to_numeric(a[column],errors='coerce').astype(float)
        if (a[column].notna() & ~p.between(0,1)).any():raise ValueError('Score '+side+' invalide')
        a[column]=p
        eligible=a.oracle_rank.le(settings.oracle_top_n)&p.notna()
        ranked=a[eligible].sort_values(['date',column,'oracle_rank','symbol'],ascending=[True,False,True,True])
        positions=ranked[['date','symbol']].assign(**{side+'_rank':ranked.groupby('date').cumcount()+1})
        a=a.merge(positions,on=['date','symbol'],how='left',validate='one_to_one')
        a['retain_'+side]=a[side+'_rank'].le(count)&allowed
    conflict=a.retain_long&a.retain_short
    tie=conflict&np.isclose(a.long_probability,a.short_probability,rtol=0,atol=1e-12)
    a.loc[(conflict&(a.long_probability<a.short_probability))|tie,'retain_long']=False
    a.loc[(conflict&(a.short_probability<a.long_probability))|tie,'retain_short']=False
    # Apply AFTER the fixed TOP-N and direction collision resolution. Never
    # promote another rank/direction to replace a threshold rejection.
    a['long_selected_before_threshold']=a.retain_long.copy()
    a['long_score_threshold']=settings.min_long_probability
    a['long_threshold_passed']=(a.long_probability.notna() if settings.min_long_probability is None
        else a.long_probability.gt(settings.min_long_probability))
    below_long_threshold=a.retain_long&~a.long_threshold_passed
    a.loc[below_long_threshold,'retain_long']=False
    a['side']=np.where(a.retain_long,'long',np.where(a.retain_short,'short','flat'))
    a['selected']=a.retain_long|a.retain_short
    a['selection_probability']=np.where(a.retain_long,a.long_probability,np.where(a.retain_short,a.short_probability,np.nan))
    selected=a[a.selected].sort_values(['date','selection_probability','oracle_rank','symbol'],ascending=[True,False,True,True])
    priority=selected[['date','symbol']].assign(rank=selected.groupby('date').cumcount()+1)
    a=a.merge(priority,on=['date','symbol'],how='left',validate='one_to_one')
    a['reason']=np.where(a.oracle_rank.gt(settings.oracle_top_n),'OUTSIDE_ORACLE_POOL',
        np.where(tie,'DIRECTION_TIE_ABSTAIN',np.where(a.selected,'SELECTED_'+a.side.str.upper(),'BELOW_TOP_OR_MISSING_BRANCH')))
    a.loc[conflict&~tie,'reason']='DIRECTION_CONFLICT_KEEP_HIGHER_PROBABILITY'
    a.loc[below_long_threshold,'reason']='LONG_SCORE_NOT_ABOVE_THRESHOLD'
    return a
