"""Prépare l'ablation dédiée du régime R10 (gating soft sélectif).

Le script génère :
- une config YAML complète ``R10.yaml`` dérivée de ``config.yaml`` ;
- un manifest JSON décrivant l'expérience ;
- un lanceur PowerShell pour exécuter ``scripts.run_ml_regime_ablation``
  sur cette variante.

Usage minimal::

    python -m scripts.prepare_regime_recalibration_r10

Exécution directe::

    python -m scripts.prepare_regime_recalibration_r10 --execute --skip-existing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_CONFIG = PROJECT_ROOT / "config.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "ablation" / "regime_hysteresis_r10"
DEFAULT_MIN_ML_COVERAGE_RATIO = 0.8
DEFAULT_WINDOW_PRESET = "core_2020"
DEFAULT_VARIANT_ID = "R10"

R5_BASE_OVERRIDES: dict[str, Any] = {
    "market_regimes": {
        "capital_preservation_max_gross_exposure": 0.65,
        "vix": {
            "high_threshold": 30.0,
        },
        "sentiment_circuit_breaker": {
            "warning_threshold": -0.20,
            "critical_threshold": -0.40,
            "critical_mode_backtest": "capital_preservation",
            "warning_max_positions": 3,
        },
        "yields": {
            "relative_spike_threshold": 0.07,
            "hard_relative_spike_threshold": 0.10,
            "hard_mode_backtest": "capital_preservation",
            "soft_max_positions": 3,
            "soft_max_position_weight": 0.25,
            "soft_max_sector_weight": 0.30,
            "soft_max_gross_exposure": 0.65,
        },
    },
}

R10_HYSTERESIS_OVERRIDES: dict[str, Any] = {
    "market_regimes": {
        "hysteresis": {
            "enabled": True,
            "enter_soft_signals_required": 2,
            "enter_confirm_days": 2,
            "exit_soft_signals_max": 0,
            "exit_confirm_days": 3,
            "min_hold_days_defensive": 5,
            "hard_trigger_immediate": True,
            "hard_exit_confirm_days": 2,
            "gate_soft_constraints_on_confirmed_entry": False,
            "gate_soft_risk_multiplier_on_confirmed_entry": False,
            "gate_soft_position_limits_on_confirmed_entry": True,
            "gate_soft_exposure_caps_on_confirmed_entry": True,
            "gate_soft_sector_blocks_on_confirmed_entry": False,
        },
    },
}


@dataclass(frozen=True, slots=True)
class VariantSpec:
    variant_id: str
    title: str
    hypothesis: str
    overrides: dict[str, Any]


VARIANT = VariantSpec(
    variant_id=DEFAULT_VARIANT_ID,
    title="Base R5 + hystérésis R10 à gating soft sélectif",
    hypothesis=(
        "Tester si un gating sélectif qui garde risk_multiplier et blocages sectoriels immédiats, "
        "mais diffère seulement position_limits et exposure_caps jusqu'à confirmation, réduit le drag "
        "sans reproduire l'échec plus global de R9.1."
    ),
    overrides={
        "market_regimes": {
            **R5_BASE_OVERRIDES["market_regimes"],
            **R10_HYSTERESIS_OVERRIDES["market_regimes"],
        },
    },
)


@dataclass(frozen=True, slots=True)
class RunCommand:
    variant_id: str
    config_path: Path
    output_root: Path
    command: tuple[str, ...]


def build_launcher_command(command: tuple[str, ...]) -> tuple[str, ...]:
    launcher_command = list(command)
    if "--execute" not in launcher_command:
        launcher_command.append("--execute")
    return tuple(launcher_command)


def _deep_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload))


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = _deep_copy(base)
    for key, value in overrides.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def load_base_payload(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration YAML invalide: {path}")
    return payload


def write_variant_config(*, base_payload: dict[str, Any], output_root: Path) -> Path:
    configs_dir = output_root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    merged = deep_merge(base_payload, VARIANT.overrides)
    config_path = configs_dir / f"{VARIANT.variant_id}.yaml"
    config_path.write_text(
        yaml.safe_dump(merged, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


def build_run_command(
    args: argparse.Namespace,
    *,
    config_path: Path,
    output_root: Path,
) -> RunCommand:
    command: list[str] = [
        str(args.python_executable),
        "-u",
        "-m",
        "scripts.run_ml_regime_ablation",
        "--base-config",
        str(config_path),
        "--output-root",
        str(output_root),
        "--window-preset",
        args.window_preset,
        "--min-ml-coverage-ratio",
        str(args.min_ml_coverage_ratio),
    ]
    if args.windows_file is not None:
        command.extend(["--windows-file", str(args.windows_file)])
    if args.execute:
        command.append("--execute")
    if args.skip_existing:
        command.append("--skip-existing")
    return RunCommand(
        variant_id=VARIANT.variant_id,
        config_path=config_path,
        output_root=output_root / "variants" / VARIANT.variant_id,
        command=tuple(command),
    )


def write_manifest(*, output_root: Path, base_config: Path, run_command: RunCommand) -> Path:
    launcher_command = build_launcher_command(run_command.command)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "project_root": str(PROJECT_ROOT),
        "base_config": str(base_config),
        "variant": {
            **asdict(VARIANT),
            "config_path": str(run_command.config_path),
            "output_root": str(run_command.output_root),
            "command": list(run_command.command),
            "command_line": subprocess.list2cmdline(list(run_command.command)),
            "launcher_command": list(launcher_command),
            "launcher_command_line": subprocess.list2cmdline(list(launcher_command)),
        },
    }
    manifest_path = output_root / "r10_manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def write_launcher(*, output_root: Path, run_command: RunCommand) -> Path:
    launcher_path = output_root / "run_r10.ps1"
    cmdline = subprocess.list2cmdline(list(build_launcher_command(run_command.command)))
    lines = [
        '$ErrorActionPreference = "Stop"',
        f'Push-Location "{PROJECT_ROOT}"',
        "try {",
        f'  Write-Host "==> {run_command.variant_id} / R10"',
        f"  {cmdline}",
        "}",
        "finally {",
        "  Pop-Location",
        "}",
        "",
    ]
    launcher_path.write_text("\n".join(lines), encoding="utf-8")
    return launcher_path


def write_overview(*, output_root: Path, config_path: Path, manifest_path: Path, launcher_path: Path, run_command: RunCommand) -> Path:
    payload = {
        "variant_id": VARIANT.variant_id,
        "title": VARIANT.title,
        "config_path": str(config_path),
        "manifest_path": str(manifest_path),
        "launcher_path": str(launcher_path),
        "output_root": str(run_command.output_root),
    }
    overview_path = output_root / "r10_overview.json"
    overview_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return overview_path


def execute_command(run_command: RunCommand) -> dict[str, Any]:
    run_command.output_root.mkdir(parents=True, exist_ok=True)
    stdout_log = run_command.output_root / "matrix_stdout.log"
    stderr_log = run_command.output_root / "matrix_stderr.log"
    with stdout_log.open("w", encoding="utf-8") as stdout_handle, stderr_log.open("w", encoding="utf-8") as stderr_handle:
        completed = subprocess.run(
            list(run_command.command),
            cwd=PROJECT_ROOT,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            check=False,
        )
    return {
        "variant_id": run_command.variant_id,
        "returncode": completed.returncode,
        "status": "completed" if completed.returncode == 0 else "failed",
        "output_root": str(run_command.output_root),
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prépare l'ablation dédiée du régime R10 (gating soft sélectif).")
    parser.add_argument("--base-config", type=Path, default=DEFAULT_BASE_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--python-executable", type=Path, default=Path(sys.executable))
    parser.add_argument("--window-preset", default=DEFAULT_WINDOW_PRESET, choices=("core_2020", "cross_cycle"))
    parser.add_argument("--windows-file", type=Path, default=None)
    parser.add_argument("--min-ml-coverage-ratio", type=float, default=DEFAULT_MIN_ML_COVERAGE_RATIO)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    base_payload = load_base_payload(args.base_config)
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    config_path = write_variant_config(base_payload=base_payload, output_root=output_root)
    run_command = build_run_command(args, config_path=config_path, output_root=output_root)
    manifest_path = write_manifest(output_root=output_root, base_config=args.base_config.resolve(), run_command=run_command)
    launcher_path = write_launcher(output_root=output_root, run_command=run_command)
    overview_path = write_overview(
        output_root=output_root,
        config_path=config_path,
        manifest_path=manifest_path,
        launcher_path=launcher_path,
        run_command=run_command,
    )

    print(f"Config écrite : {config_path}")
    print(f"Manifest écrit : {manifest_path}")
    print(f"Launcher écrit : {launcher_path}")
    print(f"Overview écrit : {overview_path}")

    if args.execute:
        execution_log = execute_command(run_command)
        execution_log_path = output_root / "execution_log.json"
        execution_log_path.write_text(json.dumps(execution_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Execution log écrit : {execution_log_path}")
        return int(execution_log["returncode"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

