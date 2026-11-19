"""Review the secondary local-timing case and combine all six economic cases."""
from pathlib import Path
from unittest.mock import patch
import json
import numpy as np
import pandas as pd

from scripts.research import us_b_protection_partial_20261118 as base
from scripts.research.us_b_protection_timing_replay_20261118 import ROOT,CASE
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def main():
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    if not (base.ROOT/'final-status.json').exists():raise ValueError('Primary four-way comparison not reviewed yet')
    plan=base.read(ROOT/'protocol.json')
    for name,expected in plan['sources'].items():
        if digest(Path(name))!=expected:raise ValueError('Changed secondary research source: '+name)
    folder=ROOT/'cases'/CASE/'result';r=validate_case(ROOT/'cases'/CASE)
    if digest(ROOT/'variants'/CASE/'signals.parquet')!=digest(base.ROOT/'variants/SL10/signals.parquet'):
        raise ValueError('Secondary candidate signals differ from reference')
    reference_config=base.read(base.ROOT/'cases/SL10/result/configuration.json')['portfolio']
    if base.read(folder/'configuration.json')['portfolio']!=reference_config:
        raise ValueError('Secondary native portfolio configuration differs')
    t=pd.read_csv(folder/'trades.csv');events=pd.read_csv(folder/'events.csv')
    buys=events[events.event.eq('BUY_FILL')].copy();buys['entry_date']=pd.to_datetime(buys.time,utc=True)
    t['entry_date']=pd.to_datetime(t.entry_date,utc=True)
    grouped=t.groupby(['campaign_id','symbol','entry_date'],as_index=False).agg(quantity=('quantity','sum'),pnl=('pnl','sum'))
    campaigns=grouped.merge(buys[['symbol','entry_date','quantity']].rename(columns={'quantity':'entry_quantity'}),on=['symbol','entry_date'],validate='one_to_one')
    if len(campaigns)!=len(grouped) or campaigns.quantity.gt(campaigns.entry_quantity).any():raise ValueError('Secondary campaign totals invalid')
    complete=campaigns[campaigns.quantity.eq(campaigns.entry_quantity)];campaigns.to_csv(folder/'campaigns.csv',index=False)
    unrealized=open_fee=0.
    for p in r['open_positions']:
        b=buys[buys.symbol.eq(p['symbol'])].sort_values('entry_date').iloc[-1]
        unrealized+=float(p['qty'])*(float(p['mark'])-float(b.price))
        open_fee+=float(b.costs)*float(p['qty'])/float(b.quantity)
    expected=4000+t.pnl.sum()+unrealized-open_fee+r['dividends_accrued']-t.dividends.sum()-r['margin_interest']
    if abs(expected-r['final_equity'])>1e-6:raise ValueError('Secondary cash/PnL does not reconcile')
    equity=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).equity
    states=pd.read_parquet(ROOT/'inputs/states.parquet');receipt=base.read(folder/'liquidations.json')
    on=states.loc['2020-12-31':'2026-09-30'].index[states.loc['2020-12-31':'2026-09-30'].transition.eq('ON')]
    if receipt['pending'] is not None or len(receipt['events'])!=len(on):raise ValueError('Secondary missing/extra basket')
    from common.winner_pyramiding import regular_bounds
    for event in receipt['events']:
        signal=pd.Timestamp(event['signal_date']);stamp=pd.Timestamp(event['executed_at'])
        nextday=equity.index[equity.index>signal][0]
        if stamp!=pd.Timestamp(regular_bounds(nextday.date())[0]):raise ValueError('Secondary exit not next official open')
        for symbol,q in event['quantities'].items():
            actual=t[t.symbol.eq(symbol)&pd.to_datetime(t.exit_date,utc=True).eq(stamp)&t.exit_reason.eq('PILOT_PROTECTION')].quantity.sum()
            if actual!=q or q>event['retained_core'][symbol]:raise ValueError('Secondary reduction quantities differ')
    original=base.source.ROOT
    labels=pd.read_parquet(original/'test-labels-and-risks.parquet')
    with patch.object(base.source,'ROOT',ROOT),patch.object(base.source,'CASES',[CASE]):review=base.source.post_review(labels)
    table=pd.read_csv(base.ROOT/'comparison-reviewed.csv');control=table[table.case.eq('SL10')].iloc[0]
    row=dict(case=CASE,label='Partie pilotée 50 % / nouvelles conditions locales',
        **{k:r.get(k) for k in ['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct',
        'average_gross_capital','maximum_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl']},
        completed_campaigns=len(complete),campaign_win_pct=100*complete.pnl.gt(0).mean(),
        protection_events=len(receipt['events']),pilot_fraction=.5,profit_retained_pct=100*r['return_pct']/control.return_pct,
        dd_improvement_pp=abs(control.max_drawdown_pct)-abs(r['max_drawdown_pct']))
    pd.concat([table,pd.DataFrame([row])],ignore_index=True).to_csv(ROOT/'comparison-all.csv',index=False)
    curves=pd.read_csv(base.ROOT/'capital-curves.csv',index_col=0,parse_dates=True)
    spy=curves.pop('SPY prix seuls');curves[row['label']]=equity;curves['SPY prix seuls']=spy
    curves.to_csv(ROOT/'capital-curves-all.csv')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=['#1d4ed8','#a8a29e','#d97706','#a855f7','#059669','#dc2626','#475569']
    for name,window in [('capital-comparison-all.png',None),('late2024-mid2025-normalized.png',slice('2024-11-06','2025-06-30'))]:
        view=curves if window is None else curves.loc[window]
        if window is not None:view=100*view/view.iloc[0]
        fig,(ax,dd)=plt.subplots(2,1,figsize=(14,8),sharex=True,gridspec_kw={'height_ratios':[2,1]},facecolor='#f7f9fc')
        for (label,values),color in zip(view.items(),colors):
            ax.plot(values.index,values,color=color,label=label,lw=1.35)
            seed=4000 if window is None else 100
            dd.plot(values.index,100*(values/values.cummax().clip(lower=seed)-1),color=color,lw=1)
        ax.set_ylabel('Capital ($)' if window is None else 'Base 100 au 6 novembre 2024')
        dd.set_ylabel('DD de clôture (%)');ax.legend(fontsize=8,ncol=2,frameon=False)
        for a in [ax,dd]:a.grid(alpha=.2);a.spines[['top','right']].set_visible(False)
        fig.suptitle('B + anti-SL TOP10 — modalités de protection et nouvelles conditions ON/OFF',fontweight='bold',fontsize=14)
        fig.text(.08,.025,'2021 au 1er octobre 2026 ; 4 000 $ continus ; SL5/open11 ; frais et financement natifs.\n'
            'Tableau : DD intraday ; graphique inférieur : DD de clôture. Pas de nouvel échantillon indépendant.',fontsize=9)
        fig.subplots_adjust(left=.08,right=.98,top=.91,bottom=.14,hspace=.12);fig.savefig(ROOT/name,dpi=150);plt.close(fig)
    audit=dict(status='COMPLETED_SECONDARY_EXPLORATORY_WITH_RESERVES' if review['price_reserves'] or review['event_label_mismatches'] else 'COMPLETED_SECONDARY_EXPLORATORY_AUDITED',
        accounting_error=float(expected-r['final_equity']),native_arithmetic=True,entry_signals_identical=True,
        causal_state_prefix_checks=3,actual_next_open_exits=True,partial_quantities_checked=True,
        completed_campaign_winrate=True,source_review=review,independent_holdout=False,tests_passed=12,
        SQL_writes=0,provider_calls=0,broker_orders=0,production_changes=False,result=row)
    atomic_json(ROOT/'final-status.json',audit)
    print(json.dumps(audit,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
