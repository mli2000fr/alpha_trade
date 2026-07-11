"""Sprint S5 — Orchestrateur du pipeline quotidien Alpha Trade.

Implémentation **pure Python** sans aucune dépendance externe. Pour activer
une intégration Prefect, installer ``prefect>=2`` et exécuter avec
``ALPHA_TRADE_USE_PREFECT=1`` dans l'environnement.

Les décorateurs ``@flow`` et ``@task`` sont transparents (pass-through) si
Prefect n'est pas disponible, garantissant la portabilité CI/Windows.

Usage batch::

    python -m flows.daily_pipeline --date 2026-05-17 --account-id paper1

Usage programmatique::

    from flows.daily_pipeline import daily_pipeline
    result = daily_pipeline(date=date(2026, 5, 17), account_id="paper1")
    print(result.status)   # "OK" ou "PARTIAL" ou "FAILED"
    print(result.steps)    # {step: StepResult, ...}
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from common.config_loader import override_config_path

LOGGER = logging.getLogger("flows.daily_pipeline")

# ---------------------------------------------------------------------------
# Intégration Prefect opt-in
# ---------------------------------------------------------------------------

_USE_PREFECT = False

try:
    import os as _os

    if _os.environ.get("ALPHA_TRADE_USE_PREFECT", "").strip() == "1":
        from prefect import flow as _pf_flow  # type: ignore[import-not-found]
        from prefect import task as _pf_task  # type: ignore[import-not-found]

        _USE_PREFECT = True
        LOGGER.info("Prefect détecté — décorateurs @flow/@task Prefect actifs.")
    else:
        raise ImportError("Prefect désactivé par variable d'environnement.")
except ImportError:
    # Fallback : décorateurs transparents
    def _pf_flow(fn: Callable | None = None, **_kw: Any) -> Any:  # type: ignore[misc]  # noqa: E302
        if fn is not None:
            return fn
        return lambda f: f

    def _pf_task(fn: Callable | None = None, **_kw: Any) -> Any:  # type: ignore[misc]
        if fn is not None:
            return fn
        return lambda f: f


def flow(fn: Callable | None = None, **kw: Any) -> Any:
    """Décorateur @flow (Prefect ou pass-through)."""
    return _pf_flow(fn, **kw) if _USE_PREFECT else (_pf_flow(fn, **kw) if fn else lambda f: f)


def task(fn: Callable | None = None, **kw: Any) -> Any:
    """Décorateur @task (Prefect ou pass-through)."""
    return _pf_task(fn, **kw) if _USE_PREFECT else (_pf_task(fn, **kw) if fn else lambda f: f)


# ---------------------------------------------------------------------------
# Métriques pipeline (opt-in via common.metrics)
# ---------------------------------------------------------------------------

try:
    from common.metrics import (
        selections_count as _selections_count,
        pipeline_steps_total as _steps_total,
        pipeline_duration_seconds as _duration,
    )

    _METRICS_OK = True
except Exception:  # pragma: no cover
    _METRICS_OK = False

    class _Noop:
        def labels(self, *_a: Any, **_kw: Any) -> "_Noop":
            return self

        def inc(self, *_a: Any, **_kw: Any) -> None:
            pass

        def set(self, *_a: Any, **_kw: Any) -> None:
            pass

        def observe(self, *_a: Any, **_kw: Any) -> None:
            pass

    _steps_total = _Noop()  # type: ignore[assignment]
    _duration = _Noop()  # type: ignore[assignment]
    _selections_count = _Noop()  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Dataclasses de résultat
# ---------------------------------------------------------------------------


@dataclass
class StepResult:
    """Résultat d'une étape pipeline."""

    step: str
    status: str  # "OK" | "SKIPPED" | "FAILED"
    duration_seconds: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FlowResult:
    """Résultat complet d'un run du pipeline quotidien."""

    account_id: str
    run_date: str
    started_at: str
    finished_at: str
    duration_seconds: float
    status: str  # "OK" | "PARTIAL" | "FAILED"
    steps: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Étapes du pipeline (importées lazy pour éviter les import loops)
# ---------------------------------------------------------------------------


def _safe_import_step(module_path: str, fn_name: str) -> Callable | None:
    """Import paresseux d'une fonction d'étape. Retourne None si non disponible."""
    try:
        import importlib

        mod = importlib.import_module(module_path)
        return getattr(mod, fn_name, None)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Import %s.%s impossible: %s", module_path, fn_name, exc)
        return None


