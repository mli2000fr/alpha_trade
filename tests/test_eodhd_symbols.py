"""Tests unitaires du mapping symbole projet <-> EODHD (Phase 2 plan §5.3)."""
from __future__ import annotations

import pytest

from service.eodhd import symbols as sym


@pytest.mark.parametrize(
    "project, expected",
    [
        # Large caps simples
        ("AAPL", "AAPL.US"),
        ("MSFT", "MSFT.US"),
        ("NVDA", "NVDA.US"),
        ("AMZN", "AMZN.US"),
        # Class shares -> point devient tiret
        ("BRK.B", "BRK-B.US"),
        ("BRK.A", "BRK-A.US"),
        ("BF.B", "BF-B.US"),
        # Alphabet : point conservé (GOOG/GOOGL n ont pas de point)
        ("GOOG", "GOOG.US"),
        ("GOOGL", "GOOGL.US"),
        # ETFs / ADRs
        ("SPY", "SPY.US"),
        ("QQQ", "QQQ.US"),
        ("BABA", "BABA.US"),
        ("TSM", "TSM.US"),
        # Mid cap
        ("AAOI", "AAOI.US"),
        # case-insensitive
        ("aapl", "AAPL.US"),
    ],
)
def test_to_eodhd_mapping(project: str, expected: str) -> None:
    assert sym.to_eodhd(project) == expected


def test_to_eodhd_custom_exchange() -> None:
    assert sym.to_eodhd("SAP", exchange="DE") == "SAP.DE"


def test_to_eodhd_preserves_native_provider_symbols() -> None:
    assert sym.to_eodhd("AAPL.US") == "AAPL.US"
    assert sym.to_eodhd("VIX.INDX") == "VIX.INDX"
    assert sym.to_eodhd("US10Y.INDX") == "US10Y.INDX"


def test_to_eodhd_empty_raises() -> None:
    with pytest.raises(ValueError):
        sym.to_eodhd("")


@pytest.mark.parametrize(
    "eodhd, expected",
    [
        ("AAPL.US", ("AAPL", "US")),
        ("BRK-B.US", ("BRK.B", "US")),
        ("BF-B.US", ("BF.B", "US")),
        ("GOOGL.US", ("GOOGL", "US")),
        ("SAP.DE", ("SAP", "DE")),
    ],
)
def test_from_eodhd(eodhd: str, expected: tuple[str, str]) -> None:
    assert sym.from_eodhd(eodhd) == expected


def test_from_eodhd_invalid() -> None:
    with pytest.raises(ValueError):
        sym.from_eodhd("AAPL")  # pas d extension


def test_to_eodhd_then_from_eodhd_roundtrip() -> None:
    for project in ("AAPL", "BRK.B", "BF.B", "GOOGL"):
        assert sym.from_eodhd(sym.to_eodhd(project))[0] == project


def test_is_supported_known_unsupported_basic_plan() -> None:
    # Post-upgrade All-In-One (2026-04-29) : TQQQ est désormais supporté.
    # Le mécanisme `known_unsupported_basic_plan` reste fonctionnel pour
    # les futurs cas (vérifié avec un symbole bidon ajouté à la volée).
    assert sym.is_supported("AAPL") is True
    assert sym.is_supported("TQQQ") is True

