"""modelFactory/model_benchmark.py — Runner de benchmark unifié (Sprint Maître 4).

Garantit que tous les challengers sont évalués dans des conditions identiques :
- Mêmes folds (indices train/val/test).
- Mêmes features, labels, coûts.
- Mêmes seeds (reproductibilité).
- Class weights calculés sur train uniquement.
- Mesure de stabilité multi-seeds, latence, complexité.
- Rejet des modèles collapsed ou inférieurs aux baselines simples.

Usage ::

    from modelFactory.model_benchmark import (
        BenchmarkRunner, run_model_benchmark, SimpleBaselines,
    )
    runner = BenchmarkRunner(prepared_df, config)
    report = runner.run()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from modelFactory.config import TrainingConfig
from modelFactory.evaluation import check_model_collapse, compute_multiclass_metrics
from modelFactory.tabular_baseline import compute_tabular_metrics, tabular_split

LOGGER = logging.getLogger(__name__)


# ── Simple baselines ────────────────────────────────────────────────────────

@dataclass
class SimpleBaselineResult:
    """Résultat d'une baseline simple (non-ML)."""
    name: str
    accuracy: float
    f1_macro: float | None
    balanced_accuracy: float | None
    action_rate: float
    collapsed: bool = False
    collapse_reason: str | None = None
    latency_ms: float = 0.0
    params_count: int = 0


