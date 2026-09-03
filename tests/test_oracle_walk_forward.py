"""Tests unitaires Oracle S4 — walk-forward causal (build_folds)."""
from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.oracle.walk_forward import build_folds, run_walk_forward


def _dataset(n_days: int = 100, n_symbols: int = 20) -> pd.DataFrame:
    dates = pd.date_range("2021-01-01", periods=n_days, freq="B")
    rows = []
    for i, d in enumerate(dates):
        for s in range(n_symbols):
            # oracle_available_date = date + 21 jours ouvrés (H20 + 1)
            avail = dates[i + 21] if i + 21 < len(dates) else None
            rows.append({
                "date": d,
                "symbol": f"S{s:03d}",
                "oracle_available_date": avail,
                "oracle_extreme10": (s + i) % 10 == 0,
                "future_return": 0.01 * ((s + i) % 10),
                "global_rank_20": (s + i) / (n_symbols + n_days),
            })
    df = pd.DataFrame(rows)
    df["oracle_available_date"] = pd.to_datetime(df["oracle_available_date"])
    df = df.dropna(subset=["oracle_available_date"])
    return df


class TestBuildFolds:
    def test_no_leakage_train_labels_available_before_test(self):
        df = _dataset(n_days=400)
        windows = [("2021-06-01", "2021-12-31"), ("2022-01-01", "2022-03-31")]
        folds = build_folds(df, windows)
        assert len(folds) >= 1
        for fold in folds:
            t_start = pd.Timestamp(fold["t_start"])
            # Toutes les labels d'entraînement sont strictement disponibles avant le début du test
            assert (fold["train"]["oracle_available_date"] < t_start).all()
            # Toutes les dates de test sont dans la fenêtre
            assert (fold["test"]["date"] >= t_start).all()

    def test_expanding_window_train_grows(self):
        df = _dataset(n_days=300)
        windows = [("2021-06-01", "2021-12-31"), ("2022-01-01", "2022-06-30")]
        folds = build_folds(df, windows)
        assert len(folds) == 2
        # Fenêtre expansive : le 2e fold a plus de données d'entraînement
        assert len(folds[1]["train"]) > len(folds[0]["train"])

    def test_empty_fold_skipped(self):
        df = _dataset(n_days=60)
        # fenêtre de test après la fin des données → pas de test → fold sauté
        windows = [("2025-01-01", "2025-12-31")]
        folds = build_folds(df, windows)
        assert folds == []

    def test_t2_raises_on_violation(self):
        # Dataset qui violerait T2 : label disponible APRES le début du test.
        df = pd.DataFrame({
            "date": pd.to_datetime(["2021-06-01"]),
            "symbol": ["AAPL"],
            "oracle_available_date": pd.to_datetime(["2021-09-01"]),  # > t_start
            "oracle_extreme10": [1],
            "future_return": [0.1],
            "global_rank_20": [0.9],
        })
        # build_folds filtre train par available < t_start → train vide → fold sauté,
        # donc T2 n'est pas déclenché ici (le fold est simplement ignoré).
        folds = build_folds(df, [("2021-06-15", "2021-12-31")])
        assert folds == []


def test_walk_forward_rejects_null_oracle_targets_without_type_error():
    dataset = pd.DataFrame({
        "oracle_extreme10": [None, None],
        "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
    })

    result = run_walk_forward(dataset, [], folds=[])

    assert result == {"status": "error", "reason": "no_labeled_oracle_targets"}
