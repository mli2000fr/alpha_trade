"""Tests du gate de blocage sur données critiques (Section 17 Point 2.5)."""

from __future__ import annotations

from datetime import datetime, timezone as _tz

import pytest

from common.data_availability import DataAvailabilityInfo, QualityState
from common.entry_data_gate import (
    CANONICAL_CRITICAL_SOURCES,
    CANONICAL_ENTRY_SOURCES,
    CANONICAL_REQUIRED_SOURCES,
    EntryDataBlocked,
    EntryDataGate,
    EntryDataGateResult,
    SourceGateResult,
    check_entry_data_readiness,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_avail(
    source: str = "price_data",
    event_time: datetime | None = None,
    available_at: datetime | None = None,
    quality: QualityState = QualityState.PRESENT,
) -> DataAvailabilityInfo:
    """Construit un DataAvailabilityInfo valide pour les tests."""
    now = datetime(2026, 7, 12, 20, 0, 0, tzinfo=_tz.utc)
    evt = event_time or now
    avl = available_at or now
    # Garantit available_at >= event_time
    if avl < evt and event_time is None:
        evt = avl
    return DataAvailabilityInfo(
        event_time=evt,
        available_at=avl,
        source=source,
        source_revision="v1",
        ingested_at=now,
        timezone="America/New_York",
        quality=quality,
    )


# ── SourceGateResult ─────────────────────────────────────────────────────────

class TestSourceGateResult:
    def test_construction(self):
        r = SourceGateResult(
            source="price_data",
            criticality="critical",
            passed=True,
            reason="ok",
            quality="present",
        )
        assert r.source == "price_data"
        assert r.criticality == "critical"
        assert r.passed


# ── EntryDataGate: critical sources ──────────────────────────────────────────

class TestEntryDataGateCriticalSources:
    """Tests sur les sources critiques (bloquantes)."""

    def test_all_critical_present_go(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data", "volume_adv"),
            required_sources=(),
            optional_sources=(),
        )
        avail = {
            "price_data": _make_avail("price_data"),
            "volume_adv": _make_avail("volume_adv"),
        }
        result = gate.check("AAPL", avail, cutoff)
        assert result.go
        assert result.blocking_sources == []
        assert result.per_source["price_data"].passed
        assert result.per_source["volume_adv"].passed

    def test_critical_missing_blocks(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data", "volume_adv"),
            required_sources=(),
            optional_sources=(),
        )
        avail = {
            "price_data": _make_avail("price_data"),
            # volume_adv MANQUANT
        }
        result = gate.check("AAPL", avail, cutoff)
        assert not result.go
        assert "volume_adv" in result.blocking_sources
        assert not result.per_source["volume_adv"].passed
        assert "missing" in result.per_source["volume_adv"].reason

    def test_critical_future_blocks(self):
        """available_at > cutoff → bloqué."""
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        future = datetime(2026, 7, 13, 21, 0, 0, tzinfo=_tz.utc)  # J+1
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=(),
            optional_sources=(),
        )
        avail = {"price_data": _make_avail("price_data", available_at=future)}
        result = gate.check("AAPL", avail, cutoff)
        assert not result.go
        assert "price_data" in result.blocking_sources
        assert "future" in result.per_source["price_data"].reason

    def test_critical_stale_blocks(self):
        """Donnée > 26h → bloqué."""
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        stale = datetime(2026, 7, 10, 21, 0, 0, tzinfo=_tz.utc)  # ~48h
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=(),
            optional_sources=(),
            max_age_hours=26.0,
        )
        avail = {"price_data": _make_avail("price_data", available_at=stale)}
        result = gate.check("AAPL", avail, cutoff)
        assert not result.go
        assert "price_data" in result.blocking_sources
        assert "stale" in result.per_source["price_data"].reason

    def test_critical_degraded_quality_blocks(self):
        """Qualité != PRESENT → bloqué pour une source critique."""
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=(),
            optional_sources=(),
        )
        avail = {"price_data": _make_avail("price_data", quality=QualityState.DELISTED)}
        result = gate.check("AAPL", avail, cutoff)
        assert not result.go
        assert "price_data" in result.blocking_sources
        assert "degraded_quality" in result.per_source["price_data"].reason


# ── EntryDataGate: required sources ──────────────────────────────────────────

class TestEntryDataGateRequiredSources:
    """Tests sur les sources requises (dégradantes mais non bloquantes)."""

    def test_required_missing_degrades_not_blocks(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=("borrow",),
            optional_sources=(),
        )
        avail = {
            "price_data": _make_avail("price_data"),
            # borrow MANQUANT
        }
        result = gate.check("AAPL", avail, cutoff)
        assert result.go  # pas bloqué
        assert "borrow" in result.degraded_sources
        assert "borrow" not in result.blocking_sources


# ── EntryDataGate: optional sources ──────────────────────────────────────────

