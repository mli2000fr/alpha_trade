"""Read-only coverage gate before any full-parity historical portfolio claim."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqlalchemy import event, text
from database.connection import get_sqlalchemy_engine
from scripts.research.us_extreme50_capture import forbid_writes
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest


def coverage(candidates, snapshots):
    """Count candidate-days with sector evidence actually available at J close."""
    target = candidates[['date', 'symbol']].drop_duplicates().copy()
    target['date'] = pd.to_datetime(target.date).dt.normalize()
    if snapshots.empty:
        return {'candidate_days': len(target), 'qualified_sector_days': 0,
                'missing_sector_days': len(target), 'first_missing': str(target.date.min().date())}
    history = snapshots.copy()
    history['available_at'] = pd.to_datetime(history.available_at)
    history['snapshot_date'] = pd.to_datetime(history.snapshot_date)
    # A later blank sector invalidates the latest evidence: do not search
    # backwards past a newer unknown state to pretend coverage remains valid.
    groups = {s: g.sort_values(['available_at', 'snapshot_date', 'id']) for s, g in history.groupby('symbol')}
    count = 0
    first_missing = None
    for row in target.itertuples(index=False):
        cutoff = (row.date+pd.Timedelta(hours=16)).tz_localize('America/New_York').tz_convert('UTC').tz_localize(None)
        h = groups.get(row.symbol)
        eligible = h[(h.available_at <= cutoff) & (h.snapshot_date <= row.date)] if h is not None else None
        good = eligible is not None and len(eligible) and pd.notna(eligible.iloc[-1].sector) and str(eligible.iloc[-1].sector).strip().lower() not in {'', 'unknown', 'unqualified_pit_sector'}
        count += bool(good)
        if not good and (first_missing is None or row.date < first_missing): first_missing = row.date
    return {'candidate_days': len(target), 'qualified_sector_days': count,
            'missing_sector_days': len(target)-count,
            'first_missing': str(first_missing.date()) if first_missing is not None else None}


def current_sector_coverage(candidates, mapping):
    """Explicit non-PIT substitution; unknown sectors remain blocking."""
    target = candidates[['date', 'symbol']].drop_duplicates().copy()
    values = target.symbol.map(mapping)
    valid = values.notna() & ~values.fillna('').astype(str).str.strip().str.lower().isin(
        {'', 'unknown', 'unqualified_pit_sector'})
    missing = target.loc[~valid]
    return {'candidate_days': len(target), 'qualified_sector_days': int(valid.sum()),
            'missing_sector_days': int((~valid).sum()),
            'first_missing': str(pd.to_datetime(missing.date).min().date()) if len(missing) else None,
            'missing_symbols': sorted(missing.symbol.unique().tolist())}


def run(archive, output, sector_policy='historical_pit'):
    if sector_policy not in {'historical_pit', 'current_explicitly_accepted'}:
        raise ValueError('Unknown sector policy')
    archive, output = Path(archive), Path(output)
    if (output/'report.json').exists(): raise ValueError('Preserve existing preflight evidence')
    output.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_parquet(archive/'candidates.parquet')
    candidates = candidates[candidates.ORACLE_TOP20].copy()
    engine = get_sqlalchemy_engine()
    event.listen(engine, 'before_cursor_execute', forbid_writes)
    try:
        current_mapping = {}
        if sector_policy == 'current_explicitly_accepted':
            from modelFactory.cross_sectional import _load_sector_mapping
            current_mapping = _load_sector_mapping(engine)
        with engine.connect() as conn:
            snapshots = pd.read_sql(text('SELECT id,symbol,snapshot_date,available_at,sector FROM security_master_snapshots WHERE snapshot_date <= :end'), conn, params={'end': '2026-09-30'})
            macro = pd.read_sql(text('SELECT * FROM stock_macro_indicators_daily WHERE trade_date BETWEEN :start AND :end'), conn, params={'start': '2025-01-01', 'end': '2026-09-30'})
            counts = conn.execute(text('SELECT COUNT(*) n, MIN(available_at) first_available, MAX(available_at) last_available FROM security_master_snapshots')).mappings().one()
    finally:
        event.remove(engine, 'before_cursor_execute', forbid_writes)
        engine.dispose()
    snapshots.to_parquet(output/'sector-evidence.parquet', index=False)
    macro.to_parquet(output/'macro-evidence.parquet', index=False)
    if sector_policy == 'current_explicitly_accepted':
        pd.DataFrame(sorted(current_mapping.items()), columns=['symbol', 'sector']).to_parquet(
            output/'current-sector-mapping.parquet', index=False)
        sectors = current_sector_coverage(candidates, current_mapping)
    else:
        sectors = coverage(candidates, snapshots)
    expected = set(pd.to_datetime(candidates.date).dt.date)
    macro_days = set(pd.to_datetime(macro.trade_date).dt.date)
    blockers = []
    if sectors['missing_sector_days']:
        blockers.append('MISSING_CURRENT_SECTORS' if sector_policy == 'current_explicitly_accepted'
                        else 'MISSING_HISTORICAL_PIT_SECTORS')
    if expected-macro_days: blockers.append('MISSING_MACRO_DATES')
    report = {'status': 'BLOCKED_FULL_HISTORICAL_PARITY' if blockers else 'INPUT_COVERAGE_ONLY_NOT_ENGINE_CERTIFICATION',
        'observed_at': datetime.now(timezone.utc).isoformat(), 'selection_policy': 'oracle_pure_long',
        'sector_policy': sector_policy,
        'sector_pit': sector_policy == 'historical_pit',
        'sector_assumption': ('User explicitly accepted current sectors for historical concentration checks; '
                              'not historical PIT evidence' if sector_policy == 'current_explicitly_accepted'
                              else 'Sector evidence available at decision time required'),
        'current_sector_mapping_sha256': digest(output/'current-sector-mapping.parquet') if current_mapping else None,
        'sector_coverage': sectors, 'security_master_range': dict(counts),
        'macro_dates': len(macro_days & expected), 'expected_dates': len(expected),
        'missing_macro_dates': [str(d) for d in sorted(expected-macro_days)],
        'macro_lineage': 'daily table created/updated timestamps are not per-field release/vintage evidence',
        'blockers': blockers, 'database_writes': False, 'training': False,
        'source_hashes': {p: digest(p) for p in ['risk_management/portfolio_builder.py', 'backtesting/risk_bridge.py', 'backtesting/simulator.py']},
        'notes': ['Stateful daily engine integration and execution revalidation still required',
                  'Current-sector substitution only under explicit accepted policy; no neutral macro invented',
                  'No PnL launched by this audit']}
    atomic_json(output/'report.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', default='artifacts/research/us_concentrated_replay/prepare-20261006-v1')
    p.add_argument('--output', required=True)
    p.add_argument('--sector-policy', choices=['historical_pit', 'current_explicitly_accepted'],
                   default='historical_pit')
    print(json.dumps(run(**vars(p.parse_args())), default=str))
