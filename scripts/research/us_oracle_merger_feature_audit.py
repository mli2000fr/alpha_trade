"""Local, read-only feature lineage audit; no model fit or new selection."""
import argparse
import json
from pathlib import Path

import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from scripts.research.us_oracle_barrier_comparison import EXTERNAL, freeze_candidates
from scripts.research.us_oracle_merger_replay import provider_frame


def run(source, output):
    columns = ['date', 'symbol', 'daily_return', 'overnight_gap', 'momentum_20',
               'atr_14_norm', 'rolling_volatility_20']
    paths = sorted(EXTERNAL.glob('corrected-features-*.parquet'))
    if not paths:
        raise ValueError('Missing frozen features')
    avb = pd.concat([pd.read_parquet(p, columns=columns, filters=[('symbol', '==', 'AVB')])
                     for p in paths], ignore_index=True).sort_values('date')
    raw = provider_frame(output/'successor-evidence', 'AVB').sort_values('date')
    raw['raw_daily_return'] = raw.close.pct_change(fill_method=None)
    raw['raw_overnight_gap'] = raw.open/raw.close.shift(1)-1
    pairs = avb.merge(raw[['date', 'raw_daily_return', 'raw_overnight_gap']],
                      on='date', validate='one_to_one')
    mismatches = pairs.loc[(pairs.daily_return-pairs.raw_daily_return).abs().gt(.01)
                          | (pairs.overnight_gap-pairs.raw_overnight_gap).abs().gt(.01)]
    scores = pd.read_parquet(source/'scores.parquet')
    selections = []
    for arm in ('OLD_TERMINAL_LONG', 'NEW_BARRIER_LONG'):
        for count in (10, 20, 50):
            chosen = freeze_candidates(scores.loc[scores.date.dt.year.eq(2026)], count, arm)
            chosen = chosen.loc[chosen.symbol.eq('AVB')]
            affected = chosen.loc[chosen.date.between('2026-07-13', '2026-08-14')]
            selections.append(dict(arm=arm, count=count, selected_avb_dates=len(chosen),
                selected_during_mixed_price_basis=len(affected),
                dates_during_mixed_price_basis=[str(d.date()) for d in affected.date]))
    report = dict(status='FEATURE_CONTAMINATION_CONFIRMED', symbol='AVB',
        sql_writes=False, training=False, predictions_recomputed=False,
        frozen_scores_modified=False, source_hashes={str(p): digest(p) for p in paths},
        raw_price_mismatches=mismatches.to_dict(orient='records'), selections=selections,
        price_restoration_only_does_not_restore_model_features=True,
        rolling_features_and_cross_sectional_ranks_potentially_affected=True,
        conclusion='Frozen-score 2026 portfolios are lifecycle scenarios, not corrected-feature predictive validation.')
    atomic_json(output/'feature-lineage-audit.json', report)
    if (output/'report.json').exists():
        replay = json.loads((output/'report.json').read_text(encoding='utf-8'))
        reviewed = dict(replay, lifecycle_report_sha256=digest(output/'report.json'),
            feature_audit_sha256=digest(output/'feature-lineage-audit.json'),
            predictive_validation_passed=False, known_avb_feature_contamination=True,
            status='LIFECYCLE_SCENARIOS_COMPLETED_PREDICTIVE_VALIDATION_NOT_QUALIFIED')
        atomic_json(output/'reviewed-report.json', reviewed)
        notice = ('# Qualification finale du rejeu AVB\n\n'
            '**Pas une validation prédictive 2026 : les scores figés utilisent des features AVB contaminées.**\n\n'
            'La fausse chute de −63,69 % du 13 juillet est un changement d’unité ; '
            'Alpaca donne +1,40 %. Les sélections AVB du nouveau modèle sont donc réservées. '
            'Corriger les prix d’exécution ne corrige pas les features ni les scores.\n\n'
            'Les fractions restent non valorisées ; aucun rendement complet du patrimoine '
            'ni parité courtier n’est certifié. Les tableaux ci-dessous sont uniquement des '
            'scénarios LONG à scores figés. Aucun entraînement ou SQL écrit.\n\n')
        (output/'reviewed-report.md').write_text(notice+(output/'report.md').read_text(encoding='utf-8'),
                                              encoding='utf-8')
    print(report['status'])
    print(mismatches.to_string(index=False))
    print(pd.DataFrame(selections).drop(columns='dates_during_mixed_price_basis').to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.output)
