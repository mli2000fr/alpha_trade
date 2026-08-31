"""Tests de la section 🔥 Oracle Extreme du rapport Diagnostic ML.

``modelFactory/report.py`` doit reproduire, en markdown, les métriques de
qualité OOS de la couche Oracle Extreme affichées dans la page IHM Diagnostic
ML (``ihm/pages/ml_diagnostics.py:_render_oracle_quality``) : AUC, IC,
precision@10%, lift, calibration D1-D10, monotonicité, répartition
directionnelle et plafond omniscient.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import modelFactory.report as report


def _fake_oos(n_dates: int = 12, per_date: int = 120) -> pd.DataFrame:
    """Prédictions OOS synthétiques (schéma de ``oracle_extreme_predictions``)."""
    rng = np.random.default_rng(42)
    rows: list[dict[str, object]] = []
    for d in pd.date_range("2025-01-01", periods=n_dates, freq="D"):
        for i in range(per_date):
            proba = float(np.clip(rng.normal(0.5, 0.25), 0.001, 0.999))
            fut = float(rng.normal(0, 0.02))
            ext = int(1 if (proba + rng.normal(0, 0.3)) > 0.85 else 0)
            rows.append({
                "date": d,
                "symbol": f"S{i:03d}",
                "proba_extreme": proba,
                "future_return": fut,
                "oracle_extreme10": ext,
            })
    return pd.DataFrame(rows)


def _patch_batch(monkeypatch: pytest.MonkeyPatch, metadata_json: str) -> None:
    detail = pd.DataFrame([{
        "batch_id": "test-batch",
        "metadata_json": metadata_json,
    }])
    monkeypatch.setattr(
        report, "_safe_query", lambda engine, q, params=None: detail
    )


def _patch_predictions(monkeypatch: pytest.MonkeyPatch, df: pd.DataFrame) -> None:
    import modelFactory.oracle.predictions_store as ps
    monkeypatch.setattr(
        ps, "load_oracle_predictions", lambda engine, *, batch_id: df
    )


def test_append_oracle_extreme_quality_renders_full_section(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un batch ayant entraîné Oracle produit la section complète."""
    _patch_batch(
        monkeypatch,
        '{"oracle": true, "cli_options": {"enable_oracle_model": true}}',
    )
    _patch_predictions(monkeypatch, _fake_oos())

    lines: list[str] = []
    report._append_oracle_extreme_quality(lines, engine=object(), batch_id="test-batch")
    out = "\n".join(lines)

    assert "## 🔥 Oracle Extreme — Qualité du modèle (OOS)" in out
    assert "AUC (cible extrême)" in out
    assert "IC (proba vs rendement)" in out
    assert "Precision@10%" in out
    assert "🚀 Lift top 10%" in out
    assert "Calibration — déciles" in out
    assert "Monotonicité décile" in out
    assert "Répartition directionnelle" in out
    assert "Plafond omniscient" in out
    # La colonne de calibration doit être « Décile » (D1..D10), pas « index ».
    assert "| D1 |" in out
    assert "| D10 |" in out


def test_append_oracle_extreme_quality_skips_without_oracle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch sans couche Oracle Extreme → aucune section dans le rapport."""
    _patch_batch(monkeypatch, '{"cli_options": {"enable_oracle_model": false}}')

    lines: list[str] = []
    report._append_oracle_extreme_quality(lines, engine=object(), batch_id="test-batch")
    assert not any("Oracle Extreme" in line for line in lines)


def test_append_oracle_extreme_quality_skips_without_predictions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch Oracle mais sans prédictions OOS → aucune section."""
    _patch_batch(monkeypatch, '{"oracle": true}')
    _patch_predictions(monkeypatch, pd.DataFrame())

    lines: list[str] = []
    report._append_oracle_extreme_quality(lines, engine=object(), batch_id="test-batch")
    assert not any("Oracle Extreme" in line for line in lines)


