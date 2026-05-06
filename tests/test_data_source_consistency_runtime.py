"""Sprint S2 / A-017 + A-023 — télémétrie data_source au runtime.

Vérifie que :
- ``aggregate_data_source_mix`` construit ratios + dominante normalisés.
- ``build_data_source_mix_check`` retourne ``status='warning'`` quand mix
  hétérogène et ``status='ok'`` au-dessus du seuil.
- ``check_data_source_homogeneity`` est défensif (engine cassé →
  ``status='unavailable'``).
- Le screener émet bien ``data_source_mix_check`` dans son run_summary.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.run_summary import (
    DEFAULT_DATA_SOURCE_MIN_DOMINANT_RATIO,
    aggregate_data_source_mix,
    build_data_source_mix_check,
)
from dataIntegrityEngine import data_source_health


def test_aggregate_handles_empty_and_none():
    payload = aggregate_data_source_mix(None)
    assert payload["rows_total"] == 0
    assert payload["dominant_source"] is None
    assert payload["dominant_ratio"] == 0.0


def test_aggregate_normalizes_blank_to_unknown():
    payload = aggregate_data_source_mix({"": 5, "eodhd_eod": 95})
    assert payload["counts"].get("unknown") == 5
    assert payload["counts"].get("eodhd_eod") == 95
    assert payload["dominant_source"] == "eodhd_eod"
    assert payload["dominant_ratio"] == pytest.approx(0.95, abs=1e-6)


def test_build_mix_check_status_ok_when_homogeneous():
    check = build_data_source_mix_check({"eodhd_eod": 99, "alpaca_iex": 1}, min_dominant_ratio=0.95)
    assert check["status"] == "ok"
    assert check["dominant_source"] == "eodhd_eod"
    assert check["min_dominant_ratio"] == 0.95


def test_build_mix_check_status_warning_when_mixed():
    check = build_data_source_mix_check({"eodhd_eod": 60, "alpaca_iex": 40}, min_dominant_ratio=0.95)
    assert check["status"] == "warning"
    assert check["dominant_ratio"] < 0.95


def test_build_mix_check_status_empty_when_no_rows():
    check = build_data_source_mix_check({}, min_dominant_ratio=0.95)
    assert check["status"] == "empty"


def test_check_homogeneity_handles_engine_failure():
    class _BoomEngine:
        def connect(self):
            raise RuntimeError("db down")

    payload = data_source_health.check_data_source_homogeneity(
        _BoomEngine(),  # type: ignore[arg-type]
        min_dominant_ratio=0.95,
    )
    assert payload["status"] == "unavailable"
    assert payload["counts"] == {}
    assert "error" in payload


def test_check_homogeneity_logs_warning_on_mix(caplog):
    caplog.set_level(logging.WARNING, logger=data_source_health.LOGGER.name)
    with patch.object(
        data_source_health,
        "fetch_data_source_counts",
        return_value={"eodhd_eod": 60, "alpaca_iex": 40},
    ):
        payload = data_source_health.check_data_source_homogeneity(
            SimpleNamespace(),  # type: ignore[arg-type]
            min_dominant_ratio=0.95,
        )
    assert payload["status"] == "warning"
    assert any("non homogene" in r.getMessage().lower() or "non homogène" in r.getMessage().lower()
               for r in caplog.records), "Un WARNING dédié A-023 doit être loggé."


def test_default_threshold_is_strict():
    """Le seuil par défaut doit rester >= 90 % pour détecter un mix réel."""
    assert DEFAULT_DATA_SOURCE_MIN_DOMINANT_RATIO >= 0.90


def test_screener_emits_data_source_mix_in_summary():
    """Le screener doit avoir le code émetteur de ``data_source_mix_check``."""
    import inspect

    from screener import stock_screener

    src = inspect.getsource(stock_screener)
    assert "data_source_mix_check" in src
    assert "data_source_mix" in src


def test_selector_emits_data_source_mix_in_summary():
    import inspect

    from selector import alpha_scanner

    src = inspect.getsource(alpha_scanner)
    assert "data_source_mix_check" in src