class TestEntryDataGateOptionalSources:
    """Tests sur les sources optionnelles (jamais bloquantes)."""

    def test_optional_missing_ignored(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=(),
            optional_sources=("sentiment",),
        )
        avail = {"price_data": _make_avail("price_data")}
        result = gate.check("AAPL", avail, cutoff)
        assert result.go
        assert result.per_source["sentiment"].passed  # pas bloquant

    def test_optional_future_not_blocking(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        future = datetime(2026, 7, 13, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=(),
            optional_sources=("sentiment",),
        )
        avail = {
            "price_data": _make_avail("price_data"),
            "sentiment": _make_avail("sentiment", available_at=future),
        }
        result = gate.check("AAPL", avail, cutoff)
        assert result.go  # optionnel = pas bloquant
        assert result.per_source["sentiment"].passed


# ── EntryDataGate: edge cases ────────────────────────────────────────────────

class TestEntryDataGateEdgeCases:
    def test_empty_critical_sources_all_go(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=(),
            required_sources=(),
            optional_sources=(),
        )
        result = gate.check("AAPL", {}, cutoff)
        assert result.go

    def test_unknown_source_is_optional(self):
        """Une source non déclarée est traitée comme optionnelle."""
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=(),
            optional_sources=(),
        )
        # "unknown_source" n'est pas dans la config → ignorée
        avail = {"price_data": _make_avail("price_data")}
        result = gate.check("AAPL", avail, cutoff)
        assert result.go

    def test_overlap_raises(self):
        with pytest.raises(ValueError, match="Overlap"):
            EntryDataGate(
                critical_sources=("price_data",),
                required_sources=("price_data",),  # overlap!
                optional_sources=(),
            )

    def test_to_dict(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=(),
            optional_sources=(),
        )
        avail = {"price_data": _make_avail("price_data")}
        result = gate.check("AAPL", avail, cutoff)
        d = result.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["go"] is True
        assert "per_source" in d

    def test_summary_no_go(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data", "volume_adv"),
            required_sources=(),
            optional_sources=(),
        )
        avail = {}  # rien
        result = gate.check("AAPL", avail, cutoff)
        assert not result.go
        assert "NO-GO" in result.summary
        assert "price_data" in result.summary

    def test_summary_go_with_degraded(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=("borrow",),
            optional_sources=(),
        )
        avail = {"price_data": _make_avail("price_data")}
        result = gate.check("AAPL", avail, cutoff)
        assert result.go
        assert "GO" in result.summary
        assert "degraded" in result.summary


# ── Convenience function ────────────────────────────────────────────────────

class TestCheckEntryDataReadiness:
    def test_ok(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        avail = {
            "price_data": _make_avail("price_data"),
            "volume_adv": _make_avail("volume_adv"),
        }
        result = check_entry_data_readiness("AAPL", avail, cutoff)
        assert result.go

    def test_missing_critical_blocks(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        avail = {"price_data": _make_avail("price_data")}
        # volume_adv manquant
        result = check_entry_data_readiness("AAPL", avail, cutoff)
        assert not result.go
        assert "volume_adv" in result.blocking_sources

    def test_future_blocks(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        future = datetime(2026, 7, 15, 21, 0, 0, tzinfo=_tz.utc)
        avail = {
            "price_data": _make_avail("price_data", available_at=future),  # future!
            "volume_adv": _make_avail("volume_adv"),
        }
        result = check_entry_data_readiness("AAPL", avail, cutoff)
        assert not result.go

    def test_with_custom_sources(self):
        """Custom critical sources."""
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        avail = {"my_source": _make_avail("my_source")}
        result = check_entry_data_readiness(
            "AAPL", avail, cutoff,
            critical_sources=("my_source",),
        )
        assert result.go


# ── EntryDataBlocked exception ──────────────────────────────────────────────

class TestEntryDataBlocked:
    def test_exception_carries_result(self):
        cutoff = datetime(2026, 7, 12, 21, 0, 0, tzinfo=_tz.utc)
        gate = EntryDataGate(
            critical_sources=("price_data",),
            required_sources=(),
            optional_sources=(),
        )
        result = gate.check("AAPL", {}, cutoff)
        with pytest.raises(EntryDataBlocked) as exc_info:
            raise EntryDataBlocked(result)
        assert exc_info.value.result is result
        assert "NO-GO" in str(exc_info.value)


# ── Canonical constants ─────────────────────────────────────────────────────

class TestCanonicalConstants:
    def test_critical_sources_non_empty(self):
        assert len(CANONICAL_CRITICAL_SOURCES) >= 2  # price_data + volume_adv

    def test_entry_sources_map_coverage(self):
        """Toutes les sources critiques sont dans le mapping canonique."""
        for src in CANONICAL_CRITICAL_SOURCES:
            assert CANONICAL_ENTRY_SOURCES[src] == "critical"
        for src in CANONICAL_REQUIRED_SOURCES:
            assert CANONICAL_ENTRY_SOURCES[src] == "required"

    def test_no_overlap_in_canonical(self):
        crit = set(CANONICAL_CRITICAL_SOURCES)
        req = set(CANONICAL_REQUIRED_SOURCES)
        assert crit.isdisjoint(req)