def test_generate_batch_report_calls_new_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    """`generate_batch_report` appelle bien les sections Périodes + Répartition + Qualité Oracle."""
    called: list[str] = []

    def _spy_periods(lines: list[str], engine: object, batch_id: str) -> None:
        called.append(("periods", batch_id))
        lines.append("## 📅 Périodes de prédictions du batch")

    def _spy_distribution(lines: list[str], engine: object, batch_id: str) -> None:
        called.append(("distribution", batch_id))
        lines.append("## 🔀 Répartition Oracle — TOP / BOTTOM 10% du modèle")

    def _spy_quality(lines: list[str], engine: object, batch_id: str) -> None:
        called.append(("quality", batch_id))
        lines.append("## 🔥 Oracle Extreme — Qualité du modèle (OOS)")

    monkeypatch.setattr(report, "_append_prediction_periods", _spy_periods)
    monkeypatch.setattr(report, "_append_oracle_distribution", _spy_distribution)
    monkeypatch.setattr(report, "_append_oracle_extreme_quality", _spy_quality)
    # On court-circuite les autres sous-sections pour un test ciblé.
    monkeypatch.setattr(report, "_safe_query", lambda engine, q, params=None: pd.DataFrame())
    monkeypatch.setattr(report, "_append_global_ranking_horizon_details", lambda *a, **k: None)
    monkeypatch.setattr(report, "_append_backtest_results", lambda *a, **k: None)
    monkeypatch.setattr(report, "_append_champion_status", lambda *a, **k: None)
    monkeypatch.setattr(report, "_build_regime_table", lambda *a, **k: pd.DataFrame())

    out = report.generate_batch_report(engine=object(), batch_id="test-batch")
    assert ("periods", "test-batch") in called
    assert ("distribution", "test-batch") in called
    assert ("quality", "test-batch") in called
    assert "Périodes de prédictions" in out
    assert "Répartition Oracle" in out
    assert "Oracle Extreme" in out


def _prediction_periods_fixtures() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Détail batch (oracle), couverture GR, runs (synth/per-symbol/sector), périodes oracle."""
    detail = pd.DataFrame([{
        "batch_id": "test-batch",
        "metadata_json": '{"oracle": true, "global_ranking": {"best_horizon": 10}}',
    }])
    coverage = pd.DataFrame([{
        "min_date": pd.Timestamp("2025-01-01"), "max_date": pd.Timestamp("2025-01-10"),
        "nb_dates": 8, "nb_symbols": 390,
    }])
    runs = pd.DataFrame([
        {"run_id": "test-batch_globalrank_synth", "run_symbol": "__GLOBAL_RANK_SYNTH__",
         "n_rows": 3120, "nb_symbols": 390, "min_date": pd.Timestamp("2025-01-01"),
         "max_date": pd.Timestamp("2025-01-10"), "nb_dates": 8},
        {"run_id": "test-batch_aapl", "run_symbol": "AAPL",
         "n_rows": 8, "nb_symbols": 1, "min_date": pd.Timestamp("2025-01-01"),
         "max_date": pd.Timestamp("2025-01-10"), "nb_dates": 8},
        {"run_id": "test-batch_it", "run_symbol": "Information Technology",
         "n_rows": 320, "nb_symbols": 40, "min_date": pd.Timestamp("2025-01-01"),
         "max_date": pd.Timestamp("2025-01-10"), "nb_dates": 8},
    ])
    oracle = pd.DataFrame([{
        "min_date": pd.Timestamp("2025-02-01"), "max_date": pd.Timestamp("2025-02-20"),
        "nb_dates": 15, "nb_symbols": 300,
    }])
    return detail, coverage, runs, oracle


def test_append_prediction_periods_renders_all_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rend la section Périodes avec les 4 types de modèle + détails secteur/oracle."""
    detail, coverage, runs, oracle = _prediction_periods_fixtures()

    def _fake_safe_query(engine: object, q: str, params: dict | None = None) -> pd.DataFrame:
        if "model_training_batch" in q:
            return detail
        if "global_rank_history" in q:
            return coverage
        if "model_predictions" in q:
            return runs
        if "oracle_extreme_predictions" in q:
            return oracle
        return pd.DataFrame()

    monkeypatch.setattr(report, "_safe_query", _fake_safe_query)

    lines: list[str] = []
    report._append_prediction_periods(lines, engine=object(), batch_id="test-batch")
    out = "\n".join(lines)

    assert "## 📅 Périodes de prédictions du batch" in out
    assert "🌐 Modèle global (Global Ranking)" in out
    assert "📈 Per-symbol" in out
    assert "🗂️ Per-sector" in out
    assert "🔥 Oracle extreme" in out
    assert "### 🗂️ Détail par secteur" in out
    assert "Information Technology" in out
    assert "### 🔥 Détail Oracle extreme (runs)" in out


