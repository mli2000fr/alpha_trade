import json

import pandas as pd
import pytest

from scripts.research.us_concentrated_volume_refresh import qualify
from scripts.research.us_concentrated_live_portfolio import apply_verified_volume_overlay
from scripts.research.us_concentrated_historical_tapes import digest, atomic_json


BASE = dict(open=14.59, high=14.985, low=14.22, close=14.82)


@pytest.mark.parametrize('volume', [0, -1, None, float('nan'), float('inf')])
def test_zero_invalid_or_infinite_vendor_volume_is_not_a_correction(volume):
    assert qualify(BASE, dict(**BASE, volume=volume)) == 'BLOCKED_ZERO_VOLUME_REPRODUCED'


def test_volume_correction_requires_unchanged_ohlc():
    assert qualify(BASE, dict(**BASE, volume=3495268)) == 'VENDOR_VOLUME_CORRECTION_NON_PIT'
    assert qualify(BASE, dict(BASE, close=15., volume=3495268)) == 'BLOCKED_OHLC_DISAGREEMENT'
    assert qualify(BASE, None) == 'BLOCKED_MISSING_PROVIDER_BAR'


def test_verified_overlay_preserves_prices_and_original_archive(tmp_path):
    bars = pd.DataFrame([dict(date=pd.Timestamp('2026-06-18'), symbol='GPRE', volume=0, **BASE)])
    atomic_json(tmp_path/'provider-response.json', [dict(date='2026-06-18', volume=3495268, **BASE)])
    raw_hash = digest(tmp_path/'provider-response.json')
    overlay_path = tmp_path/'volume-overlay.parquet'
    pd.DataFrame([dict(date=pd.Timestamp('2026-06-18'), symbol='GPRE', original_volume=0,
        replacement_volume=3495268, raw_sha256=raw_hash)]).to_parquet(overlay_path, index=False)
    atomic_json(tmp_path/'report.json', dict(status='VENDOR_VOLUME_CORRECTION_NON_PIT',
        symbol='GPRE', date='2026-06-18', original=BASE, refreshed=dict(**BASE, volume=3495268),
        raw_sha256=raw_hash, overlay_sha256=digest(overlay_path)))
    corrected = apply_verified_volume_overlay(bars, overlay_path)
    assert corrected.volume.iloc[0] == 3495268
    assert bars.volume.iloc[0] == 0
    assert corrected[list(BASE)].equals(bars[list(BASE)])
    atomic_json(tmp_path/'provider-response.json', [])
    with pytest.raises(ValueError, match='changed'):
        apply_verified_volume_overlay(bars, overlay_path)
