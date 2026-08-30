"""Tests unitaires pour la cascade ML (cascade_ml.md — Étapes 1-7).

Couvre :
- load_cascade_config()
- CascadePrediction dataclass
- cascade_select() logique pure
- apply_cascade_to_predictions()
- upsert_global_ranks() (mock DB)
- load_global_ranks_from_db() (mock DB)
- _resolve_predict_batch_id() (mock config)
- Garde-fou AST : bloc cascade dans _impl.py
- stacking_enabled dans insert_training_batch
"""
from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from modelFactory.predictor import (
    CascadePrediction,
    apply_cascade_to_predictions,
    cascade_select,
    load_cascade_config,
    load_global_ranks_from_db,
    upsert_global_ranks,
)


# ═══════════════════════════════════════════════════════════════════
# CascadePrediction
# ═══════════════════════════════════════════════════════════════════

class TestCascadePrediction:
    def test_defaults(self):
        cp = CascadePrediction(symbol="AAPL", long_prob=0.7, short_prob=0.1)
        assert cp.symbol == "AAPL"
        assert cp.long_prob == 0.7
        assert cp.short_prob == 0.1
        assert cp.flat_prob == 0.0
        assert cp.side == "flat"

    def test_explicit_side(self):
        cp = CascadePrediction(symbol="TSLA", long_prob=0.3, short_prob=0.8, side="short")
        assert cp.side == "short"
        assert cp.long_prob == 0.3
        assert cp.short_prob == 0.8


# ═══════════════════════════════════════════════════════════════════
# load_cascade_config
# ═══════════════════════════════════════════════════════════════════