def _run_step(
    step_name: str,
    fn: Callable | None,
    *args: Any,
    **kwargs: Any,
) -> StepResult:
    """Exécute une étape pipeline en capturant erreurs et métriques."""
    t0 = time.perf_counter()
    if fn is None:
        LOGGER.info("[%s] étape non disponible — SKIPPED", step_name)
        return StepResult(step=step_name, status="SKIPPED", duration_seconds=0.0)
    try:
        LOGGER.info("[%s] démarrage …", step_name)
        result = fn(*args, **kwargs) or {}
        elapsed = time.perf_counter() - t0
        _steps_total.labels(step=step_name, status="OK").inc()
        _duration.labels(step=step_name).observe(elapsed)
        LOGGER.info("[%s] terminé en %.2fs", step_name, elapsed)
        return StepResult(
            step=step_name,
            status="OK",
            duration_seconds=round(elapsed, 3),
            metadata=result if isinstance(result, dict) else {},
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - t0
        _steps_total.labels(step=step_name, status="ERROR").inc()
        _duration.labels(step=step_name).observe(elapsed)
        LOGGER.error("[%s] ÉCHEC en %.2fs : %s", step_name, elapsed, exc, exc_info=True)
        return StepResult(
            step=step_name,
            status="FAILED",
            duration_seconds=round(elapsed, 3),
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Pipeline quotidien
# ---------------------------------------------------------------------------

#: Séquence ordonnée des étapes du pipeline quotidien.
PIPELINE_STEPS: tuple[tuple[str, str, str], ...] = (
    # (step_name, module_path, function_name)
    ("import_bars",  "dataIntegrityEngine.import_bars",  "run_import"),
    ("sanitizer",    "dataIntegrityEngine.sanitizer",    "run_sanitizer"),
    ("screener",     "screener.pipeline",                "run_screener"),
    ("selector",     "selector.pipeline",                "run_selector"),
    ("ml_predictor", "modelFactory.predictor",           "run_predictions"),
)


def daily_pipeline(
    run_date: date,
    account_id: str,
    *,
    steps_override: tuple[tuple[str, str, str], ...] | None = None,
    dry_run: bool = False,
    config_path: str | Path | None = None,
) -> FlowResult:
    """Exécute le pipeline quotidien complet pour un compte donné.

    Args:
        run_date: Date de traitement (point-in-time).
        account_id: Identifiant du compte (ex. ``"paper1"``).
        steps_override: Surcharger la séquence d'étapes (pour tests).
        dry_run: Si True, skip toutes les étapes (rapport vide).
        config_path: Chemin YAML alternatif à appliquer à tout le process
            pipeline (ex. candidate finale R13a) via override global.

    Returns:
        :class:`FlowResult` avec le statut global et les résultats par étape.
    """
    started = datetime.now(timezone.utc)
    steps_config = steps_override if steps_override is not None else PIPELINE_STEPS
    step_results: dict[str, StepResult] = {}
    errors: list[str] = []

    LOGGER.info(
        "=== Pipeline quotidien démarré (date=%s, account=%s, dry_run=%s) ===",
        run_date,
        account_id,
        dry_run,
    )
    if config_path is not None:
        LOGGER.info("Pipeline quotidien: override config actif -> %s", config_path)

    with override_config_path(config_path):
        for step_name, module_path, fn_name in steps_config:
            if dry_run:
                step_results[step_name] = StepResult(step=step_name, status="SKIPPED")
                continue

            fn = _safe_import_step(module_path, fn_name)
            result = _run_step(step_name, fn, run_date, account_id)
            step_results[step_name] = result

            if result.status == "FAILED":
                errors.append(f"{step_name}: {result.error}")

    # Mise à jour jauge candidats si disponible depuis le résultat screener
    screener_result = step_results.get("screener")
    if screener_result and screener_result.status == "OK":
        n = screener_result.metadata.get("selections_count", 0)
        try:
            _selections_count.set(n)
        except Exception:  # pragma: no cover
            pass

    finished = datetime.now(timezone.utc)
    elapsed = round((finished - started).total_seconds(), 3)

    failed_count = sum(1 for r in step_results.values() if r.status == "FAILED")
    skipped_count = sum(1 for r in step_results.values() if r.status == "SKIPPED")
    total = len(step_results)

    if failed_count == 0 and skipped_count == 0:
        global_status = "OK"
    elif failed_count == total:
        global_status = "FAILED"
    elif failed_count > 0:
        global_status = "PARTIAL"
    else:
        global_status = "SKIPPED"

    LOGGER.info(
        "=== Pipeline terminé en %.2fs — status=%s (%d/%d OK) ===",
        elapsed,
        global_status,
        total - failed_count - skipped_count,
        total,
    )

    return FlowResult(
        account_id=account_id,
        run_date=str(run_date),
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        duration_seconds=elapsed,
        status=global_status,
        steps={name: r.to_dict() for name, r in step_results.items()},
        errors=errors,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Pipeline quotidien Alpha Trade (Sprint S5 orchestrateur)."
    )
    p.add_argument(
        "--date",
        required=True,
        help="Date de traitement ISO (YYYY-MM-DD).",
    )
    p.add_argument(
        "--account-id",
        default="paper1",
        help="Identifiant du compte (défaut: paper1).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip toutes les étapes, produit un rapport vide.",
    )
    p.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="Fichier JSON de sortie (défaut: stdout).",
    )
    p.add_argument(
        "--config-path",
        type=Path,
        default=None,
        help="Chemin YAML alternatif à propager à toutes les étapes du pipeline.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    try:
        run_date = date.fromisoformat(args.date)
    except ValueError as exc:
        LOGGER.error("--date invalide: %s", exc)
        return 2

    result = daily_pipeline(
        run_date=run_date,
        account_id=args.account_id,
        dry_run=args.dry_run,
        config_path=args.config_path,
    )
    payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(payload, encoding="utf-8")
    else:
        print(payload)

    return 0 if result.status in ("OK", "SKIPPED") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())






