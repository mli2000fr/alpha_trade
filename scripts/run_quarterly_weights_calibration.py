"""Sprint S11 / P3 — Job trimestriel de calibration empirique conviction/Kelly.

Industrialise la chaîne :
``backtesting.weights_calibration.EmpiricalRiskCalibrator.walk_forward_backtest``

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
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

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
        description="Job trimestriel de calibration empirique conviction/Kelly (Sprint S11 / P3)."
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
        "--segment-horizons",
        type=int,
        nargs="+",
        default=None,
        help="Liste des horizons à calibrer (ex: --segment-horizons 5 10). Défaut : 5.",
    )
    p.add_argument(
        "--segment-lookback-months",
        type=int,
        nargs="+",
        default=None,
        help="Liste des fenêtres de lookback à calibrer (ex: --segment-lookback-months 6 12). Défaut : --lookback-months.",
    )
    p.add_argument(
        "--reference-live-horizon-days",
        type=int,
        default=5,
        help="Horizon de référence live pour le segment baseline/drift (défaut : 5).",
    )
    p.add_argument(
        "--reference-live-lookback-months",
        type=int,
        default=None,
        help="Fenêtre de référence live pour le segment baseline/drift (défaut : --lookback-months).",
    )
    p.add_argument(
        "--min-live-observations",
        type=int,
        default=250,
        help="Seuil minimum d'observations pour promouvoir un segment en live.",
    )
    p.add_argument(
        "--min-live-snapshot-days",
        type=int,
        default=20,
        help="Seuil minimum de séances distinctes pour promouvoir un segment en live.",
    )
    p.add_argument(
        "--min-live-symbols",
        type=int,
        default=10,
        help="Seuil minimum de symboles distincts pour promouvoir un segment en live.",
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


def _load_previous_calibration(output_root: Path, current_dir: Path) -> dict[str, Any] | None:
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
    if is_dataclass(result) and not isinstance(result, type):
        try:
            return asdict(result)
        except TypeError:
            pass
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


def _normalize_result_payload(result: Any) -> dict[str, Any]:
    return _normalize_dates(_serialize_result(result))


def _extract_reference_final_value(payload: dict[str, Any]) -> float | None:
    if "final_value" in payload:
        try:
            return float(payload["final_value"])
        except (TypeError, ValueError):
            return None
    segments = payload.get("segments")
    if not isinstance(segments, dict):
        return None
    baseline = segments.get("all")
    if not isinstance(baseline, dict) or "final_value" not in baseline:
        return None
    try:
        return float(baseline["final_value"])
    except (TypeError, ValueError):
        return None


def _normalize_int_sequence(values: list[int] | tuple[int, ...] | None, *, default: Sequence[int]) -> list[int]:
    normalized = sorted({int(value) for value in (values or list(default)) if int(value) > 0})
    return normalized or [int(value) for value in default]


def _serialize_drift(result: Any) -> dict[str, Any]:
    return _normalize_dates(_serialize_result(result))


def _build_governance_summary(segment_payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    eligible_segments = 0
    blocked_segments = 0
    eligibility_reasons = Counter()
    for payload in segment_payloads.values():
        if bool(payload.get("eligible_for_live")):
            eligible_segments += 1
            continue
        blocked_segments += 1
        reason = str(payload.get("eligibility_reason") or "unknown").strip() or "unknown"
        eligibility_reasons[reason] += 1
    return {
        "eligible_segments": eligible_segments,
        "blocked_segments": blocked_segments,
        "eligibility_reason_counts": dict(sorted(eligibility_reasons.items())),
    }


def _supports_segment_drift(result: Any) -> bool:
    required_attributes = (
        "market_regime_mode",
        "horizon_days",
        "lookback_months",
        "calibration_run_id",
        "metric_name",
        "metric_value",
        "final_value",
    )
    return all(hasattr(result, attribute) for attribute in required_attributes)


def run(
    *,
    end: date | None = None,
    lookback_months: int = 12,
    threshold_drift_pct: float = 0.05,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    no_alert: bool = False,
    segment_horizons: list[int] | None = None,
    segment_lookback_months: list[int] | None = None,
    reference_live_horizon_days: int = 5,
    reference_live_lookback_months: int | None = None,
    min_live_observations: int = 250,
    min_live_snapshot_days: int = 20,
    min_live_symbols: int = 10,
    calibrator_factory=None,
    notifier_factory=None,
) -> int:
    """Cœur du job (testable). Retourne l'exit code (0/1/2).

    ``calibrator_factory`` / ``notifier_factory`` permettent l'injection de
    dépendances pour les tests (sinon : utilise les factories réelles).
    """
    end_date = end or date.today()
    start_date = _months_back(end_date, lookback_months)
    resolved_segment_horizons = _normalize_int_sequence(segment_horizons, default=(5,))
    resolved_segment_lookbacks = _normalize_int_sequence(segment_lookback_months, default=(lookback_months,))
    resolved_reference_live_lookback_months = int(reference_live_lookback_months or lookback_months)
    run_dir = output_root / end_date.isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info(
        "Calibration trimestrielle | start=%s end=%s output=%s",
        start_date,
        end_date,
        run_dir,
    )

    if calibrator_factory is None:
        from backtesting.weights_calibration import EmpiricalRiskCalibrator

        calibrator_factory = lambda: EmpiricalRiskCalibrator()  # noqa: E731

    try:
        calibrator = calibrator_factory()
        if hasattr(calibrator, "walk_forward_backtests_by_segment"):
            result_by_segment = calibrator.walk_forward_backtests_by_segment(
                end_date=end_date,
                output_dir=run_dir,
                horizon_days_values=resolved_segment_horizons,
                lookback_months_values=resolved_segment_lookbacks,
                min_live_observations=min_live_observations,
                min_live_snapshot_days=min_live_snapshot_days,
                min_live_symbols=min_live_symbols,
            )
        elif hasattr(calibrator, "walk_forward_backtests_by_regime"):
            result_by_segment = calibrator.walk_forward_backtests_by_regime(
                start_date=start_date,
                end_date=end_date,
                output_dir=run_dir,
            )
        else:
            result_by_segment = {
                "all": calibrator.walk_forward_backtest(
                    start_date=start_date,
                    end_date=end_date,
                    output_dir=run_dir,
                )
            }
    except Exception as exc:
        LOGGER.exception("Calibration trimestrielle a échoué : %s", exc)
        (run_dir / "calibration_error.json").write_text(
            json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 1

    segment_payloads: dict[str, dict[str, Any]] = {}
    artifacts_by_segment: dict[str, Any] = {}
    segment_results: list[Any] = []
    for segment_key, result_tuple in result_by_segment.items():
        if isinstance(result_tuple, tuple) and result_tuple:
            result = result_tuple[0]
            artifacts = result_tuple[4] if len(result_tuple) >= 5 else {}
        else:
            result = result_tuple
            artifacts = {}
        segment_results.append(result)
        segment_payloads[segment_key] = _normalize_result_payload(result)
        artifacts_by_segment[segment_key] = artifacts

    reference_segment_key = next(
        (
            segment_key
            for segment_key, payload_item in segment_payloads.items()
            if str(payload_item.get("market_regime_mode") or "all").strip().lower() == "all"
            and int(payload_item.get("horizon_days") or 0) == int(reference_live_horizon_days)
            and int(payload_item.get("lookback_months") or 0) == resolved_reference_live_lookback_months
        ),
        None,
    )
    if reference_segment_key is None:
        reference_segment_key = next(
            (
                segment_key
                for segment_key, payload_item in segment_payloads.items()
                if str(payload_item.get("market_regime_mode") or "all").strip().lower() == "all"
            ),
            next(iter(segment_payloads)),
        )

    payload = dict(segment_payloads[reference_segment_key])
    payload["artifacts"] = artifacts_by_segment.get(reference_segment_key, {})
    payload["segments"] = {}
    payload["artifacts_by_segment"] = artifacts_by_segment
    payload["artifacts_by_regime"] = artifacts_by_segment
    payload["reference_segment_key"] = reference_segment_key
    for segment_key, segment_payload in segment_payloads.items():
        payload["segments"][segment_key] = segment_payload
    payload["lookback_months"] = lookback_months
    payload["segment_horizons"] = resolved_segment_horizons
    payload["segment_lookback_months"] = resolved_segment_lookbacks
    payload["reference_live_horizon_days"] = int(reference_live_horizon_days)
    payload["reference_live_lookback_months"] = resolved_reference_live_lookback_months
    payload["governance_summary"] = _build_governance_summary(segment_payloads)
    payload["threshold_drift_pct"] = threshold_drift_pct

    if segment_results and all(_supports_segment_drift(result) for result in segment_results):
        try:
            from backtesting.weights_calibration import compute_segment_drifts, persist_segment_drifts

            segment_drifts = compute_segment_drifts(
                segment_results,
                reference_horizon_days=reference_live_horizon_days,
                reference_lookback_months=resolved_reference_live_lookback_months,
            )
            payload["segment_drifts"] = [_serialize_drift(item) for item in segment_drifts]
            engine = getattr(calibrator, "engine", None)
            if segment_drifts and engine is not None:
                try:
                    persist_segment_drifts(segment_drifts, engine=engine)
                except Exception:
                    LOGGER.warning("Persistance des drifts inter-segments impossible (best-effort).", exc_info=True)
        except Exception:
            LOGGER.warning("Calcul des drifts inter-segments impossible (best-effort).", exc_info=True)
            payload["segment_drifts"] = []
    else:
        payload["segment_drifts"] = []

    # Comparaison au précédent run.
    previous = _load_previous_calibration(output_root, run_dir)
    drift_pct: float | None = None
    current_final_value = _extract_reference_final_value(payload)
    previous_final_value = _extract_reference_final_value(previous) if previous is not None else None
    if current_final_value is not None and previous_final_value is not None:
        try:
            drift_pct = _compute_drift_pct(current_final_value, previous_final_value)
            payload["drift_vs_previous_pct"] = drift_pct
            payload["previous_final_value"] = previous_final_value
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


def main(argv: list[str] | None = None) -> int:
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
        segment_horizons=args.segment_horizons,
        segment_lookback_months=args.segment_lookback_months,
        reference_live_horizon_days=args.reference_live_horizon_days,
        reference_live_lookback_months=args.reference_live_lookback_months,
        min_live_observations=args.min_live_observations,
        min_live_snapshot_days=args.min_live_snapshot_days,
        min_live_symbols=args.min_live_symbols,
    )


if __name__ == "__main__":
    sys.exit(main())