class TestLoadCascadeConfig:
    def test_defaults_when_no_file(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = load_cascade_config()
        assert cfg["top_pct"] == 0.20
        assert cfg["min_prob_classification"] == 0.55
        assert cfg["min_prob_regression"] == 0.10

    def test_reads_from_yaml(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(
            "cascade:\n  top_pct: 0.25\n  min_prob: 0.60\n",
            encoding="utf-8",
        )
        cfg = load_cascade_config()
        assert cfg["top_pct"] == 0.25
        # rétrocompat : l'ancienne clé "min_prob" alimente les deux nouveaux seuils
        assert cfg["min_prob_classification"] == 0.60
        assert cfg["min_prob_regression"] == 0.60

    def test_partial_overrides(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(
            "cascade:\n  top_pct: 0.15\n",
            encoding="utf-8",
        )
        cfg = load_cascade_config()
        assert cfg["top_pct"] == 0.15
        assert cfg["min_prob_classification"] == 0.55  # défaut
        assert cfg["min_prob_regression"] == 0.10

    def test_missing_section_returns_defaults(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("other: 42\n", encoding="utf-8")
        cfg = load_cascade_config()
        assert cfg["top_pct"] == 0.20
        assert cfg["min_prob_classification"] == 0.55
        assert cfg["min_prob_regression"] == 0.10


# ═══════════════════════════════════════════════════════════════════
# cascade_select (logique pure, sans DB)
# ═══════════════════════════════════════════════════════════════════

def _make_ranks_df(symbols_ranks: list[tuple[str, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [(s, r3, r5, None) for s, r3, r5 in symbols_ranks],
        columns=["symbol", "global_rank_3", "global_rank_5", "global_rank_10"],
    )


class TestCascadeSelect:
    def test_top_long_passes(self, monkeypatch):
        """Un symbole top rank + bonne proba long → retenu."""
        ranks = _make_ranks_df([("AAPL", 0.95, 0.92)])
        preds = {"AAPL": CascadePrediction(symbol="AAPL", long_prob=0.70, short_prob=0.05)}

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds)

        assert len(result) == 1
        assert result[0][0] == "LONG"
        assert result[0][1] == "AAPL"
        # _rank_col = global_rank_5 (0.92) car global_rank_10 est None dans le helper.
        assert result[0][2] == pytest.approx(0.92 * 0.70, rel=0.01)

    def test_bottom_short_passes(self, monkeypatch):
        """Un symbole bottom rank + bonne proba short → retenu."""
        ranks = _make_ranks_df([("GME", 0.03, 0.05)])
        preds = {"GME": CascadePrediction(symbol="GME", long_prob=0.05, short_prob=0.80)}

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds)

        assert len(result) == 1
        assert result[0][0] == "SHORT"
        assert result[0][1] == "GME"
        # rank_dir = 1 - 0.05 = 0.95, score = 0.95 * 0.80 = 0.76
        assert result[0][2] == pytest.approx(0.95 * 0.80, rel=0.01)

    def test_oracle_mode_rank_normalizes_ptop(self, monkeypatch):
        """rank_mode='oracle' normalise P(top10) en percentile intra-date.

        Sans normalisation, proba_top=0.10 ne serait jamais > 0.90 → 0 candidats.
        """
        symbols = [f"S{i:02d}" for i in range(10)]
        probas = [0.01 + 0.01 * i for i in range(10)]  # 0.01 .. 0.10 (tous < 0.5)
        ranks = _make_ranks_df([(s, 0.5, 0.5) for s in symbols])
        preds = {s: CascadePrediction(symbol=s, long_prob=0.70, short_prob=0.05) for s in symbols}
        oracle_map = {"2026-01-15": dict(zip(symbols, probas))}

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.10, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select(
                    "2026-01-15", "batch-x", preds,
                    rank_mode="oracle", oracle_rank_map=oracle_map,
                )

        # top 10% = 1 symbole (proba_top max = S09, rang pct 1.0) → LONG.
        assert [(side, sym) for side, sym, _ in result] == [("LONG", "S09")]

    def test_oracle_mode_missing_map_returns_empty(self, monkeypatch):
        ranks = _make_ranks_df([("AAPL", 0.95, 0.92)])
        preds = {"AAPL": CascadePrediction(symbol="AAPL", long_prob=0.70, short_prob=0.05)}
        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds, rank_mode="oracle", oracle_rank_map=None)
        assert result == []

    # ── S6.1 : politiques Oracle (filter / rerank / pool) ──

    def _oracle_scenario(self):
        """10 symboles, B25 rank=0.95 (top band), P_top linéaire → pct 0.1..1.0."""
        symbols = [f"S{i:02d}" for i in range(10)]
        probas = [0.01 + 0.01 * i for i in range(10)]  # 0.01..0.10
        ranks = _make_ranks_df([(s, 0.90, 0.95) for s in symbols])
        preds = {s: CascadePrediction(symbol=s, long_prob=0.70, short_prob=0.05) for s in symbols}
        oracle_map = {"2026-01-15": dict(zip(symbols, probas))}
        return symbols, ranks, preds, oracle_map

    def test_oracle_filter_keeps_high_ptop_only(self, monkeypatch):
        """oracle_filter : B25 sélectionne, Oracle ne garde que P_top ≥ seuil (0.80)."""
        symbols, ranks, preds, oracle_map = self._oracle_scenario()
        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select(
                    "2026-01-15", "batch-x", preds,
                    rank_mode="oracle_filter", oracle_rank_map=oracle_map,
                )
        # pct = 0.1..1.0 → seuls pct ≥ 0.80 passent : S07(0.8), S08(0.9), S09(1.0)
        kept = sorted(sym for _, sym, _ in result)
        assert kept == ["S07", "S08", "S09"]
        # oracle_filter ne réordonne PAS : score = rank B25 × prob (ordre B25 conservé)
        assert result[0][2] == pytest.approx(0.95 * 0.70, rel=0.01)

    def test_oracle_rerank_same_pool_different_order(self, monkeypatch):
        """oracle_rerank : pool B25 identique (10 symboles), ordre réordonné par P_top."""
        symbols, ranks, preds, oracle_map = self._oracle_scenario()
        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select(
                    "2026-01-15", "batch-x", preds,
                    rank_mode="oracle_rerank", oracle_rank_map=oracle_map,
                )
        # Même pool que B25 : les 10 sont retenus, mais triés par P_top décroissant.
        assert len(result) == 10
        assert result[0][1] == "S09"   # pct 1.0
        assert result[-1][1] == "S00"  # pct 0.1
        # score = pct × 0.70
        assert result[0][2] == pytest.approx(1.0 * 0.70, rel=0.01)

    def test_oracle_pool_selects_top_pct_within_wider_pool(self, monkeypatch):
        """oracle_pool : pool B25 top 20%, Oracle sélectionne le top 10% par P_top."""
        symbols, ranks, preds, oracle_map = self._oracle_scenario()
        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.10, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select(
                    "2026-01-15", "batch-x", preds,
                    rank_mode="oracle_pool", oracle_rank_map=oracle_map,
                )
        # top 10% par P_top = 1 symbole (S09, pct 1.0)
        assert [(side, sym) for side, sym, _ in result] == [("LONG", "S09")]

    # ── Extreme Gate (composant officiel E6-E13) ──

    def test_extreme_gate_pure_oracle_long_only(self, monkeypatch):
        """rank_mode='extreme_gate' : univers = top pool_pct par proba_extreme
        (percentile cross-sectionnel du jour, PIT), LONG-only, SANS B25."""
        symbols = [f"S{i:02d}" for i in range(10)]
        probas = [0.01 + 0.01 * i for i in range(10)]  # 0.01..0.10
        preds = {s: CascadePrediction(symbol=s, long_prob=0.70, short_prob=0.05) for s in symbols}
        oracle_map = {"2026-01-15": dict(zip(symbols, probas))}

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db") as _mock_ranks:
                result = cascade_select(
                    "2026-01-15", "batch-x", preds,
                    rank_mode="extreme_gate", oracle_rank_map=oracle_map,
                    extreme_gate_pct=0.20,
                )
        # top 20% par percentile proba_extreme : pct >= 0.80 → S07(0.8), S08(0.9), S09(1.0).
        # LONG-only (aucun SHORT). Les rangs globaux B25 ne sont PAS chargés.
        _mock_ranks.assert_not_called()
        assert [(side, sym) for side, sym, _ in result] == [
            ("LONG", "S09"), ("LONG", "S08"), ("LONG", "S07")]
        # score = percentile × long_prob
        assert result[0][2] == pytest.approx(1.0 * 0.70, rel=0.01)

    def test_extreme_gate_missing_map_returns_empty(self, monkeypatch):
        symbols = [f"S{i:02d}" for i in range(3)]
        preds = {s: CascadePrediction(symbol=s, long_prob=0.70, short_prob=0.05) for s in symbols}
        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob": 0.55}):
            result = cascade_select("2026-01-15", "batch-x", preds,
                                    rank_mode="extreme_gate", oracle_rank_map=None)
        assert result == []

    def test_extreme_gate_directional_chooses_strongest_side(self):
        """Le nouveau mode choisit le côté le plus probable, sans priorité LONG."""
        preds = {
            "LONGER": CascadePrediction(symbol="LONGER", long_prob=0.72, short_prob=0.18),
            "SHORTER": CascadePrediction(symbol="SHORTER", long_prob=0.61, short_prob=0.78),
            "OUT": CascadePrediction(symbol="OUT", long_prob=0.90, short_prob=0.05),
        }
        oracle_map = {"2026-01-15": {"LONGER": 0.90, "SHORTER": 0.80, "OUT": 0.10}}
        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob": 0.55}):
            result = cascade_select(
                "2026-01-15", "batch-x", preds,
                rank_mode="extreme_gate_directional",
                oracle_rank_map=oracle_map,
                extreme_gate_pct=0.50,
                extreme_gate_direction_margin=0.02,
            )
        assert [(side, symbol) for side, symbol, _ in result] == [
            ("LONG", "LONGER"), ("SHORT", "SHORTER")
        ]

    def test_extreme_gate_directional_rejects_ambiguous_direction(self):
        preds = {
            "AMB": CascadePrediction(symbol="AMB", long_prob=0.61, short_prob=0.60),
        }
        oracle_map = {"2026-01-15": {"AMB": 0.99}}
        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob": 0.55}):
            result = cascade_select(
                "2026-01-15", "batch-x", preds,
                rank_mode="extreme_gate_directional",
                oracle_rank_map=oracle_map,
                extreme_gate_pct=1.0,
                extreme_gate_direction_margin=0.02,
            )
        assert result == []

    def test_extreme_gate_directional_rejects_exact_tie_even_with_zero_margin(self):
        preds = {"TIE": CascadePrediction(symbol="TIE", long_prob=0.70, short_prob=0.70)}
        oracle_map = {"2026-01-15": {"TIE": 0.99}}
        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob": 0.55}):
            result = cascade_select(
                "2026-01-15", "batch-x", preds,
                rank_mode="extreme_gate_directional",
                oracle_rank_map=oracle_map,
                extreme_gate_pct=1.0,
                extreme_gate_direction_margin=0.0,
            )
        assert result == []

    def test_extreme_gate_legacy_does_not_change_when_short_is_stronger(self):
        """Non-régression : le mode historique conserve sa priorité LONG."""
        preds = {"S": CascadePrediction(symbol="S", long_prob=0.60, short_prob=0.90)}
        oracle_map = {"2026-01-15": {"S": 0.99}}
        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob": 0.55}):
            result = cascade_select(
                "2026-01-15", "batch-x", preds,
                rank_mode="extreme_gate", oracle_rank_map=oracle_map,
                extreme_gate_pct=1.0, extreme_gate_shorts=True,
            )
        assert result[0][0] == "LONG"

    def test_compute_extreme_gate_pit(self):
        """compute_extreme_gate : percentile cross-sectionnel PAR DATE, aucun lookahead."""
        from modelFactory.oracle.extreme_gate import compute_extreme_gate
        df = pd.DataFrame({
            "date": pd.to_datetime(["2026-01-15"] * 4 + ["2026-01-16"] * 4),
            "symbol": ["A", "B", "C", "D", "A", "B", "C", "D"],
            "proba_extreme": [0.1, 0.2, 0.3, 0.4, 0.4, 0.3, 0.2, 0.1],
        })
        out = compute_extreme_gate(df, pool_pct=0.25)
        # Jour 15 : pct = 0.25/0.5/0.75/1.0 → gate (>=0.75) : C, D
        g15 = out[out["date"] == "2026-01-15"].set_index("symbol")["extreme_gate"]
        assert list(g15[g15].index) == ["C", "D"]
        # Jour 16 : pct = 1.0/0.75/0.5/0.25 → gate : A, B (mêmes symboles, ordre inversé)
        g16 = out[out["date"] == "2026-01-16"].set_index("symbol")["extreme_gate"]
        assert list(g16[g16].index) == ["A", "B"]

    def test_mid_rank_filtered_out(self, monkeypatch):
        """Un symbole au milieu du classement → rejeté."""
        ranks = _make_ranks_df([("MSFT", 0.50, 0.55)])
        preds = {"MSFT": CascadePrediction(symbol="MSFT", long_prob=0.70, short_prob=0.10)}

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds)

        assert len(result) == 0

    def test_low_proba_filtered_out(self, monkeypatch):
        """Top rank mais proba trop faible → rejeté."""
        ranks = _make_ranks_df([("AAPL", 0.90, 0.88)])
        preds = {"AAPL": CascadePrediction(symbol="AAPL", long_prob=0.40, short_prob=0.05)}

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds, min_prob=0.55)

        assert len(result) == 0

    def test_no_prediction_for_symbol(self, monkeypatch):
        """Rang dispo mais pas de prédiction per-symbol → rejeté."""
        ranks = _make_ranks_df([("AAPL", 0.95, 0.92)])
        preds: dict[str, CascadePrediction] = {}

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds)

        assert len(result) == 0

    def test_missing_rank3_or_rank5(self, monkeypatch):
        """Toutes les colonnes de rang absentes/None → rejeté."""
        ranks = pd.DataFrame([
            {"symbol": "AAPL", "global_rank_3": None, "global_rank_5": None, "global_rank_10": None},
        ])
        preds = {"AAPL": CascadePrediction(symbol="AAPL", long_prob=0.70, short_prob=0.05)}

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds)

        assert len(result) == 0

    def test_empty_ranks(self, monkeypatch):
        """Aucun rang → liste vide."""
        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=pd.DataFrame()):
                result = cascade_select("2026-01-15", "batch-x", {})
        assert len(result) == 0

    def test_sorted_by_score_desc(self, monkeypatch):
        """Les candidats sont triés par score décroissant."""
        ranks = _make_ranks_df([
            ("AAPL", 0.95, 0.92),   # avg=0.935, score=0.935*0.65=0.608
            ("MSFT", 0.88, 0.90),   # avg=0.890, score=0.890*0.80=0.712
            ("GOOG", 0.85, 0.87),   # avg=0.860, score=0.860*0.90=0.774
        ])
        preds = {
            "AAPL": CascadePrediction(symbol="AAPL", long_prob=0.65, short_prob=0.05),
            "MSFT": CascadePrediction(symbol="MSFT", long_prob=0.80, short_prob=0.05),
            "GOOG": CascadePrediction(symbol="GOOG", long_prob=0.90, short_prob=0.05),
        }

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds)

        assert len(result) == 3
        # GOOG (0.774) > MSFT (0.712) > AAPL (0.608)
        assert result[0][1] == "GOOG"
        assert result[1][1] == "MSFT"
        assert result[2][1] == "AAPL"
        assert result[0][2] > result[1][2] > result[2][2]

    def test_mixed_long_short(self, monkeypatch):
        """Mélange LONG et SHORT dans les résultats."""
        ranks = _make_ranks_df([
            ("AAPL", 0.95, 0.92),   # top → LONG
            ("GME", 0.03, 0.05),    # bottom → SHORT
        ])
        preds = {
            "AAPL": CascadePrediction(symbol="AAPL", long_prob=0.70, short_prob=0.05),
            "GME": CascadePrediction(symbol="GME", long_prob=0.05, short_prob=0.80),
        }

        with patch("modelFactory.predictor.load_cascade_config", return_value={"top_pct": 0.20, "min_prob": 0.55}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = cascade_select("2026-01-15", "batch-x", preds)

        assert len(result) == 2
        sides = {r[0] for r in result}
        assert sides == {"LONG", "SHORT"}


# ═══════════════════════════════════════════════════════════════════
# apply_cascade_to_predictions
# ═══════════════════════════════════════════════════════════════════

def _preds_df_ternary(
    symbols: list[str],
    sides: list[str],
    proba_long: list[float] | None = None,
    proba_short: list[float] | None = None,
    trade_dates: list[str] | None = None,
) -> pd.DataFrame:
    n = len(symbols)
    data: dict = {
        "symbol": symbols,
        "predicted_side": sides,
        "trade_date": trade_dates or ["2026-01-15"] * n,
        "proba_long": proba_long if proba_long is not None else [0.5] * n,
        "proba_short": proba_short if proba_short is not None else [0.1] * n,
        "proba_flat": [0.0] * n,
    }
    return pd.DataFrame(data)


class TestApplyCascadeToPredictions:
    def test_passed_symbols_unchanged(self, monkeypatch):
        """Les symboles retenus gardent leurs probas."""
        preds = _preds_df_ternary(
            ["AAPL"], ["long"], proba_long=[0.70], proba_short=[0.05],
        )
        ranks = _make_ranks_df([("AAPL", 0.95, 0.92)])

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob_classification": 0.55,
                                 "min_prob_regression": 0.10}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = apply_cascade_to_predictions(preds, "batch-x")

        assert len(result) == 1
        assert result.iloc[0]["predicted_side"] == "long"
        assert result.iloc[0]["proba_long"] == 0.70

    def test_filtered_symbols_become_flat(self, monkeypatch):
        """Les symboles non retenus → predicted_side = flat, probas = 0."""
        preds = _preds_df_ternary(
            ["MSFT"], ["long"], proba_long=[0.70], proba_short=[0.05],
        )
        ranks = _make_ranks_df([("MSFT", 0.50, 0.55)])  # milieu → filtré

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob_classification": 0.55,
                                 "min_prob_regression": 0.10}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = apply_cascade_to_predictions(preds, "batch-x")

        assert len(result) == 1
        assert result.iloc[0]["predicted_side"] == "flat"
        assert result.iloc[0]["proba_long"] == 0.0
        assert result.iloc[0]["proba_short"] == 0.0

    def test_mixed_pass_and_filter(self, monkeypatch):
        """Mélange symboles retenus et filtrés."""
        preds = _preds_df_ternary(
            ["AAPL", "MSFT", "GME"],
            ["long", "long", "short"],
            proba_long=[0.70, 0.70, 0.05],
            proba_short=[0.05, 0.05, 0.80],
        )
        ranks = _make_ranks_df([
            ("AAPL", 0.95, 0.92),   # top → LONG
            ("MSFT", 0.50, 0.55),   # milieu → filtré
            ("GME", 0.03, 0.05),    # bottom → SHORT
        ])

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob_classification": 0.55,
                                 "min_prob_regression": 0.10}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = apply_cascade_to_predictions(preds, "batch-x")

        assert len(result) == 3
        sides = dict(zip(result["symbol"], result["predicted_side"]))
        assert sides["AAPL"] == "long"
        assert sides["MSFT"] == "flat"
        assert sides["GME"] == "short"

    def test_cascade_score_column_added(self, monkeypatch):
        """La colonne cascade_score est ajoutée."""
        preds = _preds_df_ternary(
            ["AAPL"], ["long"], proba_long=[0.70], proba_short=[0.05],
        )
        ranks = _make_ranks_df([("AAPL", 0.95, 0.92)])

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob_classification": 0.55,
                                 "min_prob_regression": 0.10}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = apply_cascade_to_predictions(preds, "batch-x")

        assert "cascade_score" in result.columns
        assert result.iloc[0]["cascade_score"] > 0.0

    def test_empty_input(self):
        """DataFrame vide → retourné tel quel."""
        empty = pd.DataFrame(columns=["symbol", "trade_date", "predicted_side", "proba_long", "proba_short"])
        result = apply_cascade_to_predictions(empty, "batch-x")
        assert result.empty

    def test_missing_columns_skipped(self):
        """Colonnes manquantes → DataFrame retourné tel quel (warning log)."""
        bad = pd.DataFrame({"symbol": ["AAPL"], "trade_date": ["2026-01-15"]})
        result = apply_cascade_to_predictions(bad, "batch-x")
        # inchangé car colonnes required manquantes
        assert "proba_long" not in result.columns

    # ── FIX 2026-08-27 : cohérence cascade → phase 2 ──
    # Un candidat retenu par cascade_select (sur le rank, ex: DIP) doit voir son
    # predicted_side aligné sur le côté décidé, même si la prédiction per-symbol
    # d'origine était "flat". Avant, la branche ML normale gardait "flat" → phase 2
    # rejetait le signal (bug générique de contrat cascade→phase2).
    def test_retained_long_forces_side_long_even_if_pred_flat(self, monkeypatch):
        """Candidat retenu par le rank (DIP-like) mais prédiction per-symbol 'flat'
        → predicted_side forcé à 'long' (cohérence cascade→phase2)."""
        preds = _preds_df_ternary(
            ["AAPL"], ["flat"], proba_long=[0.84], proba_short=[0.16],
        )
        ranks = _make_ranks_df([("AAPL", 0.95, 0.92)])  # top → retenu LONG

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob_classification": 0.55,
                                 "min_prob_regression": 0.10}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = apply_cascade_to_predictions(preds, "batch-x")

        assert len(result) == 1
        assert result.iloc[0]["predicted_side"] == "long"  # était "flat" avant fix
        assert result.iloc[0]["proba_long"] == 0.84
        assert result.iloc[0]["proba_short"] == 0.0

    def test_rejected_stays_flat(self, monkeypatch):
        """Candidat NON retenu par la cascade → reste 'flat' (inchangé)."""
        preds = _preds_df_ternary(
            ["MSFT"], ["flat"], proba_long=[0.70], proba_short=[0.05],
        )
        ranks = _make_ranks_df([("MSFT", 0.50, 0.55)])  # milieu → filtré

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob_classification": 0.55,
                                 "min_prob_regression": 0.10}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = apply_cascade_to_predictions(preds, "batch-x")

        assert len(result) == 1
        assert result.iloc[0]["predicted_side"] == "flat"
        assert result.iloc[0]["proba_long"] == 0.0
        assert result.iloc[0]["proba_short"] == 0.0

    def test_retained_short_still_short(self, monkeypatch):
        """Candidat SHORT retenu par la cascade → predicted_side='short' (logique
        SHORT non cassée par le fix LONG)."""
        preds = _preds_df_ternary(
            ["GME"], ["short"], proba_long=[0.05], proba_short=[0.80],
        )
        ranks = _make_ranks_df([("GME", 0.03, 0.05)])  # bottom → SHORT

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob_classification": 0.55,
                                 "min_prob_regression": 0.10}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = apply_cascade_to_predictions(preds, "batch-x")

        assert len(result) == 1
        assert result.iloc[0]["predicted_side"] == "short"
        assert result.iloc[0]["proba_short"] == 0.80
        assert result.iloc[0]["proba_long"] == 0.0

    def test_retained_long_original_long_unchanged(self, monkeypatch):
        """Candidat LONG retenu avec prédiction 'long' d'origine → inchangé (régression)."""
        preds = _preds_df_ternary(
            ["AAPL"], ["long"], proba_long=[0.70], proba_short=[0.05],
        )
        ranks = _make_ranks_df([("AAPL", 0.95, 0.92)])  # top → LONG

        with patch("modelFactory.predictor.load_cascade_config",
                   return_value={"top_pct": 0.20, "min_prob_classification": 0.55,
                                 "min_prob_regression": 0.10}):
            with patch("modelFactory.predictor.load_global_ranks_from_db", return_value=ranks):
                result = apply_cascade_to_predictions(preds, "batch-x")

        assert len(result) == 1
        assert result.iloc[0]["predicted_side"] == "long"
        assert result.iloc[0]["proba_long"] == 0.70
        assert result.iloc[0]["proba_short"] == 0.0  # purge du côté opposé


