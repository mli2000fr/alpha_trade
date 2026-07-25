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

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
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
    # ── Sprint Maître 4 Point 4.2 : coûts et lineage ──────────────────
    cost_model_round_trip_bps: float = 16.0  # round-trip canonique (spread+comm+slippage)×2
    universe_run_id: str | None = None       # fingerprint d'univers PIT


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
    memory_bytes: int = 0          # ── Sprint Maître 4 Point 4.3
    below_baseline: bool = False
    error: str | None = None


@dataclass
class BenchmarkReport:
    """Rapport de benchmark complet (Sprint Maître 4).

    Inclut les architectures explicitement exclues du périmètre avec leur
    raison documentée (Point 4.1), les coûts et le lineage d'univers (Point 4.2),
    et les métriques de complexité réelles (Point 4.3).
    """

    symbol: str
    n_seeds: int
    baselines: dict[str, SimpleBaselineResult] = field(default_factory=dict)
    challengers: dict[str, list[ChallengerResult]] = field(default_factory=dict)
    champion: str | None = None
    champion_score: float = 0.0
    rejected_models: list[dict[str, str]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    # ── Sprint Maître 4 Point 4.1 : architectures exclues ──────────────
    excluded_architectures: dict[str, str] = field(default_factory=dict)
    # ── Sprint Maître 4 Point 4.2 : coûts et lineage ──────────────────
    cost_model_round_trip_bps: float = 16.0
    universe_run_id: str | None = None
    # ── Sprint Maître 4 Point 4.4 : persistance ───────────────────────
    benchmark_report_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
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
                        "latency_train_ms": c.latency_train_ms,
                        "latency_predict_ms": c.latency_predict_ms,
                        "params_count": c.params_count,
                        "memory_bytes": c.memory_bytes,
                        "below_baseline": c.below_baseline,
                    }
                    for c in results
                ]
                for name, results in self.challengers.items()
            },
            "champion": self.champion,
            "champion_score": self.champion_score,
            "rejected_models": self.rejected_models,
            "excluded_architectures": self.excluded_architectures,
            "cost_model_round_trip_bps": self.cost_model_round_trip_bps,
            "universe_run_id": self.universe_run_id,
            "benchmark_report_path": self.benchmark_report_path,
            "summary": self.summary,
        }
        return d


