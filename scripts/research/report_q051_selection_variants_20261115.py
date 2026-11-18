"""Detailed reusable tables/Markdown from completed frozen selection variants."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from scripts.research.us_q051_selection_variants_20261115 import ROOT,CASES,LABELS,WITNESS,read
from scripts.research.us_concentrated_historical_tapes import atomic_json


def detail(folder,name):
    out=folder/'result';r=read(out/'report.json');t=pd.read_csv(out/'trades.csv')
    marks=pd.read_parquet(out/'equity-5m.parquet');wins=t[t.pnl.gt(0)];losses=t[t.pnl.lt(0)]
    result={k:r[k] for k in ['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct',
        'winners','losers','average_winning_pnl','average_losing_pnl','average_gross_capital',
        'average_gross_equity_ratio','costs','margin_interest']}
    result.update(variant=name,label=LABELS[name],sum_winning_pnl=float(wins.pnl.sum()),
        sum_losing_pnl=float(losses.pnl.sum()),profit_factor=float(wins.pnl.sum()/-losses.pnl.sum()),
        average_winning_return_pct=float(100*wins.return_pct.mean()),
        average_losing_return_pct=float(100*losses.return_pct.mean()),
        average_winning_holding_calendar_days=float(wins.holding_days.mean()),
        average_losing_holding_calendar_days=float(losses.holding_days.mean()),
        symbols_traded=int(t.symbol.nunique()),maximum_gross_capital=float(marks.gross.max()),
        maximum_gross_equity_ratio=float((marks.gross/marks.equity).max()),
        open_positions_final=len(r.get('open_positions',[])),cash_final=float(r['settled_cash'])+float(r['unsettled_cash']),
        gross_final=float(r['gross']))
    v=marks.equity.reset_index(drop=True);dd=v/v.cummax().clip(lower=4000.)-1
    trough=int(dd.idxmin());peak=int(v.iloc[:trough+1].idxmax())
    result.update(peak_time=str(marks.iloc[peak].timestamp),trough_time=str(marks.iloc[trough].timestamp),
        exit_reasons=t.exit_reason.value_counts().to_dict())
    return result


def fr(value,percent=False,integer=False):
    if integer:return f'{int(value):,}'.replace(',',' ')
    return f'{float(value):,.2f}'.replace(',',' ').replace('.',',')+(' %' if percent else '')


def report():
    if read(ROOT/'validation-independent.json')['status']!='PASS':raise ValueError('Independent validation required')
    folders={'REFERENCE':WITNESS,**{k:ROOT/'cases'/k for k in CASES}}
    rows=[detail(folder,name) for name,folder in folders.items()]
    atomic_json(ROOT/'comparison-detailed.json',dict(cases=rows))
    pd.DataFrame([{k:v for k,v in row.items() if k!='exit_reasons'} for row in rows]).to_csv(ROOT/'comparison-detailed.csv',index=False)
    table=['| Mesure | Référence TOP5 / >0,50 | TOP10 / >0,50 | TOP5 / >0,60 |',
           '| --- | ---: | ---: | ---: |']
    specs=[('Capital final valorisé (USD)','final_equity',''),('Rendement cumulé','return_pct','p'),
        ('DD maximal intraday','max_drawdown_pct','p'),('Trades clôturés','closed_lot_trades','i'),
        ('Gagnants','winners','i'),('Perdants','losers','i'),('Taux gagnant','win_pct','p'),
        ('Gains nets cumulés des gagnants (USD)','sum_winning_pnl',''),
        ('Pertes nettes cumulées des perdants (USD)','sum_losing_pnl',''),
        ('Gain moyen gagnant (USD)','average_winning_pnl',''),('Perte moyenne perdant (USD)','average_losing_pnl',''),
        ('Rendement moyen gagnant','average_winning_return_pct','p'),
        ('Rendement moyen perdant','average_losing_return_pct','p'),('Profit factor réalisé','profit_factor',''),
        ('Détention moyenne gagnant (jours calendaires)','average_winning_holding_calendar_days',''),
        ('Détention moyenne perdant (jours calendaires)','average_losing_holding_calendar_days',''),
        ('Sociétés avec trade clôturé','symbols_traded','i'),('Frais simulés (USD)','costs',''),
        ('Intérêts de marge (USD)','margin_interest',''),('Capital engagé moyen (USD)','average_gross_capital',''),
        ('Engagement moyen / capital courant','average_gross_equity_ratio','ratio'),
        ('Capital engagé maximal observé (USD)','maximum_gross_capital',''),
        ('Exposition maximale observée / capital courant','maximum_gross_equity_ratio','ratio'),
        ('Positions ouvertes au cutoff','open_positions_final','i')]
    for label,key,kind in specs:
        values=[fr(row[key]*100 if kind=='ratio' else row[key],percent=kind in ('p','ratio'),integer=kind=='i') for row in rows]
        table.append('| '+label+' | '+' | '.join(values)+' |')
    sections=['## Résultats des variantes — terminés et validés','',
        'Même période du 1 janvier 2021 au 1 octobre 2026, 4 000 USD continus, AUC ≥0,50 inchangée. '
        'SL5/open11, portefeuille et coûts identiques ; seule la sélection diffère.','',*table,'',
        'Les gains/pertes cumulés concernent les trades clôturés. Ils ne correspondent pas à eux seuls '
        'à la variation du capital final, qui inclut les positions encore ouvertes et les coûts associés. '
        'Le profit factor est la somme des gains nets divisée par la valeur absolue des pertes nettes. '
        'Les durées sont des jours calendaires, fractions comprises. Les maxima d’exposition sont observés '
        'après variation des prix ; le plafond 1× agit sur l’admission des achats.','',
        '### Résultats annuels du portefeuille continu','']
    annual=pd.read_csv(ROOT/'annual-comparison.csv')
    for title,key,kind in [('Rendement annuel','return_pct','p'),('DD maximal dans chaque année','max_drawdown_pct','p'),
                           ('Trades clôturés','closed_lot_trades','i'),('Taux gagnant','win_pct','p')]:
        sections.extend(['#### '+title,'','| Année | Référence | TOP10 | Score >0,60 |','| --- | ---: | ---: | ---: |'])
        for year in range(2021,2027):
            values=[fr(annual[annual.variant.eq(name)&annual.year.eq(year)].iloc[0][key],
                percent=kind=='p',integer=kind=='i') for name in folders]
            sections.append('| '+str(year)+(' (jusqu’au 1 octobre)' if year==2026 else '')+' | '+' | '.join(values)+' |')
        sections.append('')
    sections.extend(['Les rendements annuels se composent sans remise à zéro du capital. '
        'Les DD annuels utilisent un pic remis à l’origine de chaque tranche : ils ne remplacent '
        'pas le DD global du portefeuille continu.','',
        '### Courbes de capital et DD aux clôtures','',
        '![Comparaison Q051 — référence et deux variantes](../artifacts/research/us_q051_selection_variants/20261115-v1/capital-comparison.png)','',
        'Le panneau inférieur montre le DD aux clôtures quotidiennes. Le tableau global mesure le DD '
        'sur les valorisations intraday simulées : les profondeurs peuvent donc différer.','',
        '### Contrôles et limites','',
        'Validation indépendante PASS des sélections, configurations, comptabilités, frais, DD, '
        'chronologie J+1/open11 et import IHM. Les 55 tests ciblés de sélection et budget de portefeuille passent. '
        'Couverture 5m partielle et repli OHLC identiques en méthode au témoin. Comparaison exploratoire '
        'sur une période déjà étudiée, univers rétrospectif et classements reconstruits ; aucune garantie prospective. '
        'Aucun entraînement, nouveau Predict, appel fournisseur/LLM, écriture SQL, ordre ou changement de production.',''])
    fragment='\n'.join(sections)
    (ROOT/'comparison-detail-fragment.md').write_text(fragment,encoding='utf-8')
    print(json.dumps([{k:r[k] for k in ['variant','final_equity','return_pct','max_drawdown_pct','win_pct','profit_factor']} for r in rows],ensure_ascii=False))
    return fragment


if __name__=='__main__':report()