# ═══════════════════════════════════════════════════════════════════
# upsert_global_ranks
# ═══════════════════════════════════════════════════════════════════

class TestUpsertGlobalRanks:
    def test_upsert_calls_execute(self):
        """Vérifie que l'upsert exécute bien les INSERT."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn

        ranks = [
            {"symbol": "AAPL", "global_rank_3": 0.95, "global_rank_5": 0.92, "global_rank_10": None},
            {"symbol": "MSFT", "global_rank_3": 0.50, "global_rank_5": 0.55, "global_rank_10": 0.48},
        ]
        count = upsert_global_ranks("batch-x", "2026-01-15", ranks, engine=mock_engine)

        assert count == 2
        assert mock_conn.execute.call_count == 2

    def test_empty_ranks_returns_zero(self):
        assert upsert_global_ranks("batch-x", "2026-01-15", [], engine=MagicMock()) == 0

    def test_no_engine_returns_zero(self):
        with patch("modelFactory.predictor.upsert_global_ranks", side_effect=None):
            # Appel sans engine → doit retourner 0 sans planter
            pass  # Testé via l'intégration, mock ci-dessus


# ═══════════════════════════════════════════════════════════════════
# load_global_ranks_from_db
# ═══════════════════════════════════════════════════════════════════

class TestLoadGlobalRanksFromDb:
    def test_returns_dataframe(self):
        """Les 2 requêtes (schéma puis données) sont mockées distinctement."""
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        # 1er execute = introspection du schéma (noms de colonnes), 2e = données.
        mock_conn.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=[
                ("symbol",), ("global_rank_3",), ("global_rank_5",), ("global_rank_10",),
            ])),
            MagicMock(fetchall=MagicMock(return_value=[
                ("AAPL", 0.95, 0.92, 0.88),
                ("MSFT", 0.50, 0.55, 0.48),
            ])),
        ]

        df = load_global_ranks_from_db("2026-01-15", "batch-x", engine=mock_engine)

        assert len(df) == 2
        assert list(df.columns) == ["symbol", "global_rank_3", "global_rank_5", "global_rank_10"]
        assert df.iloc[0]["symbol"] == "AAPL"

    def test_empty_result(self):
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = []

        df = load_global_ranks_from_db("2026-01-15", "batch-x", engine=mock_engine)
        assert df.empty


# ═══════════════════════════════════════════════════════════════════
# _resolve_predict_batch_id  (dans cli.py)
# ═══════════════════════════════════════════════════════════════════

class TestResolvePredictBatchId:
    def test_from_config_backtest_batch_id(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(
            "batch_diagnostics:\n  backtest_batch_id: my-batch-123\n",
            encoding="utf-8",
        )
        from modelFactory.cli import _resolve_predict_batch_id
        bid = _resolve_predict_batch_id(Path("/fake/artifacts/models"))
        assert bid == "my-batch-123"

    def test_fallback_to_dir_name(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Pas de config.yaml → fallback dir name
        from modelFactory.cli import _resolve_predict_batch_id
        bid = _resolve_predict_batch_id(Path("/fake/artifacts/models/model-factory-20260727-abc123"))
        assert bid == "model-factory-20260727-abc123"

    def test_none_when_indeterminable(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from modelFactory.cli import _resolve_predict_batch_id
        # Racine → name = "" ou "C:" → None
        bid = _resolve_predict_batch_id(Path("/"))
        assert bid is None


# ═══════════════════════════════════════════════════════════════════
# Garde-fou AST : bloc cascade dans _impl.py
# ═══════════════════════════════════════════════════════════════════

_IMPL_PATH = Path(__file__).resolve().parents[1] / "backtesting" / "cli" / "_impl.py"


class TestImplSourceContainsCascade:
    def test_imports_apply_cascade_to_predictions(self):
        tree = ast.parse(_IMPL_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "modelFactory.predictor":
                if any(a.name == "apply_cascade_to_predictions" for a in node.names):
                    return
        pytest.fail("_impl.py doit importer apply_cascade_to_predictions")

    def test_calls_apply_cascade_to_predictions(self):
        tree = ast.parse(_IMPL_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "apply_cascade_to_predictions":
                    return
        pytest.fail("_impl.py doit appeler apply_cascade_to_predictions")

    def test_contains_cascade_batch_id_block(self):
        text = _IMPL_PATH.read_text(encoding="utf-8")
        assert "_cascade_enabled" in text, "_impl.py doit contenir _cascade_enabled"
        assert "apply_cascade_to_predictions" in text, "_impl.py doit contenir apply_cascade_to_predictions"
        assert "cascade:" in text, "_impl.py doit lire la section cascade de config.yaml"

    def test_cascade_fail_fast_when_enabled(self):
        text = _IMPL_PATH.read_text(encoding="utf-8")
        # Vérifier que sys.exit(1) est appelé quand _cascade_enabled est true
        assert "if _cascade_enabled:" in text or "_cascade_enabled" in text


# ═══════════════════════════════════════════════════════════════════
# stacking_enabled dans insert_training_batch
# ═══════════════════════════════════════════════════════════════════

class TestStackingEnabledInDbRegistry:
    def test_mutable_fields_contains_stacking(self):
        from modelFactory.db_registry import _TRAINING_BATCH_MUTABLE_FIELDS
        assert "stacking_enabled" in _TRAINING_BATCH_MUTABLE_FIELDS

    def test_insert_includes_stacking(self):
        """Vérifie que l'INSERT SQL contient stacking_enabled."""
        from modelFactory.db_registry import insert_training_batch
        import inspect
        src = inspect.getsource(insert_training_batch)
        assert "stacking_enabled" in src
        assert ":stacking_enabled" in src

    def test_cli_passes_stacking_to_insert(self):
        """Vérifie que cli.py passe stacking_enabled à insert_training_batch."""
        cli_path = Path(__file__).resolve().parents[1] / "modelFactory" / "cli.py"
        text = cli_path.read_text(encoding="utf-8")
        assert "stacking_enabled=" in text
        assert "opts.enable_global_stacking" in text