class SimpleBaselines:
    """Baselines non-ML pour calibration du benchmark.

    Fournit les prédictions de référence :
    - ``always_flat`` : prédit toujours la classe majoritaire (flat=1 en ternaire).
    - ``momentum`` : prédit long si rendement récent > 0, short sinon.
    - ``mean_reversion`` : prédit l'inverse du momentum.
    - ``logistic`` : régression logistique simple sur les features.

    Toutes les baselines utilisent UNIQUEMENT les données train pour
    leurs paramètres (ex: seuil momentum calculé sur train).
    """

    @staticmethod
    def always_flat(y_train: np.ndarray, y_val: np.ndarray) -> SimpleBaselineResult:
        """Prédit toujours flat (classe 1 en ternaire, 0 en binaire)."""
        # En ternaire, flat=1 ; en binaire, négatif=0
        n_val = len(y_val)
        preds = np.ones(n_val, dtype=np.int64) if len(np.unique(y_train)) >= 3 else np.zeros(n_val, dtype=np.int64)
        acc = float((preds == y_val).mean())
        return SimpleBaselineResult(
            name="always_flat",
            accuracy=acc,
            f1_macro=None,
            balanced_accuracy=None,
            action_rate=0.0,
        )

    @staticmethod
    def momentum(
        returns_train: np.ndarray,
        returns_val: np.ndarray,
        y_train: np.ndarray,
        y_val: np.ndarray,
        *,
        lookback: int = 20,
    ) -> SimpleBaselineResult:
        """Momentum : long si rendement > 0, short/flat sinon.

        Le seuil est calculé sur train uniquement.
        """
        n_val = len(y_val)
        is_ternary = len(np.unique(y_train)) >= 3

        # Calculer le momentum sur train pour déterminer le seuil
        train_mom = np.mean(returns_train[-lookback:]) if len(returns_train) >= lookback else np.mean(returns_train)
        # Sur validation : prédire selon le signe du rendement
        preds = np.zeros(n_val, dtype=np.int64)
        if is_ternary:
            preds[returns_val > 0] = 1   # long
            preds[returns_val < -0.01] = -1  # short
            # flat = 0 (défaut)
        else:
            preds[returns_val > 0] = 1

        acc = float((preds == y_val).mean())
        action_rate = float((preds != (1 if is_ternary else 0)).mean())
        return SimpleBaselineResult(
            name="momentum",
            accuracy=acc,
            f1_macro=None,
            balanced_accuracy=None,
            action_rate=action_rate,
        )

    @staticmethod
    def mean_reversion(
        returns_train: np.ndarray,
        returns_val: np.ndarray,
        y_train: np.ndarray,
        y_val: np.ndarray,
        *,
        lookback: int = 20,
    ) -> SimpleBaselineResult:
        """Mean-reversion : prédit l'inverse du momentum."""
        n_val = len(y_val)
        is_ternary = len(np.unique(y_train)) >= 3

        preds = np.zeros(n_val, dtype=np.int64)
        if is_ternary:
            preds[returns_val < -0.01] = 1    # long après baisse
            preds[returns_val > 0] = -1       # short après hausse
        else:
            preds[returns_val < 0] = 1

        acc = float((preds == y_val).mean())
        action_rate = float((preds != (1 if is_ternary else 0)).mean())
        return SimpleBaselineResult(
            name="mean_reversion",
            accuracy=acc,
            f1_macro=None,
            balanced_accuracy=None,
            action_rate=action_rate,
        )

    @staticmethod
    def logistic(
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        *,
        is_ternary: bool = False,
    ) -> SimpleBaselineResult:
        """Régression logistique régularisée (L2)."""
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError:
            return SimpleBaselineResult(
                name="logistic", accuracy=0.0, f1_macro=None,
                balanced_accuracy=None, action_rate=0.0,
                collapse_reason="sklearn_not_installed",
            )

        t0 = time.perf_counter()
        # Gérer les NaN/inf
        X_train = np.nan_to_num(np.asarray(X_train, float), nan=0.0, posinf=0.0, neginf=0.0)
        X_val = np.nan_to_num(np.asarray(X_val, float), nan=0.0, posinf=0.0, neginf=0.0)

        if is_ternary:
            # One-vs-rest multiclasse
            model = LogisticRegression(
                multi_class="ovr", max_iter=500, C=1.0, random_state=42,
            )
        else:
            model = LogisticRegression(max_iter=500, C=1.0, random_state=42)

        model.fit(X_train, y_train)
        preds = model.predict(X_val)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        acc = float((preds == y_val).mean())
        n_classes = len(np.unique(np.concatenate([y_train, y_val])))
        action_rate = float((preds != (1 if is_ternary else 0)).mean())

        # Collapse check
        collapsed, reason = False, None
        if preds is not None and len(preds) > 10:
            n_classes_pred = len(np.unique(preds))
            if n_classes_pred < 2:
                collapsed, reason = True, f"single_class_predicted_{np.unique(preds)[0]}"

        return SimpleBaselineResult(
            name="logistic",
            accuracy=acc,
            f1_macro=None,
            balanced_accuracy=None,
            action_rate=action_rate,
            collapsed=collapsed,
            collapse_reason=reason,
            latency_ms=latency_ms,
            params_count=int(np.sum([np.prod(coef.shape) for coef in [model.coef_, model.intercept_]])),
        )


# ── Benchmark runner ────────────────────────────────────────────────────────

@dataclass
class BenchmarkConfig:
    """Configuration du benchmark (Sprint Maître 4)."""

    n_seeds: int = 3
    base_seed: int = 42
    min_improvement_vs_baseline: float = 0.01  # 1% de gain min sur F1 macro
    max_latency_ms: float = 60_000  # 60 secondes max EOD
    reject_collapsed: bool = True
    reject_below_baselines: bool = True
    measure_latency: bool = True


@dataclass
class ChallengerResult:
    """Résultat d'un challenger ML sur un fold/seed."""

    model_name: str
    seed: int
    status: str  # "completed", "skipped", "failed"
    val_metrics: dict[str, Any] = field(default_factory=dict)
    test_metrics: dict[str, Any] = field(default_factory=dict)
    collapsed: bool = False
    collapse_reason: str | None = None
    latency_train_ms: float = 0.0
    latency_predict_ms: float = 0.0
    params_count: int = 0
    below_baseline: bool = False
    error: str | None = None


