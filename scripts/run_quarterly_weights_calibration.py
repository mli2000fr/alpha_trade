"""Sprint S11 / S11.1 — Job trimestriel de calibration des poids sentiment.

Industrialise la chaîne :
``backtesting.sentiment_calibration.SentimentWeightCalibrator.walk_forward_backtest``

Sortie :
- ``artifacts/weights_calibration_runs/<YYYY-MM-DD>/calibration.json``
- ``artifacts/weights_calibration_runs/<YYYY-MM-DD>/<csv...>`` (artefacts WF)

Comparaison au dernier run trimestriel persisté : si l'écart relatif sur
``final_value`` dépasse ``--threshold-drift-pct`` (défaut 5 %), un avertissement
est émis (notifier env-driven + log structuré) et l'exit code est ``2``.

Exit codes :
- ``0`` : OK, pas de dérive notable.
- ``1`` : erreur d'exécution (DB indispo, exception métier…).
- ``2`` : dérive détectée (alerte émise).

CI nightly : à brancher dans GitHub Actions (cron trimestriel).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger("scripts.run_quarterly_weights_calibration")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "weights_calibration_runs"


def _months_back(reference: date, months: int) -> date:
    """Retourne `reference - months mois` (approximation 30 j si edge case)."""
    year = reference.year
    month = reference.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(reference.day, 28)
    return date(year, month, day)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Job trimestriel de calibration des poids sentiment (Sprint S11 / S11.1)."
    )
    p.add_argument(
        "--end",
        type=date.fromisoformat,
        default=None,
        help="Date de fin de la fenêtre (YYYY-MM-DD). Défaut : aujourd'hui.",
    )
    p.add_argument(
        "--lookback-months",
        type=int,
        default=12,
        help="Nombre de mois de lookback (défaut : 12).",
    )
    p.add_argument(
        "--threshold-drift-pct",
        type=float,
        default=0.05,
        help="Seuil de dérive relative sur final_value (défaut : 0.05 = 5%%).",
    )
    p.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Répertoire racine des runs (défaut : artifacts/weights_calibration_runs/).",
    )
    p.add_argument(
        "--no-alert",
        action="store_true",
        help="Désactive l'envoi d'alerte (utile pour dry-run / CI dev).",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return p


def _load_previous_calibration(output_root: Path, current_dir: Path) -> Optional[dict[str, Any]]:
    """Trouve le dossier daté précédent (le plus récent) et charge ``calibration.json``."""
    if not output_root.exists():
        return None
    candidates = sorted(
        (
            d
            for d in output_root.iterdir()
            if d.is_dir() and d.name != current_dir.name and (d / "calibration.json").is_file()
        ),
        key=lambda p: p.name,
        reverse=True,
    )
    if not candidates:
        return None
    try:
        return json.loads((candidates[0] / "calibration.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("calibration précédente illisible (%s): %s", candidates[0], exc)
        return None


def _compute_drift_pct(current: float, previous: float) -> float:
    if previous == 0:
        return float("inf") if current != 0 else 0.0
    return (current - previous) / abs(previous)


def _serialize_result(result: Any) -> dict[str, Any]:
    """Sérialise un :class:`WalkForwardCalibrationResult` (dataclass) en dict JSON."""
    if hasattr(result, "__dict__") and not isinstance(result, dict):
        try:
            return asdict(result)
        except TypeError:
            pass
    if isinstance(result, dict):
        return dict(result)
    return {"repr": repr(result)}


def _normalize_dates(payload: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in payload.items():
        out[k] = v.isoformat() if isinstance(v, date) else v
    return out


def run(
    *,
    end: Optional[date] = None,
    lookback_months: int = 12,
    threshold_drift_pct: float = 0.05,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    no_alert: bool = False,
    calibrator_factory=None,
    notifier_factory=None,
) -> int:
    """Cœur du job (testable). Retourne l'exit code (0/1/2).

    ``calibrator_factory`` / ``notifier_factory`` permettent l'injection de
    dépendances pour les tests (sinon : utilise les factories réelles).
    """
    end_date = end or date.today()
    start_date = _months_back(end_date, lookback_months)
    run_dir = output_root / end_date.isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info(
        "Calibration trimestrielle | start=%s end=%s output=%s",
        start_date,
        end_date,
        run_dir,
    )

    if calibrator_factory is None:
        from backtesting.sentiment_calibration import SentimentWeightCalibrator

        calibrator_factory = lambda: SentimentWeightCalibrator()  # noqa: E731

    try:
        calibrator = calibrator_factory()
        result_tuple = calibrator.walk_forward_backtest(
            start_date=start_date,
            end_date=end_date,
            output_dir=run_dir,
        )
    except Exception as exc:
        LOGGER.exception("Calibration trimestrielle a échoué : %s", exc)
        (run_dir / "calibration_error.json").write_text(
            json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 1

    # walk_forward_backtest renvoie un tuple (result, fold_df, oos_df, signals_df, artifacts).
    if isinstance(result_tuple, tuple) and result_tuple:
        result = result_tuple[0]
        artifacts = result_tuple[4] if len(result_tuple) >= 5 else {}
    else:
        result = result_tuple
        artifacts = {}

    payload = _normalize_dates(_serialize_result(result))
    payload["artifacts"] = artifacts
    payload["lookback_months"] = lookback_months
    payload["threshold_drift_pct"] = threshold_drift_pct

    # Comparaison au précédent run.
    previous = _load_previous_calibration(output_root, run_dir)
    drift_pct: Optional[float] = None
    if previous is not None and "final_value" in previous and "final_value" in payload:
        try:
            drift_pct = _compute_drift_pct(
                float(payload["final_value"]), float(previous["final_value"])
            )
            payload["drift_vs_previous_pct"] = drift_pct
            payload["previous_final_value"] = float(previous["final_value"])
        except (TypeError, ValueError):
            LOGGER.warning("final_value non numérique : drift non calculé.")

    (run_dir / "calibration.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    if drift_pct is not None and abs(drift_pct) > threshold_drift_pct:
        msg = (
            f"[calibration trimestrielle] dérive détectée : "
            f"final_value {payload.get('final_value')} vs précédent "
            f"{payload['previous_final_value']} (delta={drift_pct:+.2%}, "
            f"seuil={threshold_drift_pct:+.2%})"
        )
        LOGGER.warning(msg)
        if not no_alert:
            try:
                if notifier_factory is None:
                    from service.alerting import build_notifier_from_env

                    notifier_factory = build_notifier_from_env
                notifier = notifier_factory()
                if notifier is not None:
                    # API best-effort : try notify_warning, fallback notify.
                    fn = getattr(notifier, "notify_warning", None) or getattr(notifier, "notify", None)
                    if callable(fn):
                        fn(msg)
            except Exception:
                LOGGER.exception("Échec envoi alerte (best-effort).")
        return 2

    LOGGER.info("Calibration trimestrielle OK (drift=%s).", drift_pct)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return run(
        end=args.end,
        lookback_months=args.lookback_months,
        threshold_drift_pct=args.threshold_drift_pct,
        output_root=args.output_root,
        no_alert=args.no_alert,
    )


if __name__ == "__main__":
    sys.exit(main())