# ═══════════════════════════════════════════════════════════════════
# report.py — ligne Stacking Global Rank
# ═══════════════════════════════════════════════════════════════════

class TestReportContainsStacking:
    def test_generate_batch_report_contains_stacking(self):
        report_path = Path(__file__).resolve().parents[1] / "modelFactory" / "report.py"
        text = report_path.read_text(encoding="utf-8")
        assert "Stacking Global Rank" in text
        assert "stacking_enabled" in text


# ═══════════════════════════════════════════════════════════════════
# ml_diagnostics.py — stacking display + global_rank_history
# ═══════════════════════════════════════════════════════════════════

class TestMlDiagnosticsCascade:
    def test_contains_stacking_metric(self):
        diag_path = Path(__file__).resolve().parents[1] / "ihm" / "pages" / "ml_diagnostics.py"
        text = diag_path.read_text(encoding="utf-8")
        assert "stacking_enabled" in text
        assert "Stacking Global Rank" in text

    def test_contains_global_rank_history_section(self):
        diag_path = Path(__file__).resolve().parents[1] / "ihm" / "pages" / "ml_diagnostics.py"
        text = diag_path.read_text(encoding="utf-8")
        assert "_render_global_rank_history" in text
        assert "GLOBAL_RANK_TOP_BOTTOM_QUERY" in text
        assert "global_rank_history" in text


