"""Offline, retrospective double-AUC screen of two explicit TOP100 definitions."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/research/us_predictable_symbols/20261103-v1'
OUT = ROOT / 'artifacts/research/us_predictable_symbols/20261104-top100-auc060-v1'


def run():
    if OUT.exists():
        raise FileExistsError('A fresh immutable output directory is required')
    validation_path = BASE / 'check-2026-per-symbol.csv'
    validation = pd.read_csv(validation_path, keep_default_na=False)
    inputs = [validation_path, Path(__file__)]
    inputs += [BASE / f'{t}-per-symbol-ranking.csv' for t in ('winner_h10', 'parcours_h20')]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    OUT.mkdir(parents=True)
    report = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        status='COMPLETED_RETROSPECTIVE_SCREEN_NOT_INDEPENDENT_VALIDATION',
        historical_years=[2023, 2024, 2025], check_year=2026, price_asof='2026-11-02',
        rule='Historical nonoverlap AUC > 0.60 AND 2026 nonoverlap AUC > 0.60',
        threshold_precision='Round AUC to 12 decimal places before strict comparison; 0.6000000000000001 equals 0.60, excluded',
        selection_uses_2026_outcomes=True, sources_unchanged=True,
        source_intersections_still_unqualified=True, production_changed=False,
        sql_writes=False, provider_calls=0, new_models=0, orders=0, input_hashes=hashes, cases={})
    for target in ('winner_h10', 'parcours_h20'):
        ranking = pd.read_csv(BASE / f'{target}-per-symbol-ranking.csv', keep_default_na=False)
        assert ranking.symbol.is_unique and ranking['rank'].tolist() == list(range(1, len(ranking)+1))
        versions = {'historical_auc_top100': ranking.sort_values(
            ['auc_nonoverlap', 'symbol'], ascending=[False, True]).head(100),
            'original_reliability_top100': ranking.head(100)}
        v = validation[validation.target.eq(target)][['symbol', 'auc', 'observations']].rename(
            columns={'auc': 'auc_2026_nonoverlap', 'observations': 'observations_2026'})
        for origin, first in versions.items():
            a = first.merge(v, on='symbol', how='left', validate='one_to_one', sort=False)
            a['origin_top100_rank'] = range(1, len(a)+1)
            for column in ('auc_nonoverlap', 'auc_2026_nonoverlap'):
                a[column] = pd.to_numeric(a[column], errors='coerce')
            mask = a.auc_nonoverlap.round(12).gt(.60) & a.auc_2026_nonoverlap.round(12).gt(.60)
            kept = a[mask].copy()
            assert len(a) == 100 and kept.symbol.is_unique
            assert not set(kept.symbol) & {'CHRD', 'WFRD'}
            stem = f'{target}-{origin}-both-auc-gt060'
            kept.to_csv(OUT / f'{stem}.csv', index=False)
            (OUT / f'{stem}.txt').write_text(','.join(kept.symbol) + ('\n' if len(kept) else ''), encoding='utf-8')
            report['cases'][stem] = dict(origin=origin, target=target, original_count=100,
                selected_count=len(kept), symbols=kept.symbol.tolist(),
                observations_2026_min=int(kept.observations_2026.min()) if len(kept) else None,
                observations_2026_max=int(kept.observations_2026.max()) if len(kept) else None,
                excluded_at_exact_060=a.loc[(a.auc_nonoverlap.round(12).eq(.60) |
                    a.auc_2026_nonoverlap.round(12).eq(.60)), 'symbol'].tolist())
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    report['verification'] = 'PASS: source files unchanged; selected names subset of stated TOP100; strict threshold and identity gates preserved'
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for name, case in report['cases'].items():
        print(name, case['selected_count'], ','.join(case['symbols']))


if __name__ == '__main__':
    run()
