"""Offline paired-date uncertainty and calendar/cohort portfolio reporting.

No new model, signal, rule or threshold. Reads an already frozen comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest


def tp_summary(group):
    known = group.long_tp_before_sl.notna()
    successes = int(group.loc[known, 'long_tp_before_sl'].sum())
    unknown = int((~known).sum())
    return dict(selected=len(group), evaluated=int(known.sum()), unknown=unknown,
        tp_rate=successes/int(known.sum()) if known.any() else None,
        tp_lower_all_selected=successes/len(group),
        tp_upper_all_selected=(successes+unknown)/len(group))


def paired_date_interval(old, new, *, repetitions=2000, block=20, seed=12026):
    """Same resampled dates for both arms, preserving 20-session dependence.

    Descriptive finite-sample interval, not a proof of exploitable future alpha.
    Unknown labels retain their actual denominators; bounds are separate.
    """
    def counts(frame):
        temp = frame[['date', 'long_tp_before_sl']].copy()
        temp['known'] = temp.long_tp_before_sl.notna().astype(int)
        temp['successes'] = temp.long_tp_before_sl.fillna(0)
        return temp.groupby('date')[['successes', 'known']].sum()
    a, b = counts(old), counts(new)
    if not a.index.equals(b.index):
        raise ValueError('Unpaired date population')
    n = len(a)
    if n < block or not a.known.sum() or not b.known.sum():
        return None
    rng = np.random.default_rng(seed)
    differences = []
    # Circular moving blocks, same bootstrap dates in both strategies.
    for _ in range(repetitions):
        starts = rng.integers(0, n, size=int(np.ceil(n/block)))
        indices = ((starts[:, None]+np.arange(block)) % n).ravel()[:n]
        old_counts, new_counts = a.to_numpy()[indices].sum(axis=0), b.to_numpy()[indices].sum(axis=0)
        if old_counts[1] and new_counts[1]:
            differences.append(new_counts[0]/new_counts[1]-old_counts[0]/old_counts[1])
    return dict(point_delta=float(b.successes.sum()/b.known.sum()-a.successes.sum()/a.known.sum()),
        lower=float(np.quantile(differences, .025)), upper=float(np.quantile(differences, .975)),
        repetitions=repetitions, block_sessions=block, seed=seed,
        symbol_concentration_not_resampled=True)


def portfolio_periods(daily, year, cutoff, initial_equity=4000.):
    # The last recorded equity at the cutoff is mark-to-market, with open lots
    # still held; it does not invent closing fills/fees at that date.
    period = daily.loc[daily.date.le(pd.Timestamp(cutoff))]
    if period.empty:
        raise ValueError('Empty calendar period')
    curve = pd.concat([pd.Series([initial_equity]), period.equity], ignore_index=True)
    all_curve = pd.concat([pd.Series([initial_equity]), daily.equity], ignore_index=True)
    return dict(year=year, decision_cutoff=cutoff,
        calendar_terminal=str(period.date.iloc[-1].date()),
        calendar_mark_to_market_return=float(curve.iloc[-1]/initial_equity-1),
        calendar_max_drawdown=float((curve/curve.cummax()-1).min()),
        cohort_terminal=str(daily.date.iloc[-1].date()),
        cohort_fully_closed_return=float(all_curve.iloc[-1]/initial_equity-1),
        cohort_max_drawdown=float((all_curve/all_curve.cummax()-1).min()))


def summarize(root):
    root = Path(root)
    report = json.loads((root/'report.json').read_text(encoding='utf-8'))
    if report['status'] == 'PARTIAL_BLOCKED_CORPORATE_ACTION':
        return summarize_remediation(root, report)
    selected = pd.read_parquet(root/'selected-outcomes.parquet')
    candidates = []
    for (year, count), group in selected.groupby([selected.date.dt.year, 'count']):
        old = group.loc[group.arm.eq('OLD_TERMINAL_LONG')]
        new = group.loc[group.arm.eq('NEW_BARRIER_LONG')]
        candidates.append(dict(year=int(year), count=int(count), old=tp_summary(old), new=tp_summary(new),
            paired_date_bootstrap=paired_date_interval(old, new)))
    portfolios = []
    for item in report['portfolios']:
        path = root/f"{item['year']}-TOP{item['count']}-{item['arm']}"
        daily = pd.read_parquet(path/'daily.parquet')
        cutoff = f"{item['year']}-12-31" if item['year'] == 2025 else '2026-09-03'
        portfolios.append(dict(arm=item['arm'], count=item['count'],
            **portfolio_periods(daily, item['year'], cutoff),
            closed_positions=item['closed_positions'], exits=item['exit_reasons'],
            margin_interest=item['margin_interest'], cash_reconciliation_error=item['cash_reconciliation_error']))
    result = dict(status=report['status'], candidates=candidates, portfolios=portfolios,
        failures=report['failures'], source_report_sha256=digest(root/'report.json'),
        inference='descriptive shared archived-input replay; not deployable PIT/borrow certification')
    atomic_json(root/'summary.json', result)
    lines = ['# Comparaison figée — TOP10/20/50', '',
        'Rendements nets du capital, pas taux TP. Selections LONG des deux modèles ;',
        '4 000 USD réinitialisés pour chaque cohorte, mêmes coûts/risque, SL7/TP20, J21 open.', '',
        '| Année | N | Modèle | Rendement à la coupe | DD à la coupe | Cohorte close | DD cohorte | Positions closes |',
        '| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |']
    for row in portfolios:
        values = [row[k]*100 for k in ('calendar_mark_to_market_return', 'calendar_max_drawdown',
                                      'cohort_fully_closed_return', 'cohort_max_drawdown')]
        lines.append(f"| {row['year']} | {row['count']} | {row['arm']} | "
            +' | '.join(f'{x:+.2f} %' for x in values)+f" | {row['closed_positions']} |")
    lines += ['', 'La coupe 2025 est le 31/12 ; celle de 2026 est le 03/09. Les positions',
        'encore détenues sont valorisées, pas liquidées artificiellement. La cohorte',
        'close ajoute la queue des sorties J21, éventuellement dans l’année suivante.',
        'Secteurs actuels/non PIT acceptés ; OHLC ajustés actuels ; macro et screener',
        'non certifiés publication PIT. Aucun signal SHORT promu ni exécuté.', '',
        f"État : {report['status']}. Échecs : {len(report['failures'])}.", '']
    (root/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return result


def summarize_remediation(root, report):
    """Never relabel a marked partial prefix as a fully closed portfolio."""
    prefix = [{key: row[key] for key in ('year', 'count', 'arm', 'decision_cutoff',
        'calendar_terminal', 'calendar_mark_to_market_return', 'calendar_max_drawdown')}
        for row in report['paired_prefix_diagnostic_not_confirmation']]
    for row in prefix:
        row.update(mark_to_market_only=True, fully_closed=False,
                   exploratory_cutoff_chosen_due_to_data_blocker=True)
    result = dict(status=report['status'], completed_runs=report['complete_runs'],
        blocked_runs=len(report['failures']), portfolios=report['summary'],
        paired_partial_prefix=prefix, failures=report['failures'],
        source_report_sha256=digest(root/'report.json'), promotion=False)
    atomic_json(root/'summary.json', result)
    lines = ['# Oracle H20 contre TP avant SL — TOP10/20/50', '',
        '**9 portefeuilles terminés, 3 bloqués par la conversion AVB → VMRK.**',
        'Même capital 4 000 USD, coûts/risque, entrée J+1, SL7/TP20, sortie J21 open.', '',
        '| Année | N | Modèle | À la coupe | DD à la coupe | Cohorte close | DD cohorte |',
        '| --- | ---: | --- | ---: | ---: | ---: | ---: |']
    for row in report['summary']:
        values = [row[k]*100 for k in ('calendar_mark_to_market_return', 'calendar_max_drawdown',
                                      'cohort_fully_closed_return', 'cohort_max_drawdown')]
        lines.append(f"| {row['year']} | {row['count']} | {row['arm']} | "
            +' | '.join(f'{x:+.2f} %' for x in values)+' |')
    lines += ['', 'Coupe 2025 : 31/12. Coupe 2026 : 03/09. Les positions à la coupe sont',
        'valorisées, pas liquidées fictivement ; leur cohorte finit au 30/01/2026',
        'ou au 05/10/2026. Ne pas confondre taux TP et rendement net du capital.', '',
        '## Diagnostic du préfixe commun 2026, au 14 août', '',
        'Ce préfixe a été choisi parce que le replay échoue ensuite sur une fusion.',
        'Il est partiel et les positions sont encore ouvertes ; **ce n’est pas une',
        'confirmation économique sur une nouvelle période préspécifiée**.', '',
        '| N | Modèle | Rendement valorisé au 14/08 | DD |',
        '| ---: | --- | ---: | ---: |']
    for row in prefix:
        lines.append(f"| {row['count']} | {row['arm']} | {row['calendar_mark_to_market_return']*100:+.2f} % | "
                     f"{row['calendar_max_drawdown']*100:+.2f} % |")
    lines += ['', 'Secteurs actuels/non PIT acceptés ; prix ajustés actuels ; disponibilité',
        'macro/screener non certifiée. Aucune promotion ni automatisation SHORT.',
        'La macro finale est omise seulement en cash intégral sans nouvelle entrée ;',
        'AVB reste détenu/inconnu au blocage, sans liquidation ou bar inventé.', '']
    (root/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    summarize(args.source)
