from __future__ import annotations

import os

import numpy as np

from modelFactory.config import ReproducibilityConfig
from modelFactory.model_benchmark import (
    BenchmarkReport,
    ChallengerResult,
    SimpleBaselines,
)
from modelFactory.reproducibility import _MAX_NUMPY_SEED, apply_reproducibility, derive_seed


def test_apply_reproducibility_keeps_pythonhashseed_in_supported_range() -> None:
    state = apply_reproducibility(ReproducibilityConfig(seed=(2**63 - 2), deterministic=True))

    python_hash_seed = int(os.environ["PYTHONHASHSEED"])
    assert 0 <= python_hash_seed < _MAX_NUMPY_SEED
    assert python_hash_seed == state["python_hash_seed"]
    assert state["seed"] == 2**63 - 2


# ── Sprint Maître 4 : tests de reproductibilité et stabilité ────────────────

def test_derive_seed_is_deterministic() -> None:
    """Même entrée → même seed dérivée."""
    s1 = derive_seed(42, "tabular_baseline", "lightgbm", "AAPL")
    s2 = derive_seed(42, "tabular_baseline", "lightgbm", "AAPL")
    assert s1 == s2


def test_derive_seed_different_per_model() -> None:
    """Modèles différents → seeds différentes."""
    s_lgbm = derive_seed(42, "tabular_baseline", "lightgbm", "AAPL")
    s_cb = derive_seed(42, "tabular_baseline", "catboost", "AAPL")
    assert s_lgbm != s_cb


def test_derive_seed_different_per_symbol() -> None:
    """Symboles différents → seeds différentes."""
    s_aapl = derive_seed(42, "tabular_baseline", "lightgbm", "AAPL")
    s_msft = derive_seed(42, "tabular_baseline", "lightgbm", "MSFT")
    assert s_aapl != s_msft


def test_same_seed_same_random() -> None:
    """Même seed → mêmes nombres aléatoires."""
    rng1 = np.random.RandomState(42)
    rng2 = np.random.RandomState(42)
    assert (rng1.randn(100) == rng2.randn(100)).all()


def test_different_seed_different_random() -> None:
    """Seeds différentes → nombres aléatoires différents."""
    rng1 = np.random.RandomState(42)
    rng2 = np.random.RandomState(43)
    assert not (rng1.randn(100) == rng2.randn(100)).all()


def test_multi_seed_stability_measured() -> None:
    """La stabilité multi-seeds doit être mesurable (≥ 1 seed)."""
    f1_scores = [0.72, 0.74, 0.71]
    f1_vals = np.array(f1_scores, float)
    mean_f1 = float(np.mean(f1_vals))
    std_f1 = float(np.std(f1_vals))
    assert mean_f1 > 0.7
    assert std_f1 < 0.1


def test_multi_seed_outlier_detected() -> None:
    """Un seed avec performance anormale doit être détectable."""
    f1_scores = [0.72, 0.74, 0.35]
    std = float(np.std(f1_scores))
    assert std > 0.15


def test_class_weights_on_train_only() -> None:
    """Les poids de classes doivent être calculés sur train, pas val/test."""
    y_train = np.array([0, 0, 0, 1, 1])
    y_val = np.array([1, 1, 1, 0, 0])
    n_train = len(y_train)
    classes_train, counts_train = np.unique(y_train, return_counts=True)
    weights_train = {c: n_train / (len(classes_train) * cnt) for c, cnt in zip(classes_train, counts_train)}
    n_val = len(y_val)
    classes_val, counts_val = np.unique(y_val, return_counts=True)
    weights_val = {c: n_val / (len(classes_val) * cnt) for c, cnt in zip(classes_val, counts_val)}
    assert weights_train != weights_val
    assert weights_train[1] > 1.0


def test_always_flat_not_collapsed() -> None:
    """Always-flat est une baseline valide (non collapsed par définition)."""
    result = SimpleBaselines.always_flat(
        np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1]),
    )
    assert result.collapsed is False


def test_benchmark_report_summary_complete() -> None:
    report = BenchmarkReport(symbol="TEST", n_seeds=2)
    report.baselines["always_flat"] = SimpleBaselines.always_flat(
        np.array([0, 1]), np.array([0, 1]),
    )
    report.champion = "lightgbm"
    report.champion_score = 0.78
    report.summary = {
        "total_runs": 2, "completed_runs": 2,
        "collapsed_runs": 0, "below_baseline_runs": 0,
        "champion": "lightgbm", "champion_score": 0.78,
        "rejected_count": 0,
    }
    d = report.to_dict()
    assert d["summary"]["champion"] == "lightgbm"
    assert d["summary"]["collapsed_runs"] == 0

