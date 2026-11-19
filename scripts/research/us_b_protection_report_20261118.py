"""Final diagnostics and readable charts; frozen replays are never changed."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

from scripts.research.us_b_protection_partial_20261118 import ROOT as PRIMARY
from scripts.research.us_b_protection_timing_replay_20261118 import ROOT
from scripts.research.us_b_protection_timing_20261118 import future_targets
from scripts.research.us_q051_b_early_sl_20261116 import FULL
from scripts.research.us_concentrated_historical_tapes import digest, atomic_json


def main():
    for path in [PRIMARY/'final-status.json', ROOT/'final-status.json', ROOT/'exposure-validation.json']:
        if not path.exists():
            raise ValueError('Missing final review: '+str(path))
    curves = pd.read_csv(ROOT/'capital-curves-all.csv', index_col=0, parse_dates=True)
    reference = curves['B + anti-SL témoin']
    targets = future_targets(reference)
    policies = {
        'OLD': pd.read_parquet(PRIMARY/'inputs/OLD-states.parquet'),
        'PROGRESSIVE': pd.read_parquet(PRIMARY/'inputs/PROGRESSIVE-states.parquet'),
        'LOCAL': pd.read_parquet(ROOT/'inputs/states.parquet')}
    rows, events, windows = [], [], []
    for name, state in policies.items():
        for start, end in [('2021-01-01','2023-12-31'), ('2024-01-01','2024-12-31'), ('2025-01-01','2026-09-30')]:
            g = state.loc[start:end].join(targets).dropna(subset=['forward_return10'])
            risk, rebound = g.risk10.eq(True), g.recovery10.eq(True)
            nonnormal = g.phase.ne('NORMAL')
            on = g.transition.eq('ON')
            rows.append(dict(rule=name,start=start,end=end,sessions=len(g),on=int(on.sum()),
                normal_pct=100*g.phase.eq('NORMAL').mean(),probe_pct=100*g.phase.eq('PROBE').mean(),
                protected_pct=100*g.phase.eq('PROTECTED').mean(),
                ON_followed_by_risk10_pct=100*g.loc[on,'risk10'].astype(float).mean(),
                risk10_in_nonnormal_pct=100*nonnormal[risk].mean(),
                rebound10_in_nonnormal_pct=100*nonnormal[rebound].mean()))
        transitions = state.loc['2021-01-01':'2026-09-30']
        for day, row in transitions[transitions.transition.ne('')].iterrows():
            t = targets.reindex([day]).iloc[0]
            events.append(dict(rule=name,date=str(day.date()),transition=row.transition,phase=row.phase,
                               forward_return10=t.forward_return10,forward_min10=t.forward_min10))
    for label, values in curves.items():
        if label == 'SPY prix seuls':
            continue
        for start,end in [('2024-11-06','2025-04-04'),('2024-11-06','2025-06-30'),('2025-07-01','2026-10-01')]:
            w = values.loc[start:end]
            windows.append(dict(label=label,start=start,end=end,return_pct=100*(w.iloc[-1]/w.iloc[0]-1),
                                close_dd_pct=100*(w/w.cummax()-1).min()))
    pd.DataFrame(rows).to_csv(ROOT/'timing-diagnostics-final.csv',index=False)
    pd.DataFrame(events).to_csv(ROOT/'timing-events-final.csv',index=False)
    pd.DataFrame(windows).to_csv(ROOT/'windows-all.csv',index=False)
    annual = pd.read_csv(PRIMARY/'annual-comparison.csv')
    extra = pd.read_csv(ROOT/'cases/HALF_LOCAL_TIMING/result/annual-summary.csv')
    extra['case'] = 'HALF_LOCAL_TIMING'
    pd.concat([annual,extra],ignore_index=True).to_csv(ROOT/'annual-comparison-all.csv',index=False)

    # Volume=0 is screened separately from actual price corruption. Only cached
    # observations are compared, with no replacement or claim of a full session.
    from scripts.research.us_q051_feature_groups_cd_20261116 import ReferencePrices, EXT
    from datetime import date
    tape = ReferencePrices(EXT).day(date(2026,6,18))
    price = {c:pd.read_parquet(FULL/'inputs'/(c+'.parquet')) for c in ['open','high','low','close']}
    evidence = []
    for symbol in ['ALNT','QTWO']:
        g = tape[symbol].sort_values('timestamp')
        daily = {c:float(f.loc['2026-06-18',symbol]) for c,f in price.items()}
        evidence.append(dict(symbol=symbol,date='2026-06-18',daily=daily,cached_5m_bars=len(g),
            cached_volume=int(g.volume.sum()),observed_open=float(g.iloc[0].open),
            observed_high=float(g.high.max()),observed_low=float(g.low.min()),
            last_5m_close=float(g.iloc[-1].close),
            exact_open_match=bool(np.isclose(daily['open'],g.iloc[0].open)),
            full_session_qualified=False))
    atomic_json(ROOT/'volume-screen-review.json',dict(
        status='RESERVE_RETAINED_NO_PRICE_REPLACEMENT',evidence=evidence,
        explanation='Daily volume zero despite positive cached trades. Opening prices corroborated; 68/77 bars are incomplete. No full price certification or optimistic replacement.',
        unqualified_symbols_in_actual_holdings=['ALNT','QTWO'],
        LBRDK_or_GWRE_zero_volume_overlap=False,SQL_reads=0,provider_calls=0,data_changes=0))

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    selected = ['B + anti-SL témoin','Liquidation totale / ancienne sortie',
                'Partie pilotée 50 % / nouvelles conditions locales','SPY prix seuls']
    colors = ['#1d4ed8','#a8a29e','#dc2626','#d97706']
    fig, ax = plt.subplots(figsize=(13,6),facecolor='#f7f9fc')
    for label,color in zip(selected,colors):
        values=curves[label]
        ax.plot(values.index,values,label=f'{label} : {values.iloc[-1]:,.0f} $',color=color,lw=1.6)
    ax.set_ylabel('Capital valorisé ($)');ax.grid(alpha=.2)
    ax.spines[['top','right']].set_visible(False);ax.legend(fontsize=9,frameon=False)
    fig.suptitle('B + anti-SL TOP10 — les nouvelles conditions ne battent pas le témoin',fontweight='bold',fontsize=14)
    fig.text(.08,.02,'2021–1er octobre 2026 ; 4 000 $ ; frais inclus. Résultats exploratoires, intraday partiel et réserves historiques.\n'
             'Protection partielle : base conservée et partie pilotée, pas un plafond strict de 50 % du compte.',fontsize=9)
    fig.subplots_adjust(left=.08,right=.98,bottom=.16,top=.9)
    fig.savefig(ROOT/'capital-summary.png',dpi=150);plt.close(fig)

    fig,(ax,a,b)=plt.subplots(3,1,sharex=True,figsize=(13,7),gridspec_kw={'height_ratios':[3,1,1]},facecolor='#f7f9fc')
    w=reference.loc['2024-11-06':'2025-07-01'];ax.plot(w.index,100*w/w.iloc[0],color='#1d4ed8',label='Témoin virtuel, base 100')
    ax.grid(alpha=.2);ax.legend(frameon=False);ax.set_ylabel('Capital relatif')
    from matplotlib.patches import Patch
    phase_colors={'NORMAL':'#b8e3cc','PROBE':'#f7d68a','PROTECTED':'#f1aaa5'}
    for axis,name,title in [(a,'OLD','Anciennes conditions'),(b,'LOCAL','Nouvelles conditions')]:
        # State at close becomes actionable only on the following session.
        s=policies[name].phase.reindex(reference.index).shift(1).loc[w.index]
        for left,right,phase in zip(w.index[:-1],w.index[1:],s.iloc[:-1]):
            axis.axvspan(left,right,color=phase_colors[phase])
        axis.set_yticks([]);axis.set_ylabel(title.replace(' ','\n',1),fontsize=9,rotation=0,ha='right',va='center')
    b.legend(handles=[Patch(color=c,label=n) for n,c in [('Normal',phase_colors['NORMAL']),('Reprise partielle',phase_colors['PROBE']),('Protection',phase_colors['PROTECTED'])]],
             loc='lower left',bbox_to_anchor=(0,-1.2),ncol=3,frameon=False)
    fig.suptitle('Fin 2024–mi-2025 : moins de retard, mais plusieurs faux départs',fontweight='bold',fontsize=14)
    fig.text(.08,.02,'Phases décalées à la séance d’exécution ; décisions connues à la clôture précédente.\n'
             'Courbe du témoin indépendant des protections ; pas le rendement des portefeuilles protégés.',fontsize=9)
    fig.subplots_adjust(left=.13,right=.98,top=.91,bottom=.21,hspace=.12)
    fig.savefig(ROOT/'activation-recovery-2024-2025.png',dpi=150);plt.close(fig)

    files=[ROOT/'comparison-all.csv',ROOT/'annual-comparison-all.csv',ROOT/'final-status.json',PRIMARY/'final-status.json',
           ROOT/'exposure-validation.json',ROOT/'actual-held-volume-screen.json',ROOT/'volume-screen-review.json',
           ROOT/'timing-diagnostics-final.csv',ROOT/'windows-all.csv']
    atomic_json(ROOT/'completion.json',dict(status='COMPLETED_EXPLORATORY_WITH_RESERVES',
        economic_cases=6,controls_exactly_matched=True,accounting_and_actual_exposure_checked=True,
        outcome='No protected case improves both return and maximum intraday drawdown vs unprotected reference',
        reserves=['Inherited BIDU first-session label discrepancy in each case','ALNT/QTWO daily volume zero on2026-06-18; incomplete cached tape; no price replacement',
                  'Partial intraday/daily fallback, revised prices and contemporary universe; no new independent holdout'],
        production_changes=False,SQL_writes=0,provider_calls=0,broker_orders=0,
        receipts_sha256={str(p):digest(p) for p in files}))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':
    main()
