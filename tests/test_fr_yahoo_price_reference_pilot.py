import io
import json
from datetime import date

import pytest

from service.fr.yahoo_price_reference_pilot import (
    chart_url,
    compare,
    fetch_chart,
    normalize_chart,
)


def _payload() -> dict:
    return {
        "chart": {"error": None, "result": [{
            "meta": {"currency": "EUR", "exchangeName": "PAR",
                     "instrumentType": "EQUITY",
                     "exchangeTimezoneName": "Europe/Paris"},
            "timestamp": [1704182400, 1704268800, 1704355200],
            "indicators": {
                "quote": [{
                    "open": [10.0, None, 12.0], "high": [11.0, None, 13.0],
                    "low": [9.0, None, 11.0], "close": [10.5, None, 12.5],
                    "volume": [100, None, 300],
                }],
                "adjclose": [{"adjclose": [10.4, None, 12.5]}],
            },
        }]},
    }


def test_chart_url_has_inclusive_end_via_exclusive_period2() -> None:
    url = chart_url("AIR.PA", date(2024, 1, 1), date(2024, 1, 2))
    assert "AIR.PA" in url
    assert "interval=1d" in url
    assert "period1=1704067200" in url
    assert "period2=1704240000" in url


def test_normalize_chart_skips_incomplete_session() -> None:
    rows, metadata = normalize_chart(_payload())
    assert list(rows) == ["2024-01-02", "2024-01-04"]
    assert rows["2024-01-02"]["close"] == 10.5
    assert rows["2024-01-04"]["volume"] == 300
    assert metadata["currency"] == "EUR"


def test_compare_keeps_price_and_volume_differences_separate() -> None:
    reference, _ = normalize_chart(_payload())
    provider = [
        {"date": "2024-01-02", "open": 10, "high": 11, "low": 9,
         "close": 10.5, "volume": 99},
        {"date": "2024-01-04", "open": 12, "high": 13, "low": 11,
         "close": 12.4, "volume": 300},
    ]
    result = compare(reference, provider, start="2024-01-01", end="2024-01-31")
    assert result["overlap_rows"] == 2
    assert result["price_difference_count"] == 1
    assert result["volume_difference_count"] == 1


def test_fetch_chart_preserves_tls_verification_contract() -> None:
    seen = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, *, context, timeout):
        seen.update({"url": req.full_url, "context": context, "timeout": timeout})
        return Response(json.dumps(_payload()).encode())

    payload = fetch_chart("AIR.PA", date(2024, 1, 1), date(2024, 1, 5),
                          timeout=7, urlopen=fake_urlopen)
    assert payload["chart"]["error"] is None
    assert seen["timeout"] == 7
    assert seen["context"].verify_mode.name == "CERT_REQUIRED"


def test_normalize_chart_rejects_misaligned_arrays() -> None:
    payload = _payload()
    payload["chart"]["result"][0]["indicators"]["quote"][0]["open"] = [10.0]
    with pytest.raises(ValueError, match="longueurs incohérentes"):
        normalize_chart(payload)
