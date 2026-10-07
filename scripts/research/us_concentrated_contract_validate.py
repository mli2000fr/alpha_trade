"""Validate technical contract on synthetic fixtures, version BAND overlay.

No provider request, SQL, model training or historical economic performance.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import pandas as pd

from scripts.research.us_concentrated_contract_audit import dump, frozen_backtest_config


def band_overlay(source, evidence):
    raw_path = Path(evidence)/'BAND_eod.json'
    raw = json.loads(raw_path.read_text(encoding='utf-8'))
    current = next(row for row in raw if row['date'] == '2026-06-18')
    bars = pd.read_parquet(Path(source)/'bars-2026.parquet')
    match = bars[bars.symbol.eq('BAND') & pd.to_datetime(bars.date).eq(pd.Timestamp('2026-06-18'))]
    if len(match) != 1 or float(match.iloc[0].volume) != 0:
        raise ValueError('BAND source no longer matches the reviewed zero-volume case')
    for column in ('open', 'high', 'low', 'close'):
        if abs(float(match.iloc[0][column]) - float(current[column])) > .005:
            raise ValueError('BAND price mismatch: no volume-only overlay allowed')
    if float(current['volume']) <= 0:
        raise ValueError('BAND refreshed volume is not positive')
    return pd.DataFrame([dict(symbol='BAND', date=pd.Timestamp('2026-06-18'),
        original_volume=0, replacement_volume=int(current['volume']),
        provider='eodhd', evidence_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        evidence_observed_at='2026-10-06', kind='RESEARCH_ONLY_VENDOR_CORRECTION',
        historical_pit_certified=False)])


def run(output, source, evidence):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    targets = ['tests/test_execution_contract_cashflows.py',
               'tests/test_concentrated_pipeline_contract.py',
               'tests/test_us_concentrated_contract_audit.py']
    command = [sys.executable, '-m', 'pytest', *targets, '--no-cov', '-o', 'addopts=', '-q',
               '--junitxml', str(output/'tests.xml')]
    test_result = subprocess.run(command, capture_output=True, text=True, errors='replace', check=False)
    (output/'tests.log').write_text(test_result.stdout+test_result.stderr, encoding='utf-8')
    tests = ET.parse(output/'tests.xml').getroot().find('testsuite')
    if tests is None or test_result.returncode != 0 or int(tests.get('failures', '0')) or int(tests.get('errors', '0')):
        dump(output/'report.json', dict(status='FAILED_TECHNICAL_VALIDATION', returncode=test_result.returncode))
        raise RuntimeError('Contract fixtures failed: inspect tests.log')
    overlay = band_overlay(source, evidence)
    overlay.to_parquet(output/'band_volume_overlay.parquet', index=False)
    config = frozen_backtest_config('2025-01-01', '2026-09-30')
    dump(output/'resolved_contract.json', asdict(config))
    paths = ['config.yaml', 'common/trading_costs.py', 'backtesting/simulator.py',
             'risk_management/config.py', 'risk_management/position_sizer.py',
             'risk_management/portfolio_builder.py', 'execution_engine/config.py',
             'execution_engine/order_intents.py', 'backtesting/execution_replay.py',
             'backtesting/execution_lifecycle_replay.py', 'backtesting/protection_watcher_replay.py',
             'backtesting/exit_lifecycle_replay.py', *targets,
             'scripts/research/us_concentrated_contract_audit.py', __file__]
    report = dict(status='TECHNICAL_CONTRACT_VALIDATED_ON_SYNTHETIC_FIXTURES',
        created_at=datetime.now(timezone.utc).isoformat(),
        database_writes=False, historical_economic_replay=False,
        synthetic_cashflow_checks=True, tests_passed=int(tests.get('tests', '0')),
        tests_skipped=int(tests.get('skipped', '0')),
        source_hashes={p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
        resolved_contract_sha256=hashlib.sha256((output/'resolved_contract.json').read_bytes()).hexdigest(),
        band_overlay_sha256=hashlib.sha256((output/'band_volume_overlay.parquet').read_bytes()).hexdigest(),
        band_overlay_rows=len(overlay), production_data_changed=False,
        contract=dict(blockers=[
            'TOP20_PRICE_PATH_AND_HISTORICAL_TRADABILITY_REVIEW_REMAINS',
            'HISTORICAL_TAPES_NOT_YET_ASSEMBLED_OR_COMPARED',
            'SHORT_BORROW_IS_HYPOTHETICAL_NOT_CERTIFIED']),
        scope='Shared pipeline functions on deterministic fixtures, not certification of every live/broker execution path',
        excluded_paths=['tiered commissions', 'force-close defensive/breaker/research overlays',
                        'actual broker fills', 'automatic terminal liquidation'])
    dump(output/'report.json', report)
    print(json.dumps(dict(status=report['status'], tests=report['tests_passed'], overlay_rows=len(overlay))))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source', default='artifacts/research/us_concentrated_replay/prepare-20261006-v1')
    parser.add_argument('--evidence', default='artifacts/research/us_concentrated_replay/qualification-contract-20261006-v2')
    run(**vars(parser.parse_args()))
