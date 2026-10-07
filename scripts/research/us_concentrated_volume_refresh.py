"""Bounded vendor recheck for a zero-volume bar. Research artifacts only."""
from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
import ssl

import pandas as pd
import requests

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from service.eodhd.clientEodhd import fetch_eod
from service.eodhd.quota import EodhdQuotaTracker


def qualify(original, refreshed):
    if refreshed is None:
        return 'BLOCKED_MISSING_PROVIDER_BAR'
    for column in ('open', 'high', 'low', 'close'):
        value = refreshed.get(column)
        if (value is None or not pd.notna(value) or not math.isfinite(float(value))
                or not math.isfinite(float(original[column]))
                or abs(float(value)-float(original[column])) > .005):
            return 'BLOCKED_OHLC_DISAGREEMENT'
    volume = refreshed.get('volume')
    if volume is None or not pd.notna(volume) or not math.isfinite(float(volume)) or float(volume) <= 0:
        return 'BLOCKED_ZERO_VOLUME_REPRODUCED'
    return 'VENDOR_VOLUME_CORRECTION_NON_PIT'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--date', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('artifacts/research/us_concentrated_replay/prepare-20261006-v1'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    day = pd.Timestamp(args.date)
    bars_path = args.source if args.source.is_file() else args.source/f'bars-{day.year}.parquet'
    bars = pd.read_parquet(bars_path)
    match = bars.loc[bars.symbol.eq(args.symbol) & pd.to_datetime(bars.date).eq(day)]
    if len(match) != 1 or float(match.volume.iloc[0]) != 0:
        raise ValueError('Exactly one original zero-volume bar required')
    original = match.iloc[0].to_dict()
    trust = args.output/'windows-trust.pem'
    trust.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in
        ssl.create_default_context().get_ca_certs(binary_form=True)), encoding='ascii')
    session = requests.Session()
    session.verify = str(trust.resolve())
    tracker = EodhdQuotaTracker(cache_dir=args.output/'provider-quota')
    try:
        payload = fetch_eod(args.symbol, start=(day-pd.Timedelta(days=3)).date().isoformat(),
            end=(day+pd.Timedelta(days=3)).date().isoformat(), session=session, tracker=tracker,
            feature='concentrated_volume_refresh')
    except Exception as exc:
        atomic_json(args.output/'report.json', {'status': 'BLOCKED_PROVIDER', 'error_type': type(exc).__name__})
        raise RuntimeError(f'Provider refresh failed: {type(exc).__name__}') from None
    finally:
        session.close()
    raw = args.output/'provider-response.json'
    atomic_json(raw, payload)
    rows = [r for r in payload if r.get('date') == args.date]
    refreshed = rows[0] if len(rows) == 1 else None
    status = qualify(original, refreshed)
    observed = datetime.now(timezone.utc).isoformat()
    report = dict(status=status, symbol=args.symbol, date=args.date,
        source_path=str(bars_path), source_sha256=digest(bars_path),
        original=original, refreshed=refreshed, raw_sha256=digest(raw),
        observed_at=observed, database_writes=False,
        independent_volume_certification=False, historical_pit_evidence=False)
    if status == 'VENDOR_VOLUME_CORRECTION_NON_PIT':
        overlay = args.output/'volume-overlay.parquet'
        pd.DataFrame([dict(symbol=args.symbol, date=day, original_volume=0.,
            replacement_volume=float(refreshed['volume']), observed_at=observed,
            provider='eodhd', raw_sha256=digest(raw))]).to_parquet(overlay, index=False)
        report['overlay_sha256'] = digest(overlay)
    atomic_json(args.output/'report.json', report)
    print(status)


if __name__ == '__main__':
    main()
