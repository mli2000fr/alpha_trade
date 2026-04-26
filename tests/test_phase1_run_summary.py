"""Tests Phase 1 — helper run_summary transverse (`core/run_summary.py`)."""
from __future__ import annotations

from core.run_summary import (
    IEX_BIAS_KEYS,
    RUN_SUMMARY_SCHEMA_VERSION,
    attach_schema_version,
    merge_iex_bias_counters,
)


def test_attach_schema_version_default() -> None:
    payload = attach_schema_version({"foo": 1})
    assert payload["schema_version"] == RUN_SUMMARY_SCHEMA_VERSION
    assert payload["foo"] == 1


def test_attach_schema_version_preserves_existing() -> None:
    payload = attach_schema_version({"schema_version": 42, "foo": 1})
    assert payload["schema_version"] == 42


def test_attach_schema_version_handles_none() -> None:
    payload = attach_schema_version(None)
    assert payload == {"schema_version": RUN_SUMMARY_SCHEMA_VERSION}


def test_attach_schema_version_idempotent() -> None:
    once = attach_schema_version({"foo": 1})
    twice = attach_schema_version(once)
    assert once == twice


def test_merge_iex_bias_counters_filters_unknown_keys() -> None:
    summary: dict = {"existing": True}
    merge_iex_bias_counters(summary, {
        "symbols_zero_volume_30d": 12,
        "stale_quote_pct": 0.42,
        "unknown_key_should_be_ignored": "x",
    })
    assert summary["symbols_zero_volume_30d"] == 12
    assert summary["stale_quote_pct"] == 0.42
    assert "unknown_key_should_be_ignored" not in summary


def test_merge_iex_bias_counters_skips_none() -> None:
    summary: dict = {}
    merge_iex_bias_counters(summary, {"symbols_zero_volume_30d": None})
    assert summary == {}


def test_merge_iex_bias_counters_noop_on_none() -> None:
    summary: dict = {"x": 1}
    merge_iex_bias_counters(summary, None)
    assert summary == {"x": 1}


def test_iex_bias_keys_contract() -> None:
    # Garde-fou : la liste documentée dans README/audit_global.md
    # ne doit pas dériver sans bump de version explicite.
    assert IEX_BIAS_KEYS == (
        "symbols_zero_volume_30d",
        "stale_quote_pct",
        "stale_market_cap_pct",
    )

