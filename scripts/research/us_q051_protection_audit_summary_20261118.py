"""Summarize frozen warning audits; no threshold selection or portfolio replay."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research import us_q051_protection_feature_audit_20261118 as audit
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT = audit.ROOT


def main():
    outcomes = pd.read_parquet(ROOT / 'future-outcomes.parquet')
    features = pd.read_parquet(ROOT / 'all-audit-features.parquet')
    selected = pd.read_csv(ROOT / 'frozen-selected-features.csv')
    screens = pd.read_csv(ROOT / 'feature-screen-all-years.csv')
    # Keep the originally selected orientations, also for shorter horizons.
    rows = []
    for row in selected.itertuples():
        for horizon in [5, 10, 20]:
            trough = outcomes[f'SL10__trough{horizon}']
            ret = outcomes[f'SL10__return{horizon}']
            label = (trough < -.05) if row.target == 'risk20' else ((ret > 0) & (trough >= -.05))
            label = label.astype(float).where(trough.notna() & ret.notna())
            for year in range(2023, 2027):
                mask = (outcomes.index.year == year) & outcomes[f'SL10__available{horizon}'].lt(pd.Timestamp(year + 1, 1, 1))
                value, n = audit.auc(row.direction * features.loc[mask, row.feature], label.loc[mask])
                rows.append(dict(feature=row.feature, family=row.family, original_target=row.target,
                                 horizon=horizon, year=year, auc=value, days=n, thresholds_refitted=False))
    pd.DataFrame(rows).to_csv(ROOT / 'frozen-feature-horizon-sensitivity.csv', index=False)

    # A controller chosen at end2024 cannot use the last20 decisions whose
    # diagnostic labels mature in2025. Recheck nomination with that purge.
    nomination = []
    validation = outcomes.loc[(outcomes.index.year == 2024) & outcomes.SL10__available20.lt('2025-01-01')]
    for folder, group in [(ROOT, 'raw'), (ROOT / 'adaptive-qualified-v2', 'relative'),
                          (ROOT / 'macro-sensitivity-v1/relative-qualified', 'macro_relative')]:
        for path in sorted(folder.glob('*-timeline.parquet')):
            timeline = pd.read_parquet(path)
            if 'risk' not in timeline:
                continue
            values, _ = audit.rule_metrics(path.stem, timeline[['risk']], timeline, validation)
            record = next(r for r in values if r['family'] == 'SL10' and r['scope'] == '2024')
            record['group'] = group
            record['nomination_passed'] = bool(record['auc'] >= .55 and record['balanced_accuracy'] >= .55
                and record['active_pct'] <= 40 and record['on_events'] >= 2 and record['off_events'] >= 2)
            nomination.append(record)
    pd.DataFrame(nomination).to_csv(ROOT / 'nomination-2024-purged.csv', index=False)

    old = Path('artifacts/research/us_q051_internal_liquidation/20261118-v1/inputs')
    metrics, events = [], []
    for name in ['B_RATE', 'B_SHADOW', 'SL10_RATE', 'SL10_SHADOW']:
        states = pd.read_parquet(old / (name + '-states.parquet')).reindex(outcomes.index)
        # The old policy is a binary alarm; report state discrimination, not a model AUC.
        score = pd.DataFrame({'risk': states.active.astype(float)}, index=outcomes.index)
        a, b = audit.rule_metrics('OLD_' + name, score, states, outcomes)
        metrics.extend(a)
        events.extend(b)
    pd.DataFrame(metrics).to_csv(ROOT / 'old-policy-diagnostic-metrics.csv', index=False)
    pd.DataFrame(events).to_csv(ROOT / 'old-policy-event-outcomes.csv', index=False)

    # Comparable event calendar. Old states are continuous from2021; new rules
    # are initialized OFF in2024. This is a diagnostic, not an economic comparison.
    timing = []
    for folder, prefix in [(old, 'OLD'), (ROOT / 'adaptive-qualified-v2', 'RELATIVE')]:
        paths = [folder / 'SL10_RATE-states.parquet', folder / 'SL10_SHADOW-states.parquet'] if prefix == 'OLD' else sorted(folder.glob('*-timeline.parquet'))
        for path in paths:
            f = pd.read_parquet(path)
            f = f.loc['2024-11-01':'2025-07-31']
            for day, r in f[f.transition.isin(['ON', 'OFF'])].iterrows():
                timing.append(dict(policy=prefix + ':' + path.stem, date=str(day.date()), transition=r.transition))
    pd.DataFrame(timing).to_csv(ROOT / 'late2024-mid2025-event-comparison.csv', index=False)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11})
    table = [
        ('sentinel__risk20_top5', 'risk20', '5 titres : alerte de baisse'),
        ('sentinel__risk20_top10', 'risk20', '10 titres : alerte de baisse'),
        ('sentinel__recovery20_top5', 'recovery20', '5 titres : reprise'),
        ('sentinel__recovery20_top10', 'recovery20', '10 titres : reprise'),
    ]
    values = np.array([screens.loc[screens.feature.eq(f) & screens.target.eq(t), ['auc_' + str(y) for y in range(2021, 2027)]].iloc[0].to_numpy(float) for f, t, _ in table])
    fig, ax = plt.subplots(figsize=(11.5, 4.8), facecolor='#f7f9fc')
    ax.set_facecolor('#f7f9fc')
    im = ax.imshow(values, cmap='RdYlGn', vmin=0.25, vmax=0.9, aspect='auto')
    ax.set_xticks(range(6), ['2021*', '2022*', '2023', '2024', '2025', '2026¹'])
    ax.set_yticks(range(4), [x[2] for x in table])
    for i in range(4):
        for j in range(6):
            ax.text(j, i, f'{values[i, j]:.2f}'.replace('.', ','), ha='center', va='center', fontweight='bold', color='#13233c')
    ax.axvline(1.5, color='#23364e', linewidth=2)
    ax.tick_params(length=0)
    fig.colorbar(im, ax=ax, shrink=.85, label='AUC : 0,50 = absence de classement utile')
    fig.suptitle('Les titres sentinelles perdent leur stabilité après sélection', fontsize=16, fontweight='bold', x=.5, y=.96)
    fig.text(.03, .045, '* Années utilisées pour choisir les titres, leur indicateur et son sens. Liste ensuite figée.\n'
             '¹ Jusqu’au 30 septembre ; dernières observations sans recul suffisant exclues. Cibles : risque / reprise du témoin B + anti-SL à 20 séances.', fontsize=9, color='#475569')
    fig.subplots_adjust(left=.27, right=.92, top=.80, bottom=.22)
    fig.savefig(ROOT / 'sentinel-stability.png', dpi=160)
    plt.close(fig)

    # One declared rule shown for illustration, not a winner selected on2025.
    rule = 'market_internal_account_OFF1'
    new = pd.read_parquet(ROOT / 'adaptive-qualified-v2' / (rule + '-timeline.parquet'))
    original = pd.read_parquet(old / 'SL10_RATE-states.parquet')
    equity = pd.read_csv(audit.SOURCE / 'cases/SL10/result/equity-daily.csv', index_col=0, parse_dates=True).equity
    dates = equity.loc['2024-11-01':'2025-07-31'].index
    fig, axes = plt.subplots(3, 1, figsize=(12, 6.5), sharex=True, gridspec_kw={'height_ratios': [2.3, .7, .7]}, facecolor='#f7f9fc')
    nav = equity.reindex(dates) / equity.reindex(dates).iloc[0] * 100
    axes[0].plot(dates, nav, color='#2356c8', linewidth=1.6)
    axes[0].set_ylabel('Capital témoin\nbase 100')
    for ax, state, label, color in [(axes[1], original, 'Ancien taux', '#e88428'), (axes[2], new, 'Combinaison relative', '#6875a8')]:
        active = state.active.reindex(dates).fillna(False).astype(int)
        ax.fill_between(dates, 0, active, step='post', color=color, alpha=.7)
        ax.set_ylim(0, 1.1)
        ax.set_yticks([0, 1], ['OFF', 'ON'])
        ax.set_ylabel(label, fontsize=9)
    for ax in axes:
        ax.grid(alpha=.18)
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Changer les indicateurs ne résout pas encore le calendrier de protection', fontsize=14, fontweight='bold')
    fig.text(.07, .025, 'Diagnostic de décisions à la clôture, application éventuelle à l’ouverture suivante.\n'
             'Combinaison relative non validée : ce graphique ne représente pas son rendement et ne recommande aucun seuil.', fontsize=9, color='#475569')
    fig.subplots_adjust(left=.18, right=.96, top=.9, bottom=.16, hspace=.15)
    fig.savefig(ROOT / 'warning-timing-diagnostic.png', dpi=160)
    plt.close(fig)

    meta = json.loads((ROOT / 'sql-feature-availability.json').read_text())
    atomic_json(ROOT / 'availability-supplement.json', dict(
        supersedes='external-availability.json macro rows referred only to an older partial cache',
        SQL_tables=len(meta['tables']), SQL_writes=0, provider_calls=0,
        macro=dict(history_rows=len(json.loads((ROOT / 'macro-retrospective-rows.json').read_text())),
                   sensitivity_features=120, retrospective_only=True, certified_vintage_history=False,
                   sensitivity_conclusion=json.loads((ROOT / 'macro-sensitivity-v1/relative-qualified/conclusion.json').read_text())),
        fundamentals=dict(historical_SEC_records_present=True, dedicated_factor_signal_test=False,
                          reason='Need accession/vintage, units, fiscal identity and calculation-price qualification before constructing historical rules'),
        consensus=dict(global_range_unresolved=True, reason='Bounded10s SQL range query failed; no fiscal period substituted for observation date'),
        no_universal_exhaustiveness_claim=True))
    atomic_json(ROOT / 'final-audit-status.json', dict(
        status='COMPLETED_EXPLORATORY_AUDIT_NO_QUALIFIED_CONTROLLER', features_primary=features.shape[1],
        macro_sensitivity_added=120, raw_rule_count=6, qualified_relative_rule_count=4,
        macro_sensitivity_rule_count=4, original_unqualified_relative_rules_excluded=4,
        sentinel_stock_metric_target_tests=28144, production_changes=False, economic_replay=False,
        purged_nomination_rules=len(nomination), purged_nomination_passes=sum(r['nomination_passed'] for r in nomination),
        independent_holdout=False, tests='15 focused tests passed', script_sha256=digest(Path(__file__))))
    print(json.dumps(json.loads((ROOT / 'final-audit-status.json').read_text()), indent=2))


if __name__ == '__main__':
    main()