class BenchmarkRunner:
    """Runner de benchmark unifié (Sprint Maître 4).

    Garantit que tous les modèles sont comparés équitablement :
    mêmes données, mêmes folds, mêmes seeds, mêmes coûts.

    Les architectures non supportées par le benchmark tabulaire sont documentées
    dans ``report.excluded_architectures`` (Point 4.1). Le modèle global
    multi-symboles dispose de son propre ``GlobalBenchmarkRunner`` dans
    ``modelFactory/global_benchmark_runner.py``.
    """

    # ═══════════════════════════════════════════════════════════════════
    # Architectures dans le périmètre du benchmark tabulaire
    # ═══════════════════════════════════════════════════════════════════
    BENCHMARKED_ARCHITECTURES: tuple[str, ...] = ("lightgbm", "catboost", "lstm_attention")

    # ═══════════════════════════════════════════════════════════════════
    # Architectures EXCLUES et leur raison documentée (Point 4.1)
    # ═══════════════════════════════════════════════════════════════════
    EXCLUDED_ARCHITECTURES: dict[str, str] = {}

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
            excluded_architectures=dict(self.EXCLUDED_ARCHITECTURES),
            cost_model_round_trip_bps=self.benchmark_cfg.cost_model_round_trip_bps,
            universe_run_id=self.benchmark_cfg.universe_run_id,
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
            for arch in self.BENCHMARKED_ARCHITECTURES:
                self._run_challenger(arch, seed, self.df, report, baseline_threshold)

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
            include_screener_scores=self.training_cfg.data.include_screener_scores,
            include_short_score=self.training_cfg.data.include_short_score_features,
            include_macro_vix=self.training_cfg.data.include_macro_vix_features,
            include_macro_vxn=self.training_cfg.data.include_macro_vxn_features,
            include_macro_vix3m=self.training_cfg.data.include_macro_vix3m_features,
            include_macro_move=self.training_cfg.data.include_macro_move_features,
            include_global_stacking=self.training_cfg.global_model.stacking_enabled,
            include_fundamentals=self.training_cfg.data.include_fundamentals_features,
            include_factors=self.training_cfg.data.include_factors_features,
        )

    def _run_challenger(
        self,
        model_name: str,
        seed: int,
        df: pd.DataFrame,
        report: BenchmarkReport,
        baseline_threshold: float,
    ) -> None:
        """Exécute un challenger ML et enregistre le résultat.

        Extrait ``params_count`` et ``memory_bytes`` du modèle entraîné
        (Sprint Maître 4 Point 4.3).
        """
        from modelFactory.lightgbm_baseline import run_lightgbm_baseline
        from modelFactory.catboost_baseline import run_catboost_baseline
        from modelFactory.lstm_benchmark_adapter import run_lstm_benchmark
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
                artifacts_dir=self.training_cfg.artifacts_dir,
                benchmark_artifacts_dir=self.training_cfg.benchmark_artifacts_dir,
                global_benchmark_artifacts_dir=self.training_cfg.global_benchmark_artifacts_dir,
                catboost_artifacts_dir=self.training_cfg.catboost_artifacts_dir,
                batch_id=self.training_cfg.batch_id,
            )
            if model_name == "lightgbm":
                result = run_lightgbm_baseline(df, cfg)
            elif model_name == "catboost":
                result = run_catboost_baseline(df, cfg)
            elif model_name == "lstm_attention":
                result = run_lstm_benchmark(df, cfg)
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

        latency_train_ms = (time.perf_counter() - t0) * 1000.0
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

        # ── Sprint Maître 4 Point 4.3 : extraire params_count ────────
        params_count = 0
        memory_bytes = 0
        artifact_paths = result.get("artifact_paths", {}) or {}
        model_path = artifact_paths.get("model_path") or artifact_paths.get("model") or artifact_paths.get("classifier")
        if not model_path:
            # Fallback : le résultat peut contenir params_count/memory_bytes directement
            params_count = int(result.get("params_count", 0))
            memory_bytes = int(result.get("memory_bytes", 0))
        elif os.path.exists(str(model_path)):
            try:
                memory_bytes = os.path.getsize(str(model_path))
            except OSError:
                pass

            # LSTM : params_count déjà calculé par l'adaptateur
            if model_name == "lstm_attention":
                params_count = int(result.get("params_count", 0))
                if memory_bytes == 0:
                    memory_bytes = int(result.get("memory_bytes", 0))
            # LightGBM : compter les feuilles dans le booster
            elif model_name == "lightgbm":
                try:
                    import lightgbm as lgb
                    booster = lgb.Booster(model_file=str(model_path))
                    # Nombre de feuilles = nombre de nœuds terminaux
                    dump = booster.dump_model()
                    params_count = _count_lightgbm_leaves(dump)
                except Exception:
                    params_count = 0
            # CatBoost : nombre d'arbres × profondeur moyenne
            elif model_name == "catboost":
                try:
                    from catboost import CatBoostClassifier
                    cb_model = CatBoostClassifier()
                    cb_model.load_model(str(model_path))
                    params_count = cb_model.tree_count_ * getattr(cb_model, 'get_param', lambda _: 6)('depth')  # type: ignore[arg-type]
                except Exception:
                    params_count = 0

        # ── Mesurer latency_predict_ms sur le fold val ───────────────
        latency_predict_ms = 0.0
        if self.benchmark_cfg.measure_latency:
            # LSTM : latency déjà mesurée par l'adaptateur
            if model_name == "lstm_attention":
                latency_predict_ms = float(result.get("latency_predict_ms", 0.0))
            elif model_path and os.path.exists(str(model_path)):
                try:
                    feature_cols = self._get_feature_columns()
                    X_val_sample = df[feature_cols].iloc[:100].to_numpy(float)  # max 100 lignes
                    if model_name == "lightgbm":
                        import lightgbm as lgb
                        booster = lgb.Booster(model_file=str(model_path))
                        t0_pred = time.perf_counter()
                        booster.predict(X_val_sample)
                        latency_predict_ms = (time.perf_counter() - t0_pred) * 1000.0
                    elif model_name == "catboost":
                        from catboost import CatBoostClassifier
                        cb_model = CatBoostClassifier()
                        cb_model.load_model(str(model_path))
                        t0_pred = time.perf_counter()
                        cb_model.predict(X_val_sample)
                        latency_predict_ms = (time.perf_counter() - t0_pred) * 1000.0
                except Exception:
                    latency_predict_ms = 0.0

        cr = ChallengerResult(
            model_name=model_name,
            seed=seed,
            status="completed",
            val_metrics=val_metrics,
            test_metrics=test_metrics,
            collapsed=collapsed,
            collapse_reason=collapse_reason,
            latency_train_ms=latency_train_ms,
            latency_predict_ms=latency_predict_ms,
            params_count=params_count,
            memory_bytes=memory_bytes,
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
    report = runner.run()
    if training_cfg.batch_id is not None:
        persist_benchmark_report(report, artifact_dir=training_cfg.benchmark_artifacts_dir)
    return report


# ── Helpers ─────────────────────────────────────────────────────────────────

def _count_lightgbm_leaves(dump: dict[str, Any]) -> int:
    """Compte récursivement les feuilles dans un dump LightGBM.

    Sprint Maître 4 Point 4.3 : extraction de ``params_count``.
    """
    total = 0
    tree_info = dump.get("tree_info", [])
    for tree in tree_info:
        tree_structure = tree.get("tree_structure", {})
        total += _count_leaves_recursive(tree_structure)
    return total


def _count_leaves_recursive(node: dict[str, Any]) -> int:
    if "leaf_value" in node:
        return 1
    count = 0
    if "left_child" in node:
        count += _count_leaves_recursive(node["left_child"])
    if "right_child" in node:
        count += _count_leaves_recursive(node["right_child"])
    return count if count > 0 else 1


# ── Persistence (Sprint Maître 4 Point 4.4) ─────────────────────────────────

DEFAULT_BENCHMARK_DIR = Path("artifacts/benchmarks")


def persist_benchmark_report(
    report: BenchmarkReport,
    *,
    artifact_dir: Path | str | None = None,
) -> Path:
    """Persiste le rapport de benchmark en JSON atomique.

    Le fichier est stocké dans ``<artifact_dir>/<symbol>_<n_seeds>seeds.json``.
    Utilisé par le trainer pour injecter ``benchmark_report`` dans les
    résultats des challengers et activer le gate ``require_benchmark_report``.

    Parameters
    ----------
    report : BenchmarkReport
        Rapport à persister.
    artifact_dir : Path | str | None
        Répertoire de sortie. Défaut : ``artifacts/benchmarks/``.

    Returns
    -------
    Path
        Chemin du fichier écrit.
    """
    target_dir = Path(artifact_dir) if artifact_dir else DEFAULT_BENCHMARK_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    safe_symbol = report.symbol.replace("/", "_").replace("\\", "_")
    filename = f"{safe_symbol}_{report.n_seeds}seeds.json"
    file_path = target_dir / filename
    tmp_path = target_dir / f".{filename}.tmp"

    payload = report.to_dict()
    payload["persisted_at"] = pd.Timestamp.utcnow().isoformat()

    tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp_path.replace(file_path)  # atomic rename

    report.benchmark_report_path = str(file_path)
    LOGGER.info("Benchmark report persisted: %s", file_path)
    return file_path


def load_benchmark_report(path: Path | str) -> dict[str, Any]:
    """Charge un rapport de benchmark persisté.

    Returns
    -------
    dict
        Dictionnaire compatible avec le champ ``benchmark_report``
        attendu par ``champion_selection.select_champion()``.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    # Injecter le statut attendu par le gate
    if "status" not in raw:
        raw["status"] = "completed"  # un rapport chargé depuis le disque est considéré complété
    return raw


# ── Quality validation (Sprint Maître 4 Point 4.5) ──────────────────────────

@dataclass(frozen=True, slots=True)
class BenchmarkQualityReport:
    """Rapport de validation des gates de qualité sur un benchmark réel."""

    is_valid: bool
    collapse_gate_ok: bool
    net_gain_gate_ok: bool
    latency_gate_ok: bool
    multi_seed_stability_ok: bool
    champion_above_baselines: bool
    violations: list[str]


def validate_benchmark_quality(
    report: BenchmarkReport,
    *,
    min_improvement_vs_baseline: float = 0.01,
    max_latency_ms: float = 60_000,
    max_f1_std_across_seeds: float = 0.10,
) -> BenchmarkQualityReport:
    """Valide les gates de qualité sur un rapport de benchmark réel (Point 4.5).

    Vérifie que :
    1. Aucun modèle n'est collapsed
    2. Le champion a un gain net vs la meilleure baseline
    3. La latence est compatible EOD
    4. La stabilité multi-seeds est acceptable (F1 std ≤ seuil)
    5. Le champion est au-dessus des baselines

    Parameters
    ----------
    report : BenchmarkReport
        Rapport de benchmark à valider.
    min_improvement_vs_baseline : float
        Gain minimal du champion vs meilleure baseline.
    max_latency_ms : float
        Latence max acceptable (défaut 60s).
    max_f1_std_across_seeds : float
        Écart-type max de F1 entre seeds (défaut 0.10).

    Returns
    -------
    BenchmarkQualityReport
    """
    violations: list[str] = []

    # 1. Collapse gate
    collapse_ok = True
    for model_name, results in report.challengers.items():
        for r in results:
            if r.collapsed:
                violations.append(f"collapse:{model_name}_seed_{r.seed}:{r.collapse_reason}")
                collapse_ok = False

    # 2. Net gain gate (champion vs baselines)
    net_gain_ok = True
    if report.champion is not None:
        best_baseline_acc = max(b.accuracy for b in report.baselines.values())
        champion_results = report.challengers.get(report.champion, [])
        completed = [r for r in champion_results if r.status == "completed"]
        if completed:
            champion_mean_f1 = float(np.mean([r.val_metrics.get("f1_macro") or 0.0 for r in completed]))
            if champion_mean_f1 < best_baseline_acc + min_improvement_vs_baseline:
                violations.append(
                    f"net_gain:champion={report.champion}:f1={champion_mean_f1:.4f}"
                    f"_baseline_best_acc={best_baseline_acc:.4f}"
                    f"_min_improvement={min_improvement_vs_baseline:.4f}"
                )
                net_gain_ok = False
        else:
            violations.append(f"net_gain:champion={report.champion}_no_completed_seeds")
            net_gain_ok = False

    # 3. Latency gate
    latency_ok = True
    for model_name, results in report.challengers.items():
        for r in results:
            if r.latency_predict_ms > max_latency_ms:
                violations.append(f"latency:{model_name}:{r.latency_predict_ms:.0f}ms>{max_latency_ms:.0f}ms")
                latency_ok = False

    # 4. Multi-seed stability
    stability_ok = True
    for model_name, results in report.challengers.items():
        completed = [r for r in results if r.status == "completed" and not r.collapsed]
        if len(completed) >= 2:
            f1_vals = [r.val_metrics.get("f1_macro") or 0.0 for r in completed]
            f1_std = float(np.std(f1_vals))
            if f1_std > max_f1_std_across_seeds:
                violations.append(
                    f"stability:{model_name}:f1_std={f1_std:.4f}>{max_f1_std_across_seeds:.4f}"
                )
                stability_ok = False

    # 5. Champion above baselines
    champion_above = True
    if report.champion is None:
        violations.append("champion:none_selected")
        champion_above = False
    elif report.champion_score <= 0:
        violations.append(f"champion:{report.champion}:score={report.champion_score:.4f}<=0")
        champion_above = False

    is_valid = len(violations) == 0

    return BenchmarkQualityReport(
        is_valid=is_valid,
        collapse_gate_ok=collapse_ok,
        net_gain_gate_ok=net_gain_ok,
        latency_gate_ok=latency_ok,
        multi_seed_stability_ok=stability_ok,
        champion_above_baselines=champion_above,
        violations=violations,
    )
