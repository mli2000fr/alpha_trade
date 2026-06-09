"""Orchestration d'une ablation factorielle ML × régime sur plusieurs fenêtres.

Objectif
--------
Préparer une comparaison propre et reproductible entre 4 variantes :
- ``control``              : ML ON  + régime ON
- ``ml_off``               : ML OFF + régime ON
- ``regime_off``           : ML ON  + régime OFF
- ``ml_off_regime_off``    : ML OFF + régime OFF

Le script :
1. fige la configuration runtime dans ``output_root/configs`` ;
2. génère un manifest JSON + un script PowerShell avec toutes les commandes ;
3. peut exécuter les runs séquentiellement ;
4. agrège ``report.json`` / ``fidelity_manifest.json`` / ``phase2_risk_summary.json`` ;
5. calcule les effets factoriels par fenêtre puis une synthèse décisionnelle.

Usage rapide
------------
Plan uniquement (sans lancer les backtests) ::

    python -m scripts.run_ml_regime_ablation --output-root artifacts/ablation/ml_regime_objective

Exécution réelle ::

    python -m scripts.run_ml_regime_ablation --execute --skip-existing \
        --output-root artifacts/ablation/ml_regime_objective
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_CONFIG = PROJECT_ROOT / "config.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "ablation" / "ml_regime_objective"
DEFAULT_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "models"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "artifacts" / "backtest_cache"


@dataclass(frozen=True, slots=True)
class WindowSpec:
    window_id: str
    start: str
    end: str
    description: str


@dataclass(frozen=True, slots=True)
class VariantSpec:
    variant_id: str
    ml_mode: str
    regime_enabled: bool
    description: str


@dataclass(frozen=True, slots=True)
class RunPlan:
    window: WindowSpec
    variant: VariantSpec
    config_path: Path
    output_dir: Path
    stdout_log: Path
    stderr_log: Path
    command: tuple[str, ...]


DEFAULT_WINDOWS: dict[str, tuple[WindowSpec, ...]] = {
    "core_2020": (
        WindowSpec("2020_q1_crash", "2020-01-01", "2020-03-31", "Crash Covid / stress test"),
        WindowSpec("2020_q2_rebound", "2020-04-01", "2020-06-30", "Rebond post-crash"),
        WindowSpec("2020_q3_momentum", "2020-07-01", "2020-09-30", "Momentum d'été"),
        WindowSpec("2020_q4_rotation", "2020-10-01", "2020-12-31", "Rotation / reprise fin 2020"),
        WindowSpec("2020_full_year", "2020-01-01", "2020-12-31", "Vue agrégée annuelle"),
    ),
    "cross_cycle": (
        WindowSpec("2020_q1_crash", "2020-01-01", "2020-03-31", "Crash Covid / stress test"),
        WindowSpec("2020_q2_rebound", "2020-04-01", "2020-06-30", "Rebond post-crash"),
        WindowSpec("2022_h1_bear", "2022-01-03", "2022-06-30", "Bear market inflation / hausse des taux"),
        WindowSpec("2022_h2_bottom", "2022-07-01", "2022-12-30", "Phase de bottoming / bear rallies"),
        WindowSpec("2023_h1_recovery", "2023-01-03", "2023-06-30", "Recovery / leadership growth"),
    ),
}

DEFAULT_VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec("control", "rebuild-missing", True, "ML ON + régime ON"),
    VariantSpec("ml_off", "off", True, "ML OFF + régime ON"),
    VariantSpec("regime_off", "rebuild-missing", False, "ML ON + régime OFF"),
    VariantSpec("ml_off_regime_off", "off", False, "ML OFF + régime OFF"),
)

_EXPECTED_VARIANTS = {variant.variant_id for variant in DEFAULT_VARIANTS}


def _iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _add_bool_argument(
    parser: argparse.ArgumentParser,
    *,
    name: str,
    default: bool,
    help_enabled: str,
    help_disabled: str,
) -> None:
    dest = name.replace("-", "_")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(f"--{name}", dest=dest, action="store_true", help=help_enabled)
    group.add_argument(f"--no-{name}", dest=dest, action="store_false", help=help_disabled)
    parser.set_defaults(**{dest: default})


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        return {"_parse_error": f"JSON invalide: {exc}"}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _get_nested(payload: dict[str, Any] | None, *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_windows_from_file(path: Path) -> tuple[WindowSpec, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Le fichier --windows-file doit contenir une liste non vide.")
    windows: list[WindowSpec] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Fenêtre #{index} invalide: objet JSON attendu.")
        try:
            window_id = str(item["window_id"]).strip()
            start = str(item["start"]).strip()
            end = str(item["end"]).strip()
        except KeyError as exc:
            raise ValueError(f"Fenêtre #{index}: clé manquante {exc!s}.") from exc
        if not window_id or not start or not end:
            raise ValueError(f"Fenêtre #{index}: window_id/start/end obligatoires.")
        description = str(item.get("description") or window_id).strip()
        windows.append(WindowSpec(window_id=window_id, start=start, end=end, description=description))
    return tuple(windows)


def resolve_windows(window_preset: str, windows_file: Path | None) -> tuple[WindowSpec, ...]:
    if windows_file is not None:
        return _normalize_windows_from_file(windows_file)
    return DEFAULT_WINDOWS[window_preset]


def write_frozen_runtime_configs(*, base_config_path: Path, output_root: Path) -> dict[str, Path]:
    payload = yaml.safe_load(base_config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration YAML invalide: {base_config_path}")

    configs_dir = output_root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = configs_dir / "baseline.runtime.yaml"
    regime_off_path = configs_dir / "regime_off.runtime.yaml"

    baseline_payload = json.loads(json.dumps(payload))
    regime_off_payload = json.loads(json.dumps(payload))
    market_regimes = regime_off_payload.setdefault("market_regimes", {})
    if not isinstance(market_regimes, dict):
        raise ValueError("La clé `market_regimes` doit être un objet YAML/dict.")
    market_regimes["enabled"] = False

    baseline_path.write_text(
        yaml.safe_dump(baseline_payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    regime_off_path.write_text(
        yaml.safe_dump(regime_off_payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return {"baseline": baseline_path, "regime_off": regime_off_path}


def build_backtest_command(args: argparse.Namespace, *, window: WindowSpec, variant: VariantSpec, config_path: Path, output_dir: Path) -> tuple[str, ...]:
    command: list[str] = [
        str(args.python_executable),
        "-u",
        "-m",
        "backtesting",
        "run",
        "--start",
        window.start,
        "--end",
        window.end,
        "--equity",
        str(args.equity),
        "--tp",
        str(args.tp),
        "--ts",
        str(args.ts),
        "--max-positions",
        str(args.max_positions),
        "--commission-bps",
        str(args.commission_bps),
        "--slippage-bps",
        str(args.slippage_bps),
        "--account-type",
        args.account_type,
        "--sentiment-lookback",
        str(args.sentiment_lookback),
        "--ml-mode",
        variant.ml_mode,
        "--sentiment-mode",
        args.sentiment_mode,
        "--artifacts-dir",
        str(args.artifacts_dir),
        "--config-path",
        str(config_path),
        "--output-dir",
        str(output_dir),
        "--engine-mode",
        args.engine_mode,
        "--scores-pit-mode",
        args.scores_pit_mode,
        "--macro-pit-mode",
        args.macro_pit_mode,
        "--ml-pit-strategy",
        args.ml_pit_strategy,
        "--phase2-mode",
        args.phase2_mode,
        "--phase3-mode",
        args.phase3_mode,
        "--phase4-mode",
        args.phase4_mode,
        "--phase5-mode",
        args.phase5_mode,
        "--phase7-mode",
        args.phase7_mode,
        "--capital-preset-key",
        args.capital_preset_key,
        "--score-column",
        args.score_column,
        "--risk-free-rate",
        str(args.risk_free_rate),
        "--max-entry-gap-pct",
        str(args.max_entry_gap_pct),
        "--max-sector-exposure-pct",
        str(args.max_sector_exposure_pct),
        "--max-portfolio-dd-pct",
        str(args.max_portfolio_dd_pct),
        "--dd-recovery-pct",
        str(args.dd_recovery_pct),
        "--dd-rolling-peak-window-days",
        str(args.dd_rolling_peak_window_days),
        "--dd-degraded-allocation-pct",
        str(args.dd_degraded_allocation_pct),
    ]
    if args.target_annual_vol is not None:
        command.extend(["--target-annual-vol", str(args.target_annual_vol)])
    if args.min_ml_coverage_ratio is not None:
        command.extend(["--min-ml-coverage-ratio", str(args.min_ml_coverage_ratio)])
    if args.walk_forward_artifacts_dir is not None:
        command.extend(["--walk-forward-artifacts-dir", str(args.walk_forward_artifacts_dir)])
    if args.allow_fractional_shares:
        command.append("--allow-fractional-shares")
    if args.swing_only:
        command.append("--swing-only")
    if args.allow_neutral_fallback_on_missing_macro_data:
        command.append("--allow-neutral-fallback-on-missing-macro-data")
    else:
        command.append("--fail-on-missing-macro-data")
    if args.use_cache:
        command.append("--use-cache")
        command.extend(["--cache-dir", str(args.cache_dir)])
    if args.seed is not None:
        command.extend(["--seed", str(args.seed)])
    return tuple(command)


def build_run_plans(args: argparse.Namespace, *, windows: tuple[WindowSpec, ...], config_paths: dict[str, Path]) -> tuple[RunPlan, ...]:
    plans: list[RunPlan] = []
    for window in windows:
        for variant in DEFAULT_VARIANTS:
            config_path = config_paths["baseline" if variant.regime_enabled else "regime_off"]
            output_dir = args.output_root / "runs" / window.window_id / variant.variant_id
            stdout_log = output_dir / "stdout.log"
            stderr_log = output_dir / "stderr.log"
            command = build_backtest_command(
                args,
                window=window,
                variant=variant,
                config_path=config_path,
                output_dir=output_dir,
            )
            plans.append(
                RunPlan(
                    window=window,
                    variant=variant,
                    config_path=config_path,
                    output_dir=output_dir,
                    stdout_log=stdout_log,
                    stderr_log=stderr_log,
                    command=command,
                )
            )
    return tuple(plans)


def write_plan_manifest(plans: tuple[RunPlan, ...], *, output_root: Path, config_paths: dict[str, Path], base_config_path: Path) -> Path:
    windows: list[dict[str, Any]] = []
    seen_windows: set[str] = set()
    for plan in plans:
        if plan.window.window_id in seen_windows:
            continue
        seen_windows.add(plan.window.window_id)
        windows.append(asdict(plan.window))
    manifest = {
        "generated_at": _iso_now(),
        "project_root": str(PROJECT_ROOT),
        "base_config_path": str(base_config_path),
        "frozen_configs": {key: str(value) for key, value in config_paths.items()},
        "variants": [asdict(variant) for variant in DEFAULT_VARIANTS],
        "windows": windows,
        "runs": [
            {
                "window": asdict(plan.window),
                "variant": asdict(plan.variant),
                "config_path": str(plan.config_path),
                "output_dir": str(plan.output_dir),
                "stdout_log": str(plan.stdout_log),
                "stderr_log": str(plan.stderr_log),
                "command": list(plan.command),
                "command_line": subprocess.list2cmdline(list(plan.command)),
            }
            for plan in plans
        ],
    }
    manifest_path = output_root / "ablation_plan.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def write_powershell_launcher(plans: tuple[RunPlan, ...], *, output_root: Path) -> Path:
    launcher_path = output_root / "run_all.ps1"
    lines = [
        '$ErrorActionPreference = "Stop"',
        f'Push-Location "{PROJECT_ROOT}"',
        "try {",
    ]
    for plan in plans:
        plan.output_dir.mkdir(parents=True, exist_ok=True)
        cmdline = subprocess.list2cmdline(list(plan.command))
        lines.append(f'  Write-Host "==> {plan.window.window_id} / {plan.variant.variant_id}"')
        lines.append(f"  {cmdline}")
    lines.extend([
        "}",
        "finally {",
        "  Pop-Location",
        "}",
        "",
    ])
    launcher_path.write_text("\n".join(lines), encoding="utf-8")
    return launcher_path


def execute_plans(plans: tuple[RunPlan, ...], *, skip_existing: bool, stop_on_error: bool) -> list[dict[str, Any]]:
    execution_log: list[dict[str, Any]] = []
    for plan in plans:
        plan.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = plan.output_dir / "report.json"
        if skip_existing and report_path.is_file():
            execution_log.append(
                {
                    "window_id": plan.window.window_id,
                    "variant_id": plan.variant.variant_id,
                    "status": "skipped_existing",
                    "output_dir": str(plan.output_dir),
                    "timestamp": _iso_now(),
                }
            )
            continue
        with plan.stdout_log.open("w", encoding="utf-8") as stdout_handle, plan.stderr_log.open("w", encoding="utf-8") as stderr_handle:
            completed = subprocess.run(
                list(plan.command),
                cwd=PROJECT_ROOT,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                check=False,
            )
        status = "completed" if completed.returncode == 0 else "failed"
        execution_log.append(
            {
                "window_id": plan.window.window_id,
                "variant_id": plan.variant.variant_id,
                "status": status,
                "returncode": completed.returncode,
                "output_dir": str(plan.output_dir),
                "stdout_log": str(plan.stdout_log),
                "stderr_log": str(plan.stderr_log),
                "timestamp": _iso_now(),
            }
        )
        if completed.returncode != 0 and stop_on_error:
            break
    return execution_log


def collect_run_row(plan: RunPlan) -> dict[str, Any]:
    report_path = plan.output_dir / "report.json"
    fidelity_path = plan.output_dir / "fidelity_manifest.json"
    phase2_path = plan.output_dir / "phase2_risk_summary.json"

    report = _read_json(report_path)
    fidelity = _read_json(fidelity_path)
    phase2 = _read_json(phase2_path)

    status = "planned"
    if report_path.exists() and isinstance(report, dict) and "_parse_error" not in report:
        status = "completed"
    elif plan.stderr_log.exists() or plan.stdout_log.exists():
        status = "missing_report"

    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    params = report.get("params", {}) if isinstance(report, dict) else {}
    if (not phase2 or "_parse_error" in phase2) and isinstance(params, dict):
        phase2 = _get_nested(params, "phase2", "risk_bridge") or {}
    if (not fidelity or "_parse_error" in fidelity) and isinstance(report, dict):
        fidelity = report.get("fidelity", {}) or {}

    degraded_reasons = _get_nested(fidelity, "degraded_reasons") if isinstance(fidelity, dict) else None
    if isinstance(degraded_reasons, list):
        degraded_reasons_str = "|".join(str(item) for item in degraded_reasons)
    else:
        degraded_reasons_str = ""

    return {
        "window_id": plan.window.window_id,
        "window_start": plan.window.start,
        "window_end": plan.window.end,
        "window_description": plan.window.description,
        "variant_id": plan.variant.variant_id,
        "variant_description": plan.variant.description,
        "expected_ml_mode": plan.variant.ml_mode,
        "expected_regime_enabled": plan.variant.regime_enabled,
        "status": status,
        "output_dir": str(plan.output_dir),
        "config_path": str(plan.config_path),
        "total_return_pct": _safe_float(summary.get("total_return_pct")),
        "sharpe_ratio": _safe_float(summary.get("sharpe_ratio")),
        "max_drawdown_pct": _safe_float(summary.get("max_drawdown_pct")),
        "total_trades": _safe_int(summary.get("total_trades")),
        "win_rate_pct": _safe_float(summary.get("win_rate_pct")),
        "final_value": _safe_float(summary.get("final_value")),
        "actual_ml_mode": params.get("ml_mode") if isinstance(params, dict) else None,
        "actual_regime_enabled": _get_nested(phase2, "regime_enabled") if isinstance(phase2, dict) else None,
        "entries_accepted": _safe_int(_get_nested(phase2, "entries_accepted")),
        "entries_blocked_by_regime": _safe_int(_get_nested(phase2, "entries_blocked_by_regime")),
        "phase2_snapshot_dates": _safe_int(_get_nested(phase2, "snapshot_dates")),
        "degraded": bool(_get_nested(fidelity, "degraded")) if isinstance(fidelity, dict) and "degraded" in fidelity else None,
        "degraded_reasons": degraded_reasons_str,
        "ml_coverage_ratio_after": _safe_float(_get_nested(fidelity, "coverage", "ml", "coverage_ratio_after")),
        "ml_missing_symbol_count_after": _safe_int(_get_nested(fidelity, "coverage", "ml", "missing_symbol_count_after")),
    }


def collect_run_rows(plans: tuple[RunPlan, ...]) -> list[dict[str, Any]]:
    return [collect_run_row(plan) for plan in plans]


def _mean_or_none(values: list[float]) -> float | None:
    return mean(values) if values else None


def _median_or_none(values: list[float]) -> float | None:
    return median(values) if values else None


def _positive_count(values: list[float]) -> int:
    return sum(1 for value in values if value > 0)


def compute_factorial_effects(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_window: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        if row.get("status") != "completed":
            continue
        window_id = str(row["window_id"])
        variant_id = str(row["variant_id"])
        by_window.setdefault(window_id, {})[variant_id] = row

    per_window: dict[str, dict[str, dict[str, float]]] = {}
    ml_return_effects: list[float] = []
    ml_sharpe_effects: list[float] = []
    ml_drawdown_effects: list[float] = []
    regime_return_effects: list[float] = []
    regime_sharpe_effects: list[float] = []
    regime_drawdown_effects: list[float] = []
    combo_return_synergies: list[float] = []
    combo_sharpe_synergies: list[float] = []
    combo_drawdown_synergies: list[float] = []

    for window_id, window_rows in sorted(by_window.items()):
        if set(window_rows) != _EXPECTED_VARIANTS:
            continue

        control = window_rows["control"]
        ml_off = window_rows["ml_off"]
        regime_off = window_rows["regime_off"]
        combo = window_rows["ml_off_regime_off"]

        metric_map: dict[str, dict[str, float]] = {}
        for metric in ("total_return_pct", "sharpe_ratio", "max_drawdown_pct"):
            values = {
                key: _safe_float(item.get(metric))
                for key, item in {
                    "control": control,
                    "ml_off": ml_off,
                    "regime_off": regime_off,
                    "ml_off_regime_off": combo,
                }.items()
            }
            if any(value is None for value in values.values()):
                metric_map = {}
                break
            control_raw = values["control"]
            ml_off_raw = values["ml_off"]
            regime_off_raw = values["regime_off"]
            combo_raw = values["ml_off_regime_off"]
            if control_raw is None or ml_off_raw is None or regime_off_raw is None or combo_raw is None:
                metric_map = {}
                break
            control_value = float(control_raw)
            ml_off_value = float(ml_off_raw)
            regime_off_value = float(regime_off_raw)
            combo_value = float(combo_raw)

            ml_off_effect = ((ml_off_value + combo_value) / 2.0) - ((control_value + regime_off_value) / 2.0)
            regime_on_effect = ((control_value + ml_off_value) / 2.0) - ((regime_off_value + combo_value) / 2.0)
            if metric == "max_drawdown_pct":
                ml_off_effect *= -1.0
                regime_on_effect *= -1.0
                synergy = (control_value - ml_off_value - regime_off_value + combo_value) * -1.0
            else:
                synergy = combo_value - ml_off_value - regime_off_value + control_value
            metric_map[metric] = {
                "ml_off_effect": round(ml_off_effect, 10),
                "regime_on_effect": round(regime_on_effect, 10),
                "combo_synergy": round(synergy, 10),
            }
        if not metric_map:
            continue
        per_window[window_id] = metric_map
        ml_return_effects.append(metric_map["total_return_pct"]["ml_off_effect"])
        ml_sharpe_effects.append(metric_map["sharpe_ratio"]["ml_off_effect"])
        ml_drawdown_effects.append(metric_map["max_drawdown_pct"]["ml_off_effect"])
        regime_return_effects.append(metric_map["total_return_pct"]["regime_on_effect"])
        regime_sharpe_effects.append(metric_map["sharpe_ratio"]["regime_on_effect"])
        regime_drawdown_effects.append(metric_map["max_drawdown_pct"]["regime_on_effect"])
        combo_return_synergies.append(metric_map["total_return_pct"]["combo_synergy"])
        combo_sharpe_synergies.append(metric_map["sharpe_ratio"]["combo_synergy"])
        combo_drawdown_synergies.append(metric_map["max_drawdown_pct"]["combo_synergy"])

    def _metric_summary(values: list[float]) -> dict[str, Any]:
        return {
            "window_count": len(values),
            "mean": _mean_or_none(values),
            "median": _median_or_none(values),
            "positive_windows": _positive_count(values),
            "negative_windows": sum(1 for value in values if value < 0),
        }

    return {
        "complete_window_count": len(per_window),
        "per_window": per_window,
        "ml_off_effect": {
            "total_return_pct": _metric_summary(ml_return_effects),
            "sharpe_ratio": _metric_summary(ml_sharpe_effects),
            "drawdown_improvement": _metric_summary(ml_drawdown_effects),
        },
        "regime_on_effect": {
            "total_return_pct": _metric_summary(regime_return_effects),
            "sharpe_ratio": _metric_summary(regime_sharpe_effects),
            "drawdown_improvement": _metric_summary(regime_drawdown_effects),
        },
        "combo_synergy": {
            "total_return_pct": _metric_summary(combo_return_synergies),
            "sharpe_ratio": _metric_summary(combo_sharpe_synergies),
            "drawdown_improvement": _metric_summary(combo_drawdown_synergies),
        },
    }


def build_decision_summary(rows: list[dict[str, Any]], effects: dict[str, Any]) -> dict[str, Any]:
    completed_rows = [row for row in rows if row.get("status") == "completed"]
    degraded_by_ml_state = Counter()
    completed_by_ml_state = Counter()
    degraded_by_regime_state = Counter()
    completed_by_regime_state = Counter()
    for row in completed_rows:
        ml_state = "ml_off" if row.get("expected_ml_mode") == "off" else "ml_on"
        regime_state = "regime_on" if row.get("expected_regime_enabled") else "regime_off"
        completed_by_ml_state[ml_state] += 1
        completed_by_regime_state[regime_state] += 1
        if row.get("degraded") is True:
            degraded_by_ml_state[ml_state] += 1
            degraded_by_regime_state[regime_state] += 1

    complete_windows = int(effects.get("complete_window_count") or 0)
    ml_effect = effects.get("ml_off_effect", {})
    regime_effect = effects.get("regime_on_effect", {})

    def _ratio(effect_block: dict[str, Any], metric: str) -> float:
        if complete_windows <= 0:
            return 0.0
        positive = int(_get_nested(effect_block, metric, "positive_windows") or 0)
        return positive / complete_windows

    ml_return_ratio = _ratio(ml_effect, "total_return_pct")
    ml_sharpe_ratio = _ratio(ml_effect, "sharpe_ratio")
    ml_dd_ratio = _ratio(ml_effect, "drawdown_improvement")
    regime_return_ratio = _ratio(regime_effect, "total_return_pct")
    regime_sharpe_ratio = _ratio(regime_effect, "sharpe_ratio")
    regime_dd_ratio = _ratio(regime_effect, "drawdown_improvement")

    recommendations: list[str] = []
    if complete_windows == 0:
        recommendations.append(
            "Aucune fenêtre complète 2×2 n'est encore disponible : lancer ou compléter les runs avant de conclure."
        )
    else:
        if ml_return_ratio >= 0.6 and ml_sharpe_ratio >= 0.6:
            if degraded_by_ml_state["ml_on"] > degraded_by_ml_state["ml_off"]:
                recommendations.append(
                    "Le signal est défavorable au ML actuel : `ml_mode=off` améliore majoritairement rendement/Sharpe et réduit en plus le risque opérationnel (runs dégradés côté ML ON)."
                )
            else:
                recommendations.append(
                    "Le ML actuel n'apporte pas de valeur nette sur la majorité des fenêtres : le garder en recherche, mais passer la baseline opérationnelle en `ml_mode=off` tant qu'une version meilleure n'est pas prête."
                )
        elif ml_return_ratio <= 0.4 and ml_sharpe_ratio <= 0.4:
            recommendations.append(
                "Le ML semble utile ou au moins non nuisible sur cet échantillon : ne pas le retirer sans approfondir les fenêtres où il surperforme."
            )
        else:
            recommendations.append(
                "Le verdict ML est mixte : conserver l'ablation en place et segmenter ensuite par contexte de marché avant toute décision définitive."
            )

        if regime_return_ratio >= 0.6 and regime_sharpe_ratio >= 0.6:
            recommendations.append(
                "Le régime mérite d'être conservé : sa présence améliore majoritairement rendement et Sharpe sur les fenêtres complètes."
            )
        elif regime_dd_ratio >= 0.6 and (regime_return_ratio < 0.6 or regime_sharpe_ratio < 0.6):
            recommendations.append(
                "Le régime semble surtout utile comme amortisseur de risque : à recalibrer plutôt qu'à supprimer, car il protège plus qu'il ne crée de performance."
            )
        elif regime_return_ratio <= 0.4 and regime_sharpe_ratio <= 0.4:
            recommendations.append(
                "Le régime actuel paraît sur-filtrant : le retirer de la baseline ou le passer en shadow/recalibration est justifié tant qu'il ne démontre pas un gain net."
            )
        else:
            recommendations.append(
                "Le verdict régime est mixte : garder l'instrumentation et analyser les fenêtres où il coupe beaucoup d'entrées sans améliorer le portefeuille."
            )

    return {
        "generated_at": _iso_now(),
        "complete_window_count": complete_windows,
        "completed_run_count": len(completed_rows),
        "completed_by_ml_state": dict(completed_by_ml_state),
        "degraded_by_ml_state": dict(degraded_by_ml_state),
        "completed_by_regime_state": dict(completed_by_regime_state),
        "degraded_by_regime_state": dict(degraded_by_regime_state),
        "recommendations": recommendations,
    }


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(key, "")) for key, _ in columns) + " |")
    return "\n".join([header, separator, *body])


def build_decision_markdown(*, rows: list[dict[str, Any]], effects: dict[str, Any], decision: dict[str, Any], output_root: Path) -> str:
    completed_rows = [row for row in rows if row.get("status") == "completed"]
    completed_rows.sort(key=lambda item: (str(item["window_id"]), str(item["variant_id"])))

    window_table = _markdown_table(
        [
            {
                "window_id": row["window_id"],
                "variant_id": row["variant_id"],
                "return": row.get("total_return_pct"),
                "sharpe": row.get("sharpe_ratio"),
                "max_dd": row.get("max_drawdown_pct"),
                "degraded": row.get("degraded"),
                "blocked_by_regime": row.get("entries_blocked_by_regime"),
            }
            for row in completed_rows
        ],
        [
            ("window_id", "Fenêtre"),
            ("variant_id", "Variante"),
            ("return", "Return %"),
            ("sharpe", "Sharpe"),
            ("max_dd", "Max DD %"),
            ("degraded", "Dégradé"),
            ("blocked_by_regime", "Entrées bloquées régime"),
        ],
    ) if completed_rows else "_Aucun run terminé pour le moment._"

    effect_rows: list[dict[str, Any]] = []
    for family_key, family_label in (
        ("ml_off_effect", "Effet `ml_mode=off` (positif = couper ML aide)"),
        ("regime_on_effect", "Effet régime ON (positif = garder le régime aide)"),
        ("combo_synergy", "Synergie du combo (positif = interaction favorable)"),
    ):
        family = effects.get(family_key, {})
        for metric_key, metric_label in (
            ("total_return_pct", "Return %"),
            ("sharpe_ratio", "Sharpe"),
            ("drawdown_improvement", "Amélioration DD"),
        ):
            block = family.get(metric_key, {})
            effect_rows.append(
                {
                    "family": family_label,
                    "metric": metric_label,
                    "mean": block.get("mean"),
                    "median": block.get("median"),
                    "positive": block.get("positive_windows"),
                    "negative": block.get("negative_windows"),
                }
            )
    effects_table = _markdown_table(
        effect_rows,
        [
            ("family", "Lecture"),
            ("metric", "Métrique"),
            ("mean", "Moyenne"),
            ("median", "Médiane"),
            ("positive", "Fenêtres positives"),
            ("negative", "Fenêtres négatives"),
        ],
    )

    recommendations = "\n".join(f"- {item}" for item in decision.get("recommendations", [])) or "- Aucune recommandation."

    return "\n".join(
        [
            "# Ablation ML vs régime — synthèse objective",
            "",
            f"- Généré le : `{decision.get('generated_at')}`",
            f"- Racine des artefacts : `{output_root}`",
            f"- Fenêtres complètes 2×2 : **{decision.get('complete_window_count', 0)}**",
            f"- Runs terminés : **{decision.get('completed_run_count', 0)}**",
            "",
            "## 1. Résultats par run terminé",
            "",
            window_table,
            "",
            "## 2. Effets factoriels agrégés",
            "",
            effects_table,
            "",
            "## 3. Risque opérationnel",
            "",
            f"- ML ON : {decision.get('degraded_by_ml_state', {}).get('ml_on', 0)} run(s) dégradé(s) sur {decision.get('completed_by_ml_state', {}).get('ml_on', 0)}",
            f"- ML OFF : {decision.get('degraded_by_ml_state', {}).get('ml_off', 0)} run(s) dégradé(s) sur {decision.get('completed_by_ml_state', {}).get('ml_off', 0)}",
            f"- Régime ON : {decision.get('degraded_by_regime_state', {}).get('regime_on', 0)} run(s) dégradé(s) sur {decision.get('completed_by_regime_state', {}).get('regime_on', 0)}",
            f"- Régime OFF : {decision.get('degraded_by_regime_state', {}).get('regime_off', 0)} run(s) dégradé(s) sur {decision.get('completed_by_regime_state', {}).get('regime_off', 0)}",
            "",
            "## 4. Recommandations",
            "",
            recommendations,
            "",
            "## 5. Règle de lecture",
            "",
            "- **Effet `ml_mode=off` positif** : couper le ML actuel améliore la métrique.",
            "- **Effet régime ON positif** : garder le régime améliore la métrique.",
            "- **Amélioration DD positive** : la baisse du drawdown est favorable.",
            "- **Synergie positive** : le combo se comporte mieux que la somme naïve des effets isolés.",
            "",
        ]
    )


def write_rows_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
        "window_id",
        "variant_id",
        "status",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_outputs(*, rows: list[dict[str, Any]], effects: dict[str, Any], decision: dict[str, Any], output_root: Path) -> dict[str, Path]:
    summary_json = output_root / "ablation_summary.json"
    summary_csv = output_root / "ablation_runs.csv"
    decision_md = output_root / "ablation_decision.md"
    payload = {
        "generated_at": _iso_now(),
        "rows": rows,
        "factorial_effects": effects,
        "decision": decision,
    }
    _write_json(summary_json, payload)
    write_rows_csv(rows, summary_csv)
    decision_md.write_text(
        build_decision_markdown(rows=rows, effects=effects, decision=decision, output_root=output_root),
        encoding="utf-8",
    )
    return {
        "summary_json": summary_json,
        "summary_csv": summary_csv,
        "decision_md": decision_md,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prépare et/ou exécute une ablation multi-fenêtres ML vs régime.")
    parser.add_argument("--execute", action="store_true", help="Exécute réellement les backtests séquentiellement.")
    parser.add_argument("--skip-existing", action="store_true", help="Ne relance pas un run si `report.json` existe déjà.")
    parser.add_argument("--stop-on-error", action="store_true", help="Arrête l'exécution au premier run en échec.")
    parser.add_argument(
        "--window-preset",
        choices=tuple(DEFAULT_WINDOWS.keys()),
        default="core_2020",
        help="Preset de fenêtres à utiliser si `--windows-file` n'est pas fourni.",
    )
    parser.add_argument(
        "--windows-file",
        type=Path,
        default=None,
        help="Fichier JSON facultatif décrivant une liste de fenêtres {window_id,start,end,description}.",
    )
    parser.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG, help="Config YAML source à figer.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Racine des artefacts d'ablation.")
    parser.add_argument("--python-executable", type=Path, default=Path(sys.executable), help="Interpréteur Python à utiliser pour les sous-processus.")

    parser.add_argument("--equity", type=float, default=2000.0)
    parser.add_argument("--tp", type=float, default=0.08)
    parser.add_argument("--ts", type=float, default=0.05)
    parser.add_argument("--max-positions", type=int, default=3)
    parser.add_argument("--commission-bps", type=float, default=15.0)
    parser.add_argument("--slippage-bps", type=float, default=25.0)
    parser.add_argument("--account-type", choices=("margin", "cash"), default="cash")
    _add_bool_argument(
        parser,
        name="swing-only",
        default=True,
        help_enabled="Force le mode swing-only (défaut).",
        help_disabled="Désactive le mode swing-only.",
    )
    _add_bool_argument(
        parser,
        name="allow-fractional-shares",
        default=True,
        help_enabled="Autorise les fractions de titres (défaut).",
        help_disabled="Interdit les fractions de titres.",
    )
    parser.add_argument("--sentiment-lookback", type=int, default=365)
    parser.add_argument("--sentiment-mode", choices=("auto", "off", "rebuild-missing"), default="auto")
    parser.add_argument("--engine-mode", choices=("research", "pipeline"), default="pipeline")
    parser.add_argument("--scores-pit-mode", choices=("exact", "asof_latest"), default="exact")
    parser.add_argument("--macro-pit-mode", choices=("yaml_default", "asof_inclusive", "j_minus_1_strict"), default="asof_inclusive")
    parser.add_argument(
        "--ml-pit-strategy",
        choices=("auto", "use-persisted", "rebuild-missing", "walk-forward-train-then-predict"),
        default="rebuild-missing",
    )
    parser.add_argument("--phase2-mode", choices=("off", "risk", "risk_execution"), default="risk_execution")
    parser.add_argument("--phase3-mode", choices=("off", "execution_replay"), default="execution_replay")
    parser.add_argument("--phase4-mode", choices=("off", "protection_replay"), default="protection_replay")
    parser.add_argument("--phase5-mode", choices=("off", "watcher_replay"), default="watcher_replay")
    parser.add_argument("--phase7-mode", choices=("off", "exit_lifecycle_replay"), default="exit_lifecycle_replay")
    parser.add_argument("--capital-preset-key", default="capital_0_2000_eur")
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--score-column", choices=("auto", "final_score_walk_forward", "final_score_sentiment", "final_score"), default="auto")
    parser.add_argument("--walk-forward-artifacts-dir", type=Path, default=None)
    parser.add_argument("--risk-free-rate", type=float, default=0.0)
    parser.add_argument("--max-entry-gap-pct", type=float, default=0.03)
    parser.add_argument("--max-sector-exposure-pct", type=float, default=0.25)
    parser.add_argument("--max-portfolio-dd-pct", type=float, default=0.10)
    parser.add_argument("--dd-recovery-pct", type=float, default=0.95)
    parser.add_argument("--dd-rolling-peak-window-days", type=int, default=252)
    parser.add_argument("--dd-degraded-allocation-pct", type=float, default=0.02)
    parser.add_argument("--target-annual-vol", type=float, default=0.12)
    parser.add_argument("--min-ml-coverage-ratio", type=float, default=None)
    _add_bool_argument(
        parser,
        name="allow-neutral-fallback-on-missing-macro-data",
        default=True,
        help_enabled="Autorise le fallback neutre si la macro manque (défaut).",
        help_disabled="Échoue si la macro est indisponible.",
    )
    _add_bool_argument(
        parser,
        name="use-cache",
        default=True,
        help_enabled="Active le cache Parquet local (défaut).",
        help_disabled="Désactive le cache Parquet local.",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--seed", type=int, default=None)
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    args.base_config = args.base_config.resolve()
    args.output_root = args.output_root.resolve()
    args.python_executable = args.python_executable.resolve()
    args.artifacts_dir = args.artifacts_dir.resolve()
    if args.walk_forward_artifacts_dir is not None:
        args.walk_forward_artifacts_dir = args.walk_forward_artifacts_dir.resolve()
    args.cache_dir = args.cache_dir.resolve()

    if not args.base_config.is_file():
        parser.error(f"Configuration introuvable: {args.base_config}")

    windows = resolve_windows(args.window_preset, args.windows_file.resolve() if args.windows_file else None)
    args.output_root.mkdir(parents=True, exist_ok=True)

    config_paths = write_frozen_runtime_configs(base_config_path=args.base_config, output_root=args.output_root)
    plans = build_run_plans(args, windows=windows, config_paths=config_paths)
    manifest_path = write_plan_manifest(plans, output_root=args.output_root, config_paths=config_paths, base_config_path=args.base_config)
    launcher_path = write_powershell_launcher(plans, output_root=args.output_root)

    execution_log: list[dict[str, Any]] = []
    if args.execute:
        execution_log = execute_plans(plans, skip_existing=bool(args.skip_existing), stop_on_error=bool(args.stop_on_error))
        _write_json(args.output_root / "execution_log.json", execution_log)

    rows = collect_run_rows(plans)
    effects = compute_factorial_effects(rows)
    decision = build_decision_summary(rows, effects)
    outputs = write_summary_outputs(rows=rows, effects=effects, decision=decision, output_root=args.output_root)

    summary_payload = {
        "generated_at": _iso_now(),
        "manifest_path": str(manifest_path),
        "launcher_path": str(launcher_path),
        "summary_outputs": {key: str(value) for key, value in outputs.items()},
        "execution_log_entries": len(execution_log),
        "completed_runs": sum(1 for row in rows if row.get("status") == "completed"),
        "complete_windows": effects.get("complete_window_count", 0),
    }
    _write_json(args.output_root / "run_overview.json", summary_payload)

    if args.execute and any(item.get("status") == "failed" for item in execution_log):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())



