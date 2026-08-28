# -*- coding: utf-8 -*-
"""Tests de la colonne `source` sur model_predictions (migration 0067).

Couvre :
- ``insert_predictions`` écrit ``source`` quand présent, NULL sinon (rétro-compat) ;
- ``load_predictions`` renvoie ``source`` et filtre par ``sources`` ;
- ``apply_cascade_to_predictions`` dédoublonne de façon DÉTERMINISTE par source
  (fix contamination per-sector vs global_rank_synth).
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from modelFactory import db_registry
from modelFactory.predictor import apply_cascade_to_predictions


# ---------------------------------------------------------------------------
# insert_predictions — source
# ---------------------------------------------------------------------------

def test_insert_predictions_without_source_stays_null() -> None:
    """Sans colonne `source` dans le DataFrame → pas de param src (rétro-compat)."""
    predictions = pd.DataFrame([
        {
            "symbol": "AAPL",
            "prediction_date": "2026-06-01",
            "predicted_proba": 0.71,
            "predicted_class": 1,
            "run_id": "run-1",
            "selected_model": "lightgbm",
            "decision_threshold": 0.6,
            "signal_label": "long",
            "calibration_method": "platt",
        }
    ])
    captured: dict = {}

    class _FakeConn:
        def execute(self, stmt, params):
            captured["stmt"] = str(stmt)
            captured["params"] = params
            return type("R", (), {"rowcount": 1})()

    class _FakeEngine:
        def begin(self):
            return _Ctx(_FakeConn())

    class _Ctx:
        def __init__(self, conn):
            self._conn = conn

        def __enter__(self):
            return self._conn

        def __exit__(self, *a):
            return False

    inserted = db_registry.insert_predictions(_FakeEngine(), predictions)
    assert inserted == 1
    assert "source" not in captured["stmt"].split("(")[1].split(")")[0] or "source" not in captured["stmt"]
    assert "src" not in captured["params"]


def test_insert_predictions_with_source_persists() -> None:
    predictions = pd.DataFrame([
        {
            "symbol": "AAPL",
            "prediction_date": "2026-06-01",
            "predicted_proba": 0.71,
            "predicted_class": 1,
            "run_id": "run-1",
            "selected_model": "global_ranking_synth",
            "decision_threshold": 0.5,
            "signal_label": "long",
            "calibration_method": "none",
            "predicted_side": "long",
            "proba_long": 0.71,
            "proba_flat": 0.1,
            "proba_short": 0.1,
            "source": "global_rank_synth",
        }
    ])
    captured: dict = {}

    class _FakeConn:
        def execute(self, stmt, params):
            captured["stmt"] = str(stmt)
            captured["params"] = params
            return type("R", (), {"rowcount": 1})()

    class _FakeEngine:
        def begin(self):
            return _Ctx(_FakeConn())

    class _Ctx:
        def __init__(self, conn):
            self._conn = conn

        def __enter__(self):
            return self._conn

        def __exit__(self, *a):
            return False

    inserted = db_registry.insert_predictions(_FakeEngine(), predictions)
    assert inserted == 1
    assert "source" in captured["stmt"]
    assert captured["params"]["src"] == "global_rank_synth"


# ---------------------------------------------------------------------------
# apply_cascade_to_predictions — dédup déterministe par source
# ---------------------------------------------------------------------------

def _fake_cascade_select(date_str, batch_id, pred_dict, **kw):
    return [(s, s, p.long_prob - p.short_prob) for s, p in pred_dict.items()]


@pytest.fixture()
def _cascade_stubs():
    cfg = {"top_pct": 0.1, "min_prob_classification": 0.1, "min_prob_regression": 0.1}
    with patch("modelFactory.predictor.load_cascade_config", lambda: cfg), \
         patch("modelFactory.predictor.cascade_select", _fake_cascade_select):
        yield


def test_cascade_dedup_prefers_global_rank_synth_over_per_sector(_cascade_stubs) -> None:
    """Mode ml : per_sector ne doit JAMAIS écraser global_rank_synth (fix contamination)."""
    preds = pd.DataFrame([
        {"symbol": "AAPL", "trade_date": pd.Timestamp("2026-01-02"), "predicted_side": "long",
         "proba_long": 0.8, "proba_short": 0.1, "proba_flat": 0.1, "source": "global_rank_synth", "run_id": "b1"},
        {"symbol": "AAPL", "trade_date": pd.Timestamp("2026-01-02"), "predicted_side": "short",
         "proba_long": 0.0, "proba_short": 0.3, "proba_flat": 0.0, "source": "per_sector", "run_id": "b2_sector"},
    ])
    out = apply_cascade_to_predictions(preds.copy(), "batch-x")
    aapl = out[out["symbol"] == "AAPL"]
    assert len(aapl) == 1
    assert aapl.iloc[0]["source"] == "global_rank_synth"
    assert aapl.iloc[0]["predicted_side"] == "long"


def test_cascade_dedup_prefers_oracle_synth_in_oracle_mode(_cascade_stubs) -> None:
    preds = pd.DataFrame([
        {"symbol": "AAPL", "trade_date": pd.Timestamp("2026-01-02"), "predicted_side": "long",
         "proba_long": 0.8, "proba_short": 0.1, "proba_flat": 0.1, "source": "global_rank_synth", "run_id": "b1"},
        {"symbol": "AAPL", "trade_date": pd.Timestamp("2026-01-02"), "predicted_side": "short",
         "proba_long": 0.0, "proba_short": 0.4, "proba_flat": 0.0, "source": "oracle_synth", "run_id": "b2"},
    ])
    out = apply_cascade_to_predictions(preds.copy(), "batch-x", rank_mode="extreme_gate")
    aapl = out[out["symbol"] == "AAPL"]
    assert len(aapl) == 1
    assert aapl.iloc[0]["source"] == "oracle_synth"


def test_cascade_no_dedup_without_source_column(_cascade_stubs) -> None:
    """Rétro-compat : pas de colonne source → comportement inchangé (pas de dédup)."""
    preds = pd.DataFrame([
        {"symbol": "AAPL", "trade_date": pd.Timestamp("2026-01-02"), "predicted_side": "long",
         "proba_long": 0.8, "proba_short": 0.1, "proba_flat": 0.1, "run_id": "b1"},
        {"symbol": "AAPL", "trade_date": pd.Timestamp("2026-01-02"), "predicted_side": "short",
         "proba_long": 0.0, "proba_short": 0.3, "proba_flat": 0.0, "run_id": "b2_sector"},
    ])
    out = apply_cascade_to_predictions(preds.copy(), "batch-x")
    assert len(out[out["symbol"] == "AAPL"]) == 2
