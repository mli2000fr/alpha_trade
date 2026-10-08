"""Offline FR feature arithmetic/window audit, no model inference or release."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
import json
import math
from pathlib import Path
import statistics

import pandas as pd

from common.market_calendar import get_market_calendar
from modelFactory.fr_feature_panel import compute_symbol_features
from modelFactory.fr_oracle_h5_pilot import feature_matrix
from service.fr.daily_feature_adapter_16b import identity_resolution, observed_payloads, select_bars
from service.fr.prediction_contract_16a import ROOT, FEATURES, aware, prepare_manifest, scoped_path
from service.fr.qualification_dossier_16g import build, read_proof
from service.fr.release_review_check_16g import check


def manual_features(rows):
    """Independent arithmetic implementation for the frozen 14-feature short profile."""
    if len(rows) != 21 or len({str(r['source_session_date']) for r in rows}) != 21:
        raise ValueError('Exactly 21 distinct sessions required')
    if [str(r['source_session_date']) for r in rows] != sorted(str(r['source_session_date']) for r in rows):
        raise ValueError('Chronological rows required')
    for r in rows:
        if any(isinstance(r[k], bool) or not math.isfinite(float(r[k])) or float(r[k]) <= 0
               for k in ('open', 'high', 'low', 'close', 'volume')):
            raise ValueError('Positive finite OHLCV required')
        if float(r['high']) < max(float(r['open']), float(r['close'])) or float(r['low']) > min(float(r['open']), float(r['close'])):
            raise ValueError('Inconsistent OHLC required')
    close = [float(r['close']) for r in rows]
    last = rows[-1]
    returns = [close[i] / close[i-1] - 1 for i in range(1, 21)]
    tr = [max(float(rows[i]['high']) - float(rows[i]['low']),
              abs(float(rows[i]['high']) - close[i-1]),
              abs(float(rows[i]['low']) - close[i-1])) for i in range(1, 21)]
    bottom = min(float(r['low']) for r in rows[1:])
    width = max(float(r['high']) for r in rows[1:]) - bottom
    if width <= 0:
        raise ValueError('Undefined range position')
    result = {f'return_{h}': close[-1] / close[-1-h] - 1 for h in (1, 3, 5, 10, 20)}
    result.update(sma20_distance=close[-1] / statistics.fmean(close[1:]) - 1,
        atr20_pct=statistics.fmean(tr) / close[-1],
        realized_vol20=statistics.stdev(returns) * math.sqrt(252),
        range20_position=(close[-1] - bottom) / width,
        volume_ratio20=float(last['volume']) / statistics.fmean(float(r['volume']) for r in rows[1:]),
        traded_value_mean20_eur=statistics.fmean(float(r['close']) * float(r['volume']) for r in rows[1:]),
        overnight_gap=float(last['open']) / close[-2] - 1,
        intraday_return=close[-1] / float(last['open']) - 1,
        intraday_range=(float(last['high']) - float(last['low'])) / close[-1])
    return {name: result[name] for name in FEATURES}


def parity(rows, sessions, *, compute=compute_symbol_features, transform=feature_matrix):
    if [str(r['source_session_date']) for r in rows] != [str(d) for d in sessions]:
        raise ValueError('Rows differ from required XPAR sessions')
    manual = manual_features(rows)
    frame = compute(pd.DataFrame(rows), sessions)
    actual = {name: float(frame.iloc[-1][name]) for name in FEATURES}
    transformed = transform(pd.DataFrame([actual]))
    if list(transformed.columns) != list(FEATURES):
        raise ValueError('Training transform feature order mismatch')
    expected = dict(manual)
    expected['traded_value_mean20_eur'] = math.log1p(expected['traded_value_mean20_eur'])
    def mismatches(left, right):
        return [name for name in FEATURES if not math.isclose(left[name], right[name], rel_tol=1e-10, abs_tol=1e-10)]
    return {'raw_mismatches': mismatches(actual, manual),
        'transformed_mismatches': mismatches(transformed.iloc[0].to_dict(), expected),
        'manual_raw': manual, 'adapter_raw': actual,
        'training_transformed': {name: float(transformed.iloc[0][name]) for name in FEATURES}}


def run(packet_path, *, root=ROOT):
    root = root.resolve()
    check(packet_path, root=root)
    packet, packet_hash = read_proof(scoped_path(str(packet_path), root))
    confirmation_path = scoped_path(packet['confirmation_report'], root)
    confirmation, _ = read_proof(confirmation_path)
    dossier = build(confirmation_path, root=root)
    manifest = prepare_manifest(root=root)
    if manifest['evidence'] != packet['model_lineage']['evidence']:
        raise ValueError('Model lineage changed since packet')
    calendar = get_market_calendar('FR_EQ', allow_us_weekday_fallback=False)
    cutoff = aware(packet['decision_at'])
    # Use explicit protocol date and verify against the frozen session/cutoff.
    decision_day = date.fromisoformat(confirmation['protocol']['decision_date'])
    if calendar.session(decision_day).open_at_utc != cutoff:
        raise ValueError('Decision differs from XPAR opening')
    feature_day = calendar.previous_session(decision_day)
    sessions = calendar.session_dates(calendar.previous_session(feature_day, 20), feature_day)
    if [str(d) for d in sessions] != confirmation['daily_assembly']['required_sessions']:
        raise ValueError('Frozen window differs from XPAR calendar')
    proofs, payloads = {}, []
    bootstrap = scoped_path(confirmation['protocol']['bootstrap_dir'], root)
    for folder in (root / 'artifacts/fr/operations/eodhd_daily', bootstrap / 'eodhd_daily'):
        selected, errors = observed_payloads(folder, cutoff, root, proofs)
        if errors:
            raise ValueError('Bar archive integrity errors')
        payloads.extend(selected)
    frozen = confirmation['daily_assembly']['proofs_sha256']
    if any(frozen.get(path) != digest for path, digest in proofs.items()):
        raise ValueError('Bar proof absent or changed from frozen confirmation')
    selected = [p for p in dossier['master_proofs'] if p['end'] == dossier['reference_coverage_end']
                and p['observed_at'] == dossier['reference_observed_at']]
    if len(selected) != 1:
        raise ValueError('Exact decision master ambiguous')
    master, _ = read_proof(scoped_path(selected[0]['path'], root))
    identities = {r['provider_symbol']: r for r in manifest['universe']}
    results = []
    for target in packet['matrix']:
        symbol = target['symbol']
        rows, missing = select_bars(payloads, symbol, sessions, calendar, cutoff)
        if missing:
            raise ValueError('Frozen candidate now has missing bars: ' + symbol)
        result = parity(rows, sessions)
        identity = identities[symbol]
        resolutions = [{'session': str(day), **identity_resolution(master, identity, day)} for day in sessions]
        results.append({'symbol': symbol, 'isin': target['isin'], 'mic': target['mic'], **result,
            'reported_identity_compatible_sessions': sum(not r['reasons'] and r['mic'] == target['mic'] for r in resolutions),
            'reported_identity_reserves': [{'session': r['session'], 'reasons': r['reasons']} for r in resolutions if r['reasons']],
            'pre_anchor_sessions': target['feature_identity_sessions_before_anchor'],
            'identity_full_window_independently_qualified': False, 'servable': False})
    passed = sum(not r['raw_mismatches'] and not r['transformed_mismatches'] for r in results)
    return {'schema_version': 1, 'market_code': 'FR_EQ', 'created_at': datetime.now(UTC).isoformat(),
        'packet_sha256': packet_hash, 'decision_at': packet['decision_at'],
        'status': 'FEATURE_ARITHMETIC_PARITY_PASSED_NOT_RELEASED' if passed == len(results) else 'FEATURE_PARITY_RESERVED',
        'candidate_count': len(results), 'parity_passed_count': passed, 'features': list(FEATURES),
        'feature_count': len(FEATURES), 'sessions': [str(d) for d in sessions],
        'relative_tolerance': 1e-10, 'absolute_tolerance': 1e-10,
        'provider_price_correctness_independently_verified': False,
        'model_deserialized': False, 'model_inference_executed': False,
        'feature_arithmetic_is_not_model_release': True, 'bar_proofs_sha256': proofs,
        'master_proof': selected[0], 'matrix': results,
        'remaining_gates': packet['remaining_gates'],
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / 'artifacts/fr/research/feature_parity_16g').resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error('New isolated FR feature parity folder required')
    result = run(args.packet)
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'report.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({key: result[key] for key in ('status', 'candidate_count', 'parity_passed_count', 'feature_count')}))


if __name__ == '__main__':
    main()