def test_append_prediction_periods_oracle_not_trained(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch sans Oracle → la ligne Oracle indique « non entraîné » et pas de détail runs."""
    detail = pd.DataFrame([{
        "batch_id": "test-batch",
        "metadata_json": '{"cli_options": {"enable_oracle_model": false}}',
    }])
    coverage = pd.DataFrame([{
        "min_date": pd.Timestamp("2025-01-01"), "max_date": pd.Timestamp("2025-01-10"),
        "nb_dates": 8, "nb_symbols": 390,
    }])

    def _fake_safe_query(engine: object, q: str, params: dict | None = None) -> pd.DataFrame:
        if "model_training_batch" in q:
            return detail
        if "global_rank_history" in q:
            return coverage
        return pd.DataFrame()

    monkeypatch.setattr(report, "_safe_query", _fake_safe_query)

    lines: list[str] = []
    report._append_prediction_periods(lines, engine=object(), batch_id="test-batch")
    out = "\n".join(lines)

    assert "non entraîné dans ce batch" in out
    assert "### 🔥 Détail Oracle extreme (runs)" not in out


def _oracle_distribution_fixtures() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Détail batch (GR best_h=10 + oracle), rangs globaux, labels oracle, OOS."""
    detail = pd.DataFrame([{
        "batch_id": "test-batch",
        "metadata_json": '{"oracle": true, "global_ranking": {"best_horizon": 10}}',
    }])
    rng = np.random.default_rng(7)
    gr_rows: list[dict[str, object]] = []
    lab_rows: list[dict[str, object]] = []
    for d in pd.date_range("2025-01-01", periods=5, freq="D"):
        for i in range(80):
            gr_rows.append({"date": d, "symbol": f"S{i:03d}",
                            "global_rank_best": float(rng.uniform(0, 1))})
            lab_rows.append({"prediction_date": d, "symbol": f"S{i:03d}",
                             "oracle_decile": int(rng.integers(1, 11))})
    return detail, pd.DataFrame(gr_rows), pd.DataFrame(lab_rows), _fake_oos(n_dates=5, per_date=80)


def test_append_oracle_distribution_renders_both_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rend la répartition TOP/BOTTOM pour le Modèle global ET l'Oracle Extreme."""
    detail, global_df, labels_df, oos = _oracle_distribution_fixtures()

    def _fake_safe_query(engine: object, q: str, params: dict | None = None) -> pd.DataFrame:
        if "model_training_batch" in q:
            return detail
        if "global_rank_history" in q:
            return global_df
        if "global_oracle_labels" in q:
            return labels_df
        return pd.DataFrame()

    monkeypatch.setattr(report, "_safe_query", _fake_safe_query)
    import modelFactory.oracle.predictions_store as ps
    monkeypatch.setattr(ps, "load_oracle_predictions", lambda engine, *, batch_id: oos)

    lines: list[str] = []
    report._append_oracle_distribution(lines, engine=object(), batch_id="test-batch")
    out = "\n".join(lines)

    assert "## 🔀 Répartition Oracle — TOP / BOTTOM 10% du modèle" in out
    assert "### 🌐 Modèle global" in out
    assert "### 🔥 Modèle Oracle Extreme" in out
    assert "🟢 TOP 10% du modèle → déciles Oracle" in out
    assert "🔴 BOTTOM 10% du modèle → déciles Oracle" in out
    assert "| D1 |" in out
    assert "| **Total** |" in out
    # Les deux modèles produisent chacun 2 tableaux (TOP + BOTTOM).
    assert out.count("TOP 10% du modèle → déciles Oracle") == 2
    assert out.count("BOTTOM 10% du modèle → déciles Oracle") == 2


def test_append_oracle_distribution_skips_if_no_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batch sans modèle global ni Oracle → aucune section dans le rapport."""
    detail = pd.DataFrame([{
        "batch_id": "test-batch",
        "metadata_json": '{"cli_options": {"enable_oracle_model": false}}',
    }])

    def _fake_safe_query(engine: object, q: str, params: dict | None = None) -> pd.DataFrame:
        if "model_training_batch" in q:
            return detail
        return pd.DataFrame()

    monkeypatch.setattr(report, "_safe_query", _fake_safe_query)

    lines: list[str] = []
    report._append_oracle_distribution(lines, engine=object(), batch_id="test-batch")
    assert not any("Répartition Oracle" in line for line in lines)