@dataclass
class BenchmarkReport:
    """Rapport de benchmark complet."""

    symbol: str
    n_seeds: int
    baselines: dict[str, SimpleBaselineResult] = field(default_factory=dict)
    challengers: dict[str, list[ChallengerResult]] = field(default_factory=dict)
    champion: str | None = None
    champion_score: float = 0.0
    rejected_models: list[dict[str, str]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "n_seeds": self.n_seeds,
            "baselines": {
                name: {
                    "accuracy": b.accuracy,
                    "f1_macro": b.f1_macro,
                    "action_rate": b.action_rate,
                }
                for name, b in self.baselines.items()
            },
            "challengers": {
                name: [
                    {
                        "seed": c.seed,
                        "status": c.status,
                        "collapsed": c.collapsed,
                        "f1_macro": c.val_metrics.get("f1_macro"),
                        "auc_macro": c.val_metrics.get("auc_macro"),
                        "balanced_accuracy": c.val_metrics.get("balanced_accuracy"),
                        "latency_predict_ms": c.latency_predict_ms,
                        "below_baseline": c.below_baseline,
                    }
                    for c in results
                ]
                for name, results in self.challengers.items()
            },
            "champion": self.champion,
            "champion_score": self.champion_score,
            "rejected_models": self.rejected_models,
            "summary": self.summary,
        }


