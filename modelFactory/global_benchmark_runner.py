"""modelFactory/global_benchmark_runner.py — BenchmarkRunner pour modèle global multi-symboles (Point 4.1).

Le ``GlobalBenchmarkRunner`` étend le protocole de benchmark au modèle global,
qui est entraîné sur un univers multi-symboles avec un split par dates
(``chrono_split_by_dates``), par opposition au split par lignes des modèles
single-symbole.

Fonctionnalités :
- Mêmes baselines (always_flat, momentum, mean_reversion) calculées par symbole
  puis agrégées
- Entraînement multi-seeds du modèle global (LightGBM/CatBoost)
- Métriques par symbole (``by_symbol``) et globales (``val``/``test``)
- Rapport compatible avec ``BenchmarkReport`` + champs multi-symboles

Usage ::

    from modelFactory.global_benchmark_runner import (
        GlobalBenchmarkRunner, GlobalBenchmarkConfig,
    )
    runner = GlobalBenchmarkRunner(symbols, training_cfg, engine=engine)
    report = runner.run()
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from modelFactory.config import TrainingConfig
from modelFactory.model_benchmark import (
    BenchmarkReport, ChallengerResult, SimpleBaselineResult, SimpleBaselines,
)

LOGGER = logging.getLogger(__name__)


# ── Config ──────────────────────────────────────────────────────────────────


@dataclass
class GlobalBenchmarkConfig:
    """Configuration du benchmark global multi-symboles.

    Étend le concept de ``BenchmarkConfig`` avec des paramètres spécifiques
    au multi-symboles : split par dates, métriques par symbole.
    """

    n_seeds: int = 2
    base_seed: int = 42
    min_improvement_vs_baseline: float = 0.01
    reject_collapsed: bool = True
    reject_below_baselines: bool = True
    cost_model_round_trip_bps: float = 16.0
    universe_run_id: str | None = None
    # ── Spécifique global ──────────────────────────────────────────
    artifact_symbol: str = "__GLOBAL__"
    model_name: str = "catboost"  # "catboost" | "lightgbm"
    artifacts_dir: Path = field(default_factory=lambda: Path("artifacts/global_benchmark"))


# ── Report ──────────────────────────────────────────────────────────────────


@dataclass
class GlobalBenchmarkReport:
    """Rapport de benchmark global multi-symboles.

    Attributes
    ----------
    symbols : list[str]
        Liste des symboles dans l'univers.
    n_seeds : int
        Nombre de seeds utilisées.
    baselines : dict[str, SimpleBaselineResult]
        Baselines agrégées (moyennes par symbole).
    challengers : dict[str, list[ChallengerResult]]
        Résultats du modèle global par seed.
    champion : str | None
        Nom du champion (toujours "global_model" s'il bat les baselines).
    champion_score : float | None
        Score du champion.
    by_symbol_baselines : dict[str, dict[str, SimpleBaselineResult]]
        Baselines par symbole pour diagnostic.
    excluded_architectures : dict[str, str]
        Architectures exclues et leurs raisons.
    """

    symbols: list[str] = field(default_factory=list)
    n_seeds: int = 1
    baselines: dict[str, SimpleBaselineResult] = field(default_factory=dict)
    challengers: dict[str, list[ChallengerResult]] = field(default_factory=dict)
    champion: str | None = None
    champion_score: float | None = None
    by_symbol_baselines: dict[str, dict[str, SimpleBaselineResult]] = field(default_factory=dict)
    excluded_architectures: dict[str, str] = field(default_factory=dict)
    rejected_models: list[dict[str, str]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    cost_model_round_trip_bps: float = 16.0
    universe_run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": list(self.symbols),
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
                        "seed": cr.seed,
                        "status": cr.status,
                        "val_metrics": cr.val_metrics,
                        "test_metrics": cr.test_metrics,
                        "collapsed": cr.collapsed,
                        "latency_train_ms": cr.latency_train_ms,
                        "latency_predict_ms": cr.latency_predict_ms,
                        "params_count": cr.params_count,
                        "memory_bytes": cr.memory_bytes,
                        "below_baseline": cr.below_baseline,
                    }
                    for cr in results
                ]
                for name, results in self.challengers.items()
            },
            "champion": self.champion,
            "champion_score": self.champion_score,
            "by_symbol_baselines": {
                sym: {
                    name: {"accuracy": b.accuracy, "action_rate": b.action_rate}
                    for name, b in baselines.items()
                }
                for sym, baselines in self.by_symbol_baselines.items()
            },
            "excluded_architectures": dict(self.excluded_architectures),
            "rejected_models": list(self.rejected_models),
            "summary": dict(self.summary),
            "cost_model_round_trip_bps": self.cost_model_round_trip_bps,
            "universe_run_id": self.universe_run_id,
        }


# ── Runner ──────────────────────────────────────────────────────────────────


class GlobalBenchmarkRunner:
    """Benchmark runner pour le modèle global multi-symboles (Point 4.1).

    Contrairement au ``BenchmarkRunner`` single-symbole, ce runner :
    - Charge les données de TOUS les symboles
    - Utilise un split par dates (``chrono_split_by_dates``)
    - Calcule les baselines par symbole puis les agrège
    - Entraîne le modèle global (LightGBM/CatBoost) sur l'univers complet
    - Produit des métriques par symbole ET globales

    Le backend du modèle global est tabulaire (LightGBM/CatBoost), identique
    aux baselines single-symbole, mais l'entraînement sur données multi-symboles
    avec features cross-sectionnelles peut capturer des relations inter-symboles.
    """

    # Architectures exclues du benchmark single-symbole — documenté ici
    EXCLUDED_FROM_SINGLE_SYMBOL: dict[str, str] = {
        "global_model": (
            "Le modèle global est entraîné sur un univers multi-symboles "
            "avec un split par dates (chrono_split_by_dates), pas par lignes. "
            "Son backend (LightGBM/CatBoost) est identique aux baselines "
            "tabulaires, mais le protocole multi-symboles nécessite ce "
            "GlobalBenchmarkRunner dédié."
        ),
    }

    def __init__(
        self,
        symbols: list[str],
        training_cfg: TrainingConfig,
        *,
        benchmark_cfg: GlobalBenchmarkConfig | None = None,
        engine: Any = None,
        data_provider: Any = None,
    ) -> None:
        """Initialise le runner.

        Parameters
        ----------
        symbols : list[str]
            Liste des symboles de l'univers.
        training_cfg : TrainingConfig
            Configuration d'entraînement complète.
        benchmark_cfg : GlobalBenchmarkConfig | None
            Configuration du benchmark global.
        engine : Any | None
            Moteur SQLAlchemy pour charger les données (via ``train_global_model``).
        data_provider : Callable | None
            Alternative à ``engine`` : une fonction ``(symbols, cfg) -> pd.DataFrame``
            qui retourne un DataFrame multi-symboles déjà préparé.
        """
        self.symbols = list(symbols)
        self.training_cfg = training_cfg
        self.benchmark_cfg = benchmark_cfg or GlobalBenchmarkConfig(
            artifacts_dir=Path(training_cfg.global_benchmark_artifacts_dir),
        )
        self.engine = engine
        self.data_provider = data_provider
        self.is_ternary = training_cfg.data.target_mode == "ternary"

    # ── Public API ──────────────────────────────────────────────────────

    def run(self) -> GlobalBenchmarkReport:
        """Exécute le benchmark global complet."""
        report = GlobalBenchmarkReport(
            symbols=list(self.symbols),
            n_seeds=self.benchmark_cfg.n_seeds,
            excluded_architectures=dict(self.EXCLUDED_FROM_SINGLE_SYMBOL),
            cost_model_round_trip_bps=self.benchmark_cfg.cost_model_round_trip_bps,
            universe_run_id=self.benchmark_cfg.universe_run_id,
        )

        # ── 1. Charger les données multi-symboles ─────────────────────
        prepared_df = self._load_multi_symbol_data()
        if prepared_df is None or prepared_df.empty:
            report.summary = {"status": "no_data", "reason": "empty_multi_symbol_df"}
            return report

        # ── 2. Baselines par symbole + agrégation ─────────────────────
        report.by_symbol_baselines = self._compute_per_symbol_baselines(prepared_df)
        report.baselines = self._aggregate_baselines(report.by_symbol_baselines)

        # ── 3. Challenger : modèle global ─────────────────────────────
        report.challengers = {}
        baseline_threshold = max(b.accuracy for b in report.baselines.values()) + self.benchmark_cfg.min_improvement_vs_baseline

        for seed_idx in range(self.benchmark_cfg.n_seeds):
            seed = self.benchmark_cfg.base_seed + seed_idx
            cr = self._run_global_challenger(seed, baseline_threshold)
            if cr is not None:
                report.challengers.setdefault("global_model", []).append(cr)

        # ── 4. Champion ──────────────────────────────────────────────
        report = self._select_champion(report, baseline_threshold)

        # ── 5. Résumé ────────────────────────────────────────────────
        report.summary = self._build_summary(report, baseline_threshold)
        return report

    # ── Internal: data loading ─────────────────────────────────────────

    def _load_multi_symbol_data(self) -> pd.DataFrame | None:
        """Charge les données multi-symboles."""
        if self.data_provider is not None:
            try:
                return self.data_provider(self.symbols, self.training_cfg)
            except Exception as exc:
                LOGGER.warning("Data provider failed: %s", exc)
                return None

        if self.engine is not None:
            try:
                from modelFactory.global_model import train_global_model as _train
                # On ne lance pas l'entraînement, juste le chargement
                # On va appeler train_global_model directement dans _run_global_challenger
                return None  # Signal: use train_global_model directly
            except ImportError:
                LOGGER.warning("Cannot import train_global_model")
                return None

        LOGGER.warning("No data provider or engine configured")
        return None

    # ── Internal: baselines ────────────────────────────────────────────

    def _compute_per_symbol_baselines(
        self, prepared_df: pd.DataFrame,
    ) -> dict[str, dict[str, SimpleBaselineResult]]:
        """Calcule les baselines simples pour chaque symbole."""
        by_symbol: dict[str, dict[str, SimpleBaselineResult]] = {}

        if "symbol" not in prepared_df.columns:
            return by_symbol

        for sym in self.symbols:
            sym_df = prepared_df[prepared_df["symbol"] == sym]
            if len(sym_df) < 50:
                continue

            sym_df = sym_df.sort_values("date" if "date" in sym_df.columns else sym_df.index)

            if "target" not in sym_df.columns:
                continue

            y = sym_df["target"].astype(int).to_numpy()
            n = len(y)
            split_idx = int(n * 0.7)
            y_train = y[:split_idx]
            y_val = y[split_idx:]

            returns = sym_df["future_return"].to_numpy(float) if "future_return" in sym_df.columns else np.zeros(n)
            returns_train = returns[:split_idx]
            returns_val = returns[split_idx:]

            sym_baselines: dict[str, SimpleBaselineResult] = {}
            sym_baselines["always_flat"] = SimpleBaselines.always_flat(y_train, y_val)
            sym_baselines["momentum"] = SimpleBaselines.momentum(returns_train, returns_val, y_train, y_val)
            sym_baselines["mean_reversion"] = SimpleBaselines.mean_reversion(returns_train, returns_val, y_train, y_val)

            by_symbol[sym] = sym_baselines

        return by_symbol

    @staticmethod
    def _aggregate_baselines(
        by_symbol: dict[str, dict[str, SimpleBaselineResult]],
    ) -> dict[str, SimpleBaselineResult]:
        """Agrège les baselines par symbole en une valeur moyenne."""
        aggregated: dict[str, SimpleBaselineResult] = {}
        baseline_names = {"always_flat", "momentum", "mean_reversion"}

        for name in baseline_names:
            accs = []
            action_rates = []
            for sym_baselines in by_symbol.values():
                if name in sym_baselines:
                    accs.append(sym_baselines[name].accuracy)
                    action_rates.append(sym_baselines[name].action_rate)

            if accs:
                aggregated[name] = SimpleBaselineResult(
                    name=name,
                    accuracy=float(np.mean(accs)),
                    f1_macro=None,
                    balanced_accuracy=None,
                    action_rate=float(np.mean(action_rates)),
                )

        return aggregated

    # ── Internal: challenger ───────────────────────────────────────────

    def _run_global_challenger(
        self, seed: int, baseline_threshold: float,
    ) -> ChallengerResult | None:
        """Exécute le challenger global (LightGBM/CatBoost multi-symboles)."""
        from modelFactory.config import ReproducibilityConfig

        t0 = time.perf_counter()

        # Construire une config avec le seed demandé
        cfg = TrainingConfig(
            data=self.training_cfg.data,
            baseline=self.training_cfg.baseline,
            calibration=self.training_cfg.calibration,
            threshold_optimization=self.training_cfg.threshold_optimization,
            reproducibility=ReproducibilityConfig(
                seed=seed,
                deterministic=self.training_cfg.reproducibility.deterministic,
            ),
            champion_selection=self.training_cfg.champion_selection,
            global_model=self.training_cfg.global_model,
            artifacts_dir=self.training_cfg.artifacts_dir,
            benchmark_artifacts_dir=self.training_cfg.benchmark_artifacts_dir,
            global_benchmark_artifacts_dir=self.training_cfg.global_benchmark_artifacts_dir,
            catboost_artifacts_dir=self.training_cfg.catboost_artifacts_dir,
            batch_id=self.training_cfg.batch_id,
        )

        try:
            if self.engine is not None:
                # Utiliser train_global_model directement (charge depuis MySQL)
                from modelFactory.global_model import train_global_model

                artifacts_dir = self.benchmark_cfg.artifacts_dir / f"seed_{seed}"
                result = train_global_model(
                    symbols=self.symbols,
                    cfg=cfg,
                    artifacts_dir=artifacts_dir,
                    engine=self.engine,
                )
            elif self.data_provider is not None:
                # Utiliser le data_provider + entraînement simplifié
                prepared_df = self.data_provider(self.symbols, cfg)
                if prepared_df is None or prepared_df.empty:
                    return ChallengerResult(
                        model_name="global_model", seed=seed,
                        status="skipped", error="data_provider_returned_empty",
                    )
                result = self._train_on_prepared_df(prepared_df, cfg, seed)
            else:
                return ChallengerResult(
                    model_name="global_model", seed=seed,
                    status="skipped", error="no_engine_or_data_provider",
                )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            LOGGER.warning("Global model training failed (seed=%d): %s", seed, exc)
            return ChallengerResult(
                model_name="global_model", seed=seed,
                status="failed", error=str(exc),
                latency_train_ms=latency_ms,
            )

        latency_train_ms = (time.perf_counter() - t0) * 1000.0
        status = result.get("status", "failed")

        if status != "completed":
            return ChallengerResult(
                model_name="global_model", seed=seed, status=status,
                error=result.get("reason", "unknown"),
                latency_train_ms=latency_train_ms,
            )

        val_metrics = result.get("val", {})
        test_metrics = result.get("test", {})

        collapsed = bool(val_metrics.get("collapsed", False))
        collapse_reason = val_metrics.get("collapse_reason")

        val_acc = val_metrics.get("balanced_accuracy") or val_metrics.get("accuracy", 0.0)
        below = val_acc < baseline_threshold

        # ── Métriques de complexité ──────────────────────────────────
        params_count = 0
        memory_bytes = 0
        artifact_paths = result.get("artifact_paths", {}) or {}
        model_path = artifact_paths.get("model_path")
        if model_path:
            try:
                import os
                memory_bytes = os.path.getsize(str(model_path))
            except OSError:
                pass
            # Extraire params_count si backend connu
            backend = result.get("backend_model_name", "")
            if backend == "lightgbm":
                try:
                    from modelFactory.model_benchmark import _count_lightgbm_leaves
                    import lightgbm as lgb
                    booster = lgb.Booster(model_file=str(model_path))
                    params_count = _count_lightgbm_leaves(booster.dump_model())
                except Exception:
                    pass
            elif backend == "catboost":
                try:
                    from catboost import CatBoostClassifier
                    cb = CatBoostClassifier()
                    cb.load_model(str(model_path))
                    params_count = cb.tree_count_ * getattr(cb, 'get_param', lambda _: 6)('depth')
                except Exception:
                    pass

        latency_predict_ms = float(result.get("latency_predict_ms", 0.0))

        # ── Rejet ────────────────────────────────────────────────────
        if collapsed and self.benchmark_cfg.reject_collapsed:
            self._rejected.append({
                "model": "global_model",
                "reason": f"collapsed_seed_{seed}:{collapse_reason}",
            })

        return ChallengerResult(
            model_name="global_model",
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

    def _train_on_prepared_df(
        self, df: pd.DataFrame, cfg: TrainingConfig, seed: int,
    ) -> dict[str, Any]:
        """Entraîne un modèle global sur un DataFrame déjà préparé (sans DB).

        Version simplifiée de ``train_global_model`` pour les tests et
        les data_providers custom.
        """
        from modelFactory.dataset import chrono_split_by_dates
        from modelFactory.global_model import _build_global_estimator
        from modelFactory.tabular_baseline import compute_tabular_metrics

        is_ternary = cfg.data.target_mode == "ternary"
        backend_name, model = _build_global_estimator(cfg, resolved_seed=seed)

        # Feature columns
        from modelFactory.features import get_feature_columns
        feature_cols = get_feature_columns(
            include_sentiment=cfg.data.include_sentiment_features,
            feature_set=getattr(cfg.data, "feature_set", None),
            include_cross_sectional=getattr(cfg.data, "enable_cross_sectional_features", False),
            include_screener_scores=cfg.data.include_screener_scores,
            include_short_score=cfg.data.include_short_score_features,
        )
        available_cols = [c for c in feature_cols if c in df.columns]
        if not available_cols:
            return {"status": "skipped", "reason": "no_feature_columns"}

        # Drop NaN
        work_df = df.dropna(subset=available_cols + ["target"])
        if len(work_df) < 100:
            return {"status": "skipped", "reason": f"insufficient_data:{len(work_df)}"}

        # Split by dates
        try:
            split = chrono_split_by_dates(
                work_df,
                train_ratio=cfg.data.train_ratio,
                val_ratio=cfg.data.val_ratio,
                forecast_horizon=getattr(cfg.data, "forecast_horizon", 1),
            )
        except Exception:
            return {"status": "failed", "reason": "split_error"}

        train_df, val_df, test_df = split.train, split.val, split.test
        if len(train_df) < 50 or len(val_df) < 20:
            return {"status": "skipped", "reason": "insufficient_split_data"}

        X_train = train_df[available_cols].to_numpy(float)
        y_train = train_df["target"].astype(int).to_numpy()
        X_val = val_df[available_cols].to_numpy(float)
        y_val = val_df["target"].astype(int).to_numpy()
        X_test = test_df[available_cols].to_numpy(float)
        y_test = test_df["target"].astype(int).to_numpy()

        # Shift ternary targets
        if is_ternary:
            y_train = y_train + 1
            y_val = y_val + 1
            y_test = y_test + 1

        # Train
        model.fit(X_train, y_train)

        # Predict
        val_proba = model.predict_proba(X_val)
        test_proba = model.predict_proba(X_test)

        # Metrics
        val_metrics = compute_tabular_metrics(
            labels=y_val, proba=val_proba[:, -1] if val_proba.ndim > 1 and val_proba.shape[1] > 1 else val_proba,
            future_returns=val_df["future_return"].to_numpy(float) if "future_return" in val_df.columns else np.zeros(len(val_df)),
            decision_threshold=0.5,
            is_ternary=is_ternary,
        )
        test_metrics = compute_tabular_metrics(
            labels=y_test, proba=test_proba[:, -1] if test_proba.ndim > 1 and test_proba.shape[1] > 1 else test_proba,
            future_returns=test_df["future_return"].to_numpy(float) if "future_return" in test_df.columns else np.zeros(len(test_df)),
            decision_threshold=0.5,
            is_ternary=is_ternary,
        )

        # By-symbol metrics
        by_symbol: dict[str, dict[str, Any]] = {}
        if "symbol" in test_df.columns:
            for sym in self.symbols:
                sym_mask = test_df["symbol"] == sym
                if sym_mask.sum() < 10:
                    continue
                sym_y = y_test[sym_mask]
                sym_proba = test_proba[sym_mask]
                sym_metrics = compute_tabular_metrics(
                    labels=sym_y,
                    proba=sym_proba[:, -1] if sym_proba.ndim > 1 and sym_proba.shape[1] > 1 else sym_proba,
                    future_returns=test_df.loc[sym_mask, "future_return"].to_numpy(float) if "future_return" in test_df.columns else np.zeros(sym_mask.sum()),
                    decision_threshold=0.5,
                    is_ternary=is_ternary,
                )
                by_symbol[sym] = {"test": sym_metrics, "status": "completed"}

        return {
            "status": "completed",
            "model_name": "global_model",
            "backend_model_name": backend_name,
            "seed": seed,
            "val": val_metrics,
            "test": test_metrics,
            "by_symbol": by_symbol,
            "feature_columns": available_cols,
            "artifact_paths": {},
        }

    # ── Internal: selection ────────────────────────────────────────────

    def _select_champion(
        self, report: GlobalBenchmarkReport, baseline_threshold: float,
    ) -> GlobalBenchmarkReport:
        """Sélectionne le champion parmi les challengers non rejetés."""
        best_score = -1.0
        best_name = None

        for model_name, results in report.challengers.items():
            completed = [
                r for r in results
                if r.status == "completed" and not r.collapsed and not r.below_baseline
            ]
            if not completed:
                continue
            acc_vals = [r.val_metrics.get("accuracy", 0.0) for r in completed]
            mean_acc = float(np.mean(acc_vals)) if acc_vals else 0.0
            if mean_acc > best_score:
                best_score = mean_acc
                best_name = model_name

        report.champion = best_name
        report.champion_score = best_score if best_name else None
        return report

    def _build_summary(
        self, report: GlobalBenchmarkReport, baseline_threshold: float,
    ) -> dict[str, Any]:
        """Construit le résumé textuel du benchmark."""
        summary: dict[str, Any] = {
            "symbols_count": len(self.symbols),
            "n_seeds": self.benchmark_cfg.n_seeds,
            "baseline_best": max((b.accuracy for b in report.baselines.values()), default=0.0),
            "baseline_threshold": baseline_threshold,
            "champion": report.champion,
            "champion_score": report.champion_score,
            "rejected_count": len(report.rejected_models),
        }
        if report.challengers.get("global_model"):
            completed = [r for r in report.challengers["global_model"] if r.status == "completed"]
            if completed:
                avg_acc = float(np.mean([r.val_metrics.get("accuracy", 0.0) for r in completed]))
                summary["global_model_avg_accuracy"] = avg_acc
                summary["global_model_beats_baselines"] = avg_acc > baseline_threshold
        return summary

    # Instance-level rejected list (reset per run)
    _rejected: list[dict[str, str]] = []