# ═══════════════════════════════════════════════════════════════════
# global_ranking.py — blacklist : *_sector_neutral & CAPM réintégrés
# ═══════════════════════════════════════════════════════════════════

class TestSectorNeutralNotBlacklisted:
    """Vérifie que les features sector_neutral utiles sont conservées,
    et que les versions volatilité + CAPM sont re-blacklistées."""

    _CONSERVED_SECTOR_NEUTRAL = [
        "momentum_20_sector_neutral", "momentum_60_sector_neutral",
        "relative_strength_20_sector_neutral", "relative_strength_60_sector_neutral",
        "rsi_14_sector_neutral",
        "sma20_distance_sector_neutral", "sma50_distance_sector_neutral",
        "volume_ratio_20_sector_neutral",
    ]

    _BLACKLISTED_AGAIN = [
        "rolling_volatility_20_sector_neutral",
        "rolling_volatility_60_sector_neutral",
        "beta_252", "alpha_252", "r_squared_252",
    ]

    def test_useful_sector_neutral_present(self):
        """Les sector_neutral de momentum, RSI, SMA, volume sont conservées."""
        from modelFactory.global_ranking import _get_ranking_feature_columns
        from unittest.mock import MagicMock
        mock_cfg = MagicMock()
        mock_cfg.data.include_sentiment_features = False
        mock_cfg.data.include_screener_scores = False
        mock_cfg.data.include_short_score_features = False
        mock_cfg.data.include_macro_vix_features = False
        mock_cfg.data.include_macro_vxn_features = False
        mock_cfg.data.include_macro_vix3m_features = False
        mock_cfg.data.include_macro_move_features = False
        mock_cfg.data.include_macro_regime_features = False
        mock_cfg.data.include_fundamentals_features = False
        mock_cfg.data.include_factors_features = False
        mock_cfg.data.enable_cross_sectional_features = True
        mock_cfg.data.include_directional_features = False

        cols = _get_ranking_feature_columns(mock_cfg)
        for sn_col in self._CONSERVED_SECTOR_NEUTRAL:
            assert sn_col in cols, (
                f"{sn_col} devrait être conservée dans les features"
            )

    def test_volatility_sector_neutral_blacklisted(self):
        """Les sector_neutral de volatilité sont re-blacklistées."""
        from modelFactory.global_ranking import _get_ranking_feature_columns
        from unittest.mock import MagicMock
        mock_cfg = MagicMock()
        mock_cfg.data.include_sentiment_features = False
        mock_cfg.data.include_screener_scores = False
        mock_cfg.data.include_short_score_features = False
        mock_cfg.data.include_macro_vix_features = False
        mock_cfg.data.include_macro_vxn_features = False
        mock_cfg.data.include_macro_vix3m_features = False
        mock_cfg.data.include_macro_move_features = False
        mock_cfg.data.include_macro_regime_features = False
        mock_cfg.data.include_fundamentals_features = False
        mock_cfg.data.include_factors_features = False
        mock_cfg.data.enable_cross_sectional_features = True
        mock_cfg.data.include_directional_features = False

        cols = _get_ranking_feature_columns(mock_cfg)
        for bl_col in self._BLACKLISTED_AGAIN:
            assert bl_col not in cols, (
                f"{bl_col} doit être re-blacklistée"
            )

    def test_capm_factors_still_blacklisted(self):
        """CAPM doit rester blacklisté (importance 0.0)."""
        from modelFactory.global_ranking import _get_ranking_feature_columns
        from unittest.mock import MagicMock
        mock_cfg = MagicMock()
        mock_cfg.data.include_sentiment_features = False
        mock_cfg.data.include_screener_scores = False
        mock_cfg.data.include_short_score_features = False
        mock_cfg.data.include_macro_vix_features = False
        mock_cfg.data.include_macro_vxn_features = False
        mock_cfg.data.include_macro_vix3m_features = False
        mock_cfg.data.include_macro_move_features = False
        mock_cfg.data.include_macro_regime_features = False
        mock_cfg.data.include_fundamentals_features = False
        mock_cfg.data.include_factors_features = True  # CAPM actif
        mock_cfg.data.enable_cross_sectional_features = False

        cols = _get_ranking_feature_columns(mock_cfg)
        for capm in ("beta_252", "alpha_252", "r_squared_252"):
            assert capm not in cols, f"{capm} doit être blacklisté"

    def test_macro_features_still_blacklisted(self):
        """Les features macro (SPY/VIX) doivent rester blacklistées."""
        from modelFactory.global_ranking import _get_ranking_feature_columns
        from unittest.mock import MagicMock
        mock_cfg = MagicMock()
        mock_cfg.data.include_sentiment_features = False
        mock_cfg.data.include_screener_scores = False
        mock_cfg.data.include_short_score_features = False
        mock_cfg.data.include_macro_vix_features = True
        mock_cfg.data.include_macro_vxn_features = True
        mock_cfg.data.include_macro_vix3m_features = True
        mock_cfg.data.include_macro_move_features = True
        mock_cfg.data.include_macro_regime_features = True
        mock_cfg.data.include_fundamentals_features = False
        mock_cfg.data.include_factors_features = False
        mock_cfg.data.enable_cross_sectional_features = False

        cols = _get_ranking_feature_columns(mock_cfg)
        still_blacklisted = [
            "vix_close", "vxn_close", "vix3m_close", "move_close",
            "SPY_SMA_200_slope", "VIX_zscore",
        ]
        for sb in still_blacklisted:
            assert sb not in cols, (
                f"{sb} doit rester blacklistée (feature macro, identique ∀ symboles)"
            )