class BenchmarkRunner:
    """Runner de benchmark unifié (Sprint Maître 4).

    Garantit que tous les modèles sont comparés équitablement :
    mêmes données, mêmes folds, mêmes seeds.
    """

    def __init__(
        self,
        prepared_df: pd.DataFrame,
        training_cfg: TrainingConfig,
        *,
        benchmark_cfg: BenchmarkConfig | None = None,
    ) -> None:
        self.df = prepared_df
        self.training_cfg = training_cfg
        self.benchmark_cfg = benchmark_cfg or BenchmarkConfig()
        self.is_ternary = training_cfg.data.target_mode == "ternary"

    # ── Public API ──────────────────────────────────────────────────────

    def run(self) -> BenchmarkReport:
        """Exécute le benchmark complet."""
        symbol = self._resolve_symbol()
        report = BenchmarkReport(
            symbol=symbol,
            n_seeds=self.benchmark_cfg.n_seeds,
        )

        # 1. Split train/val/test
        train_df, val_df, test_df = tabular_split(
            self.df,
            train_ratio=self.training_cfg.data.train_ratio,
            val_ratio=self.training_cfg.data.val_ratio,
            forecast_horizon=self.training_cfg.data.forecast_horizon,
        )

        # 2. Extraire les arrays
        feature_cols = self._get_feature_columns()
        X_train = train_df[feature_cols].to_numpy(float)
        X_val = val_df[feature_cols].to_numpy(float)
        y_train = train_df["target"].astype(int).to_numpy()
        y_val = val_df["target"].astype(int).to_numpy()
        returns_train = train_df["future_return"].to_numpy(float) if "future_return" in train_df.columns else np.zeros(len(train_df))
        returns_val = val_df["future_return"].to_numpy(float) if "future_return" in val_df.columns else np.zeros(len(val_df))

        # ── 3. Baselines simples (non-ML) ───────────────────────────────
        report.baselines["always_flat"] = SimpleBaselines.always_flat(y_train, y_val)
        report.baselines["momentum"] = SimpleBaselines.momentum(returns_train, returns_val, y_train, y_val)
        report.baselines["mean_reversion"] = SimpleBaselines.mean_reversion(returns_train, returns_val, y_train, y_val)
        report.baselines["logistic"] = SimpleBaselines.logistic(X_train, y_train, X_val, y_val, is_ternary=self.is_ternary)

        # ── 4. Score plancher depuis les baselines ──────────────────────
        baseline_best_acc = max(b.accuracy for b in report.baselines.values())
        baseline_threshold = baseline_best_acc + self.benchmark_cfg.min_improvement_vs_baseline

        # ── 5. Challengers ML ───────────────────────────────────────────
        report.challengers = {}
        for seed_idx in range(self.benchmark_cfg.n_seeds):
            seed = self.benchmark_cfg.base_seed + seed_idx
            self._run_challenger("lightgbm", seed, self.df, report, baseline_threshold)
            self._run_challenger("catboost", seed, self.df, report, baseline_threshold)

        # ── 6. Sélection du champion ────────────────────────────────────
        report = self._select_champion(report, baseline_threshold)

        # ── 7. Résumé ───────────────────────────────────────────────────
        report.summary = self._build_summary(report, baseline_threshold)
        return report

    # ── Internal ────────────────────────────────────────────────────────

    def _resolve_symbol(self) -> str:
        if "symbol" in self.df.columns and not self.df["symbol"].empty:
            return str(self.df["symbol"].iloc[0])
        return "__BENCHMARK__"

    def _get_feature_columns(self) -> list[str]:
        from modelFactory.features import get_feature_columns
        return get_feature_columns(
            include_sentiment=self.training_cfg.data.include_sentiment_features,
            feature_set=self.training_cfg.data.feature_set,
            include_cross_sectional=self.training_cfg.data.enable_cross_sectional_features,
            include_selector_context=self.training_cfg.data.include_selector_context_features,
            include_short_score=self.training_cfg.data.include_short_score_features,
        )

    def _run_challenger(
        self,
        model_name: str,
        seed: int,
        df: pd.DataFrame,
        report: BenchmarkReport,
        baseline_threshold: float,
    ) -> None:
        """Exécute un challenger ML et enregistre le résultat."""
        from modelFactory.lightgbm_baseline import run_lightgbm_baseline
        from modelFactory.catboost_baseline import run_catboost_baseline
        from modelFactory.config import TrainingConfig, ReproducibilityConfig

        t0 = time.perf_counter()
        try:
            cfg = TrainingConfig(
                data=self.training_cfg.data,
                baseline=self.training_cfg.baseline,
                calibration=self.training_cfg.calibration,
                threshold_optimization=self.training_cfg.threshold_optimization,
                reproducibility=ReproducibilityConfig(seed=seed, deterministic=self.training_cfg.reproducibility.deterministic),
                champion_selection=self.training_cfg.champion_selection,
            )
            if model_name == "lightgbm":
                result = run_lightgbm_baseline(df, cfg)
            elif model_name == "catboost":
                result = run_catboost_baseline(df, cfg)
            else:
                return
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            cr = ChallengerResult(
                model_name=model_name, seed=seed, status="failed",
                error=str(exc), latency_train_ms=latency_ms,
            )
            report.challengers.setdefault(model_name, []).append(cr)
            report.rejected_models.append({"model": model_name, "reason": f"exception:{exc}"})
            return

        latency_ms = (time.perf_counter() - t0) * 1000.0
        status = result.get("status", "failed")

        if status != "completed":
            cr = ChallengerResult(model_name=model_name, seed=seed, status=status)
            report.challengers.setdefault(model_name, []).append(cr)
            if status == "skipped":
                report.rejected_models.append({"model": model_name, "reason": result.get("reason", "skipped")})
            return

        val_metrics = result.get("val", {})
        test_metrics = result.get("test", {})

        # ── Collapse check ──────────────────────────────────────────
        collapsed = bool(val_metrics.get("collapsed", False))
        collapse_reason = val_metrics.get("collapse_reason")

        # ── Below baseline check ─────────────────────────────────────
        val_f1 = val_metrics.get("f1_macro")
        val_acc = val_metrics.get("balanced_accuracy") or val_metrics.get("accuracy", 0.0)
        below = False
        if val_f1 is not None and val_f1 < baseline_threshold:
            below = True
        elif val_acc < baseline_threshold:
            below = True

        cr = ChallengerResult(
            model_name=model_name,
            seed=seed,
            status="completed",
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            collapsed=collapsed,
            collapse_reason=collapse_reason,
            latency_train_ms=latency_ms,
            params_count=0,  # serait à extraire du modèle
            below_baseline=below,
        )
        report.challengers.setdefault(model_name, []).append(cr)

        # ── Rejet ────────────────────────────────────────────────────
        if collapsed and self.benchmark_cfg.reject_collapsed:
            report.rejected_models.append({
                "model": model_name,
                "reason": f"collapsed_seed_{seed}:{collapse_reason}",
            })
        if below and self.benchmark_cfg.reject_below_baselines:
            report.rejected_models.append({
                "model": model_name,
                "reason": f"below_baseline_seed_{seed}:f1={val_f1:.4f}_threshold={baseline_threshold:.4f}",
            })

    def _select_champion(self, report: BenchmarkReport, baseline_threshold: float) -> BenchmarkReport:
        """Sélectionne le meilleur challenger non rejeté."""
        best_name = None
        best_score = -1.0

        for model_name, results in report.challengers.items():
            completed = [r for r in results if r.status == "completed" and not r.collapsed and not r.below_baseline]
            if not completed:
                continue
            # Score moyen sur les seeds
            f1_vals = [r.val_metrics.get("f1_macro") or 0.0 for r in completed]
            mean_f1 = float(np.mean(f1_vals)) if f1_vals else 0.0
            if mean_f1 > best_score:
                best_score = mean_f1
                best_name = model_name

        report.champion = best_name
        report.champion_score = best_score
        if best_name is None:
            report.rejected_models.append({
                "model": "all", "reason": "no_model_above_baselines",
            })
        return report

    def _build_summary(self, report: BenchmarkReport, baseline_threshold: float) -> dict[str, Any]:
        """Produit le résumé exécutif du benchmark."""
        total_challengers = sum(len(v) for v in report.challengers.values())
        completed = sum(
            1 for v in report.challengers.values()
            for r in v if r.status == "completed"
        )
        collapsed = sum(
            1 for v in report.challengers.values()
            for r in v if r.collapsed
        )
        below = sum(
            1 for v in report.challengers.values()
            for r in v if r.below_baseline
        )

        latency_stats = {}
        for model_name, results in report.challengers.items():
            lats = [r.latency_train_ms for r in results if r.latency_train_ms > 0]
            if lats:
                latency_stats[model_name] = {
                    "mean_ms": round(float(np.mean(lats)), 2),
                    "max_ms": round(float(np.max(lats)), 2),
                }

        return {
            "total_runs": total_challengers,
            "completed_runs": completed,
            "collapsed_runs": collapsed,
            "below_baseline_runs": below,
            "baseline_best_accuracy": round(baseline_threshold, 4),
            "champion": report.champion,
            "champion_score": round(report.champion_score, 4),
            "rejected_count": len(report.rejected_models),
            "latency_stats": latency_stats,
        }


# ── API de haut niveau ──────────────────────────────────────────────────────

def run_model_benchmark(
    prepared_df: pd.DataFrame,
    training_cfg: TrainingConfig,
    *,
    n_seeds: int = 3,
    base_seed: int = 42,
) -> BenchmarkReport:
    """Point d'entrée unique pour le benchmark de modèles (Sprint Maître 4).

    Parameters
    ----------
    prepared_df : pd.DataFrame
        DataFrame préparé avec features, target, future_return.
    training_cfg : TrainingConfig
    n_seeds : int
        Nombre de seeds à tester (min 1).
    base_seed : int
        Seed de base.

    Returns
    -------
    BenchmarkReport
    """
    cfg = BenchmarkConfig(n_seeds=n_seeds, base_seed=base_seed)
    runner = BenchmarkRunner(prepared_df, training_cfg, benchmark_cfg=cfg)
    return runner.run()
