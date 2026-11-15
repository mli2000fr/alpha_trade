"""Export matched classic TOP5/TOP10 economics and capital/drawdown figure."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from scripts.research.us_q051_classic_top10_20261115 import ROOT,read
from scripts.research.report_q051_selection_variants_20261115 import detail,fr
from scripts.research.us_concentrated_historical_tapes import atomic_json


def report():
    if read(ROOT/'validation-independent.json')['status']!='PASS':raise ValueError('Validation required')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[];annual=[];curves=[];fig,(ax,ddax)=plt.subplots(2,1,sharex=True,figsize=(13,9),
        gridspec_kw={'height_ratios':[2,1]})
    for name,alias,label,color in [('CONTROL_TOP5','REFERENCE','Q051 témoin — TOP5','#2455cc'),
                                  ('TOP10','TOP10_SCORE050','Q051 variante — TOP10','#8c44ac')]:
        folder=ROOT/'cases'/name
        row=detail(folder,alias);row.update(variant=name,label=label);rows.append(row)
        a=pd.read_csv(folder/'result/annual-summary.csv');a['variant']=name;annual.append(a)
        e=pd.read_csv(folder/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
        if not np.isclose(4000*np.prod(1+a.return_pct/100),row['final_equity'],atol=1e-6):raise ValueError('Compounding mismatch')
        curves.append(e.rename(name));ax.plot(e.index,e,label=label,color=color)
        ddax.plot(e.index,100*(e/e.cummax().clip(lower=4000)-1),color=color)
    ax.set_title('Q051 simple — TOP10 LONG contre TOP5, sans vol20 ni régime')
    ax.set_ylabel('Capital valorisé ($), départ 4 000');ax.legend();ax.grid(alpha=.2)
    ddax.set_ylabel('DD aux clôtures (%)');ddax.grid(alpha=.2)
    fig.text(.06,.01,'2021–1 octobre 2026. TOP10 % Oracle, score >0,50 / AUC ≥0,50. SL5/open11, achats 1×.\nSans B4/DD15, TP, trailing ou confirmation. Frais inclus. Archives 5m partielles et repli OHLC ; DD du bilan mesuré en intraday.',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1));fig.savefig(ROOT/'capital-comparison.png',dpi=145);plt.close(fig)
    pd.DataFrame([{k:v for k,v in r.items() if k!='exit_reasons'} for r in rows]).to_csv(ROOT/'comparison-detailed.csv',index=False)
    atomic_json(ROOT/'comparison-detailed.json',dict(cases=rows))
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    pd.concat(curves,axis=1).to_csv(ROOT/'capital-curves.csv')
    lines=['## Résultats terminés et validés','',
        '| Mesure | TOP5 témoin reproduit | TOP10 |','| --- | ---: | ---: |']
    fields=[('Capital final valorisé (USD)','final_equity',''),('Rendement cumulé','return_pct','p'),
        ('DD maximal intraday','max_drawdown_pct','p'),('Trades clôturés','closed_lot_trades','i'),
        ('Gagnants','winners','i'),('Perdants','losers','i'),('Taux gagnant','win_pct','p'),
        ('Gains nets cumulés gagnants (USD)','sum_winning_pnl',''),
        ('Pertes nettes cumulées perdants (USD)','sum_losing_pnl',''),
        ('Gain moyen gagnant (USD)','average_winning_pnl',''),('Perte moyenne perdant (USD)','average_losing_pnl',''),
        ('Profit factor réalisé','profit_factor',''),
        ('Détention gagnant (jours calendaires)','average_winning_holding_calendar_days',''),
        ('Détention perdant (jours calendaires)','average_losing_holding_calendar_days',''),
        ('Frais simulés (USD)','costs',''),('Financement de marge (USD)','margin_interest',''),
        ('Capital engagé moyen (USD)','average_gross_capital',''),
        ('Engagement moyen / capital courant','average_gross_equity_ratio','r'),
        ('Capital engagé maximal (USD)','maximum_gross_capital',''),('Positions ouvertes finales','open_positions_final','i')]
    for label,key,kind in fields:
        values=[fr(r[key]*100 if kind=='r' else r[key],percent=kind in ('p','r'),integer=kind=='i') for r in rows]
        lines.append('| '+label+' | '+' | '.join(values)+' |')
    lines.extend(['','Les gains/pertes des trades clôturés ne comprennent pas la valorisation '
        'des positions encore ouvertes. La durée est en jours calendaires.','',
        '### Résultats par année du portefeuille continu',''])
    annual=pd.concat(annual,ignore_index=True)
    for label,col,kind in [('Rendement','return_pct','p'),('DD annuel','max_drawdown_pct','p'),
                           ('Trades clôturés','closed_lot_trades','i'),('Taux gagnant','win_pct','p')]:
        lines.extend(['#### '+label,'','| Année | TOP5 | TOP10 |','| --- | ---: | ---: |'])
        for year in range(2021,2027):
            values=[fr(annual[annual.variant.eq(name)&annual.year.eq(year)].iloc[0][col],
                percent=kind=='p',integer=kind=='i') for name in ['CONTROL_TOP5','TOP10']]
            lines.append('| '+str(year)+(' (au 1 octobre)' if year==2026 else '')+' | '+' | '.join(values)+' |')
        lines.append('')
    lines.extend(['Les rendements annuels se composent ; aucune remise à zéro du capital. '
        'Les DD annuels ont un pic de référence propre à chaque tranche et ne remplacent pas le DD global.','',
        '### Courbes','',
        '![Q051 simple — TOP5 contre TOP10](../../artifacts/research/us_q051_classic_top10/20261115-v1/capital-comparison.png)','',
        'Le panneau inférieur est calculé aux clôtures quotidiennes ; les DD du bilan '
        'utilisent les valorisations intraday simulées.','',
        'Validation indépendante PASS : témoin +206,51 % reproduit, chaque clôture de capital '
        'identique à l’archive ancienne, configurations identiques entre cas, sélection, capital, '
        'frais, P&L, DD, chronologie J+1/open11 et historique IHM. Aucun réglage de production changé.',''])
    (ROOT/'comparison-fragment.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ['variant','final_equity','return_pct','max_drawdown_pct','win_pct']} for r in rows]))


if __name__=='__main__':report()