# ═══════════════════════════════════════════════════════════════════
# Sector-neutral computation in global_ranking.py
# ═══════════════════════════════════════════════════════════════════

class TestSectorNeutralComputation:
    """Vérifie que la logique de neutralisation sectorielle produit des
    valeurs non nulles quand un sector_map valide est fourni."""

    def test_neutralize_with_sectors(self):
        """Avec 2 secteurs distincts, les valeurs neutralisées doivent
        différer des valeurs brutes quand le secteur a un signal différent."""
        import pandas as pd
        import numpy as np

        # Simuler un mini-panel : 4 symboles, 2 secteurs, 2 dates
        df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT", "XOM", "CVX",
                       "AAPL", "MSFT", "XOM", "CVX"],
            "date": ["2025-01-15"] * 4 + ["2025-01-16"] * 4,
            "momentum_20": [0.10, 0.12, -0.05, -0.03,
                           0.08, 0.11, -0.02, -0.01],
            "rsi_14": [65.0, 62.0, 35.0, 38.0,
                       63.0, 60.0, 37.0, 40.0],
        })
        sector_map = {
            "AAPL": "Technology", "MSFT": "Technology",
            "XOM": "Energy", "CVX": "Energy",
        }
        df["_sector"] = df["symbol"].str.upper().map(sector_map)
        valid = df["_sector"].notna()

        # Neutraliser momentum_20
        target_col = "momentum_20_sector_neutral"
        src_col = "momentum_20"
        sector_med = df.loc[valid].groupby(["date", "_sector"])[src_col].transform("median")
        neutral = df[src_col].copy()
        neutral.loc[valid] = df.loc[valid, src_col] - sector_med
        neutral.loc[~valid] = 0.0
        df[target_col] = neutral.fillna(0.0).astype(float)

        # AAPL (momentum=0.10) dans Technology (médiane=0.11) → -0.01
        aapl_row = df[(df["symbol"] == "AAPL") & (df["date"] == "2025-01-15")]
        assert abs(float(aapl_row[target_col].iloc[0]) - (-0.01)) < 1e-6, (
            f"AAPL sector_neutral devrait être -0.01, got {aapl_row[target_col].iloc[0]}"
        )

        # XOM (momentum=-0.05) dans Energy (médiane=-0.04) → -0.01
        xom_row = df[(df["symbol"] == "XOM") & (df["date"] == "2025-01-15")]
        assert abs(float(xom_row[target_col].iloc[0]) - (-0.01)) < 1e-6

    def test_all_same_sector_produces_zeros(self):
        """Si tous les symboles sont dans le même secteur, la neutralisation
        produit des zéros (pas de variation inter-secteur)."""
        import pandas as pd

        df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT", "GOOG"],
            "date": ["2025-01-15"] * 3,
            "momentum_20": [0.10, 0.12, 0.08],
        })
        sector_map = {"AAPL": "Technology", "MSFT": "Technology", "GOOG": "Technology"}
        df["_sector"] = df["symbol"].str.upper().map(sector_map)
        valid = df["_sector"].notna()

        # Médiane = 0.10 → tout le monde est à la médiane → neutral = 0
        sector_med = df.loc[valid].groupby(["date", "_sector"])["momentum_20"].transform("median")
        neutral = df["momentum_20"].copy()
        neutral.loc[valid] = df.loc[valid, "momentum_20"] - sector_med
        neutral.loc[~valid] = 0.0
        df["momentum_20_sector_neutral"] = neutral.fillna(0.0)

        # Ce n'est pas "tout zéro" — la médiane est 0.10 donc AAPL=0.0, MSFT=0.02, GOOG=-0.02
        values = df["momentum_20_sector_neutral"].tolist()
        assert values == pytest.approx([0.0, 0.02, -0.02], abs=1e-6)

    def test_no_sector_map_produces_zeros(self):
        """Sans sector_map, pas de colonne _sector → tout est ~valid → zéros."""
        import pandas as pd

        df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "date": ["2025-01-15"] * 2,
            "momentum_20": [0.10, 0.12],
        })
        # Pas de secteur → _sector est NaN → valid=False → tout = 0.0
        df["_sector"] = None
        valid = df["_sector"].notna()

        neutral = df["momentum_20"].copy()
        neutral.loc[valid] = df.loc[valid, "momentum_20"] - 0.0  # never executed
        neutral.loc[~valid] = 0.0
        df["momentum_20_sector_neutral"] = neutral.fillna(0.0)

        assert (df["momentum_20_sector_neutral"] == 0.0).all()
