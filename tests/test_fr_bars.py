from datetime import UTC, datetime

import pytest

from service.fr.bars import FRBarError, normalize_eod_bar


PAYLOAD = {"date": "2026-03-31", "open": 100, "high": 105, "low": 99,
           "close": 103, "volume": 1000, "adjusted_close": 101}
OBSERVED = datetime(2026, 4, 2, 10, tzinfo=UTC)


def test_backfill_is_not_retroactively_pit_and_adjusted_close_stays_separate():
    bar = normalize_eod_bar(PAYLOAD, observed_at=OBSERVED)
    assert bar.available_at == OBSERVED
    assert bar.close_price == 103
    assert bar.provider_adjusted_close == 101
    assert bar.provider_volume_split_adjusted == 1000


def test_fr_bar_rejects_bad_ohlc_and_non_session():
    with pytest.raises(FRBarError, match="OHLC"):
        normalize_eod_bar({**PAYLOAD, "high": 102}, observed_at=OBSERVED)
    with pytest.raises(FRBarError, match="séance XPAR"):
        normalize_eod_bar({**PAYLOAD, "date": "2026-04-03"}, observed_at=OBSERVED)


def test_fr_bar_requires_timezone_and_integer_volume():
    with pytest.raises(FRBarError, match="timezone-aware"):
        normalize_eod_bar(PAYLOAD, observed_at=datetime(2026, 4, 2))
    with pytest.raises(FRBarError, match="volume"):
        normalize_eod_bar({**PAYLOAD, "volume": 1.5}, observed_at=OBSERVED)


def test_fr_bar_uses_later_proven_publication():
    published = datetime(2026, 4, 3, 9, tzinfo=UTC)
    bar = normalize_eod_bar(PAYLOAD, observed_at=OBSERVED, published_at=published)
    assert bar.available_at == published


def test_fr_bar_rejects_eodhd_placeholder_price():
    fake = {**PAYLOAD, "open": 999999.9999, "high": 999999.9999,
            "low": 999999.9999, "close": 999999.9999, "volume": 0}
    with pytest.raises(FRBarError, match="placeholder"):
        normalize_eod_bar(fake, observed_at=OBSERVED)
