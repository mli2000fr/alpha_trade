"""Prépare une mini-matrice de recalibration ciblée (R11a → R11c).

Objectif : isoler proprement la famille de contraintes soft qui coûte le plus,
à partir de la baseline gagnante R5.

Le script génère :
- des configs YAML complètes dérivées de ``config.yaml`` ;
- un manifest JSON décrivant les variantes ;
- un lanceur PowerShell pour exécuter ``scripts.run_ml_regime_ablation``
  sur chaque variante.

Usage minimal::

    python -m scripts.prepare_regime_recalibration_matrix_r11

Exécution directe de toute la matrice::

    python -m scripts.prepare_regime_recalibration_matrix_r11 --execute --skip-existing
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_CONFIG = PROJECT_ROOT / "config.yaml"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "ablation" / "regime_recalibration_matrix_r11"
DEFAULT_MIN_ML_COVERAGE_RATIO = 0.8
DEFAULT_WINDOW_PRESET = "core_2020"

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


@dataclass(frozen=True, slots=True)
class VariantSpec:
    variant_id: str
    title: str
    hypothesis: str
    overrides: dict[str, Any]


VARIANT_SPECS: tuple[VariantSpec, ...] = (
    VariantSpec(
        variant_id="R11a",
        title="Base R5 + neutralisation du risk_mult soft yields",
        hypothesis=(
            "Tester si le coût principal vient du multiplicateur de risque soft sur spike de taux. "
            "On conserve secteurs bloqués et caps soft, mais on retire le ralentissement de sizing global."
        ),
        overrides={
            "market_regimes": {
                **R5_BASE_OVERRIDES["market_regimes"],
                "yields": {
                    **R5_BASE_OVERRIDES["market_regimes"]["yields"],
                    "risk_mult": 1.0,
                },
            },
        },
    ),
    VariantSpec(
        variant_id="R11b",
        title="Base R5 + suppression du blocage sectoriel soft yields",
        hypothesis=(
            "Tester si le vrai coût vient surtout de la blacklist sectorielle / high-beta lors des spikes soft de taux. "
            "On conserve le risk_mult et les caps, mais on retire le filtrage sectoriel soft."
        ),
        overrides={
            "market_regimes": {
                **R5_BASE_OVERRIDES["market_regimes"],
                "yields": {
                    **R5_BASE_OVERRIDES["market_regimes"]["yields"],
                    "block_sectors": [],
                    "block_high_beta": False,
                },
            },
        },
    ),
    VariantSpec(
        variant_id="R11c",
        title="Base R5 + suppression des caps soft yields",
        hypothesis=(
            "Tester si le coût principal vient des caps soft (max positions / poids / gross exposure) plutôt que du signal lui-même. "
            "On garde le risk_mult et le blocage sectoriel soft, mais on retire les caps soft spécifiques yields."
        ),
        overrides={
            "market_regimes": {
                **R5_BASE_OVERRIDES["market_regimes"],
                "yields": {
                    **R5_BASE_OVERRIDES["market_regimes"]["yields"],
                    "soft_max_positions": None,
                    "soft_max_position_weight": None,
                    "soft_max_sector_weight": None,
                    "soft_max_gross_exposure": None,
                },
            },
        },
    ),
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


def write_variant_configs(*, base_payload: dict[str, Any], output_root: Path) -> dict[str, Path]:
    configs_dir = output_root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    config_paths: dict[str, Path] = {}
    for variant in VARIANT_SPECS:
        merged = deep_merge(base_payload, variant.overrides)
        config_path = configs_dir / f"{variant.variant_id}.yaml"
        config_path.write_text(
            yaml.safe_dump(merged, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        config_paths[variant.variant_id] = config_path
    return config_paths


def build_variant_command(
    args: argparse.Namespace,
    *,
    config_path: Path,
    output_root: Path,
) -> tuple[str, ...]:
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
    return tuple(command)


def build_run_commands(args: argparse.Namespace, *, config_paths: dict[str, Path], output_root: Path) -> tuple[RunCommand, ...]:
    commands: list[RunCommand] = []
    variants_root = output_root / "variants"
    for variant in VARIANT_SPECS:
        variant_output_root = variants_root / variant.variant_id
        commands.append(
            RunCommand(
                variant_id=variant.variant_id,
                config_path=config_paths[variant.variant_id],
                output_root=variant_output_root,
                command=build_variant_command(
                    args,
                    config_path=config_paths[variant.variant_id],
                    output_root=variant_output_root,
                ),
            )
        )
    return tuple(commands)


def write_manifest(*, output_root: Path, base_config: Path, commands: tuple[RunCommand, ...]) -> Path:
    payload = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(timespec="seconds"),
        "project_root": str(PROJECT_ROOT),
        "base_config": str(base_config),
        "variants": [
            {
                **asdict(spec),
                "config_path": str(next(cmd.config_path for cmd in commands if cmd.variant_id == spec.variant_id)),
                "output_root": str(next(cmd.output_root for cmd in commands if cmd.variant_id == spec.variant_id)),
                "command": list(next(cmd.command for cmd in commands if cmd.variant_id == spec.variant_id)),
                "command_line": subprocess.list2cmdline(list(next(cmd.command for cmd in commands if cmd.variant_id == spec.variant_id))),
            }
            for spec in VARIANT_SPECS
        ],
    }
    manifest_path = output_root / "regime_recalibration_manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def write_launcher(*, output_root: Path, commands: tuple[RunCommand, ...]) -> Path:
    launcher_path = output_root / "run_all.ps1"
    lines = [
        '$ErrorActionPreference = "Stop"',
        f'Push-Location "{PROJECT_ROOT}"',
        "try {",
    ]
    for item in commands:
        cmdline = subprocess.list2cmdline(list(build_launcher_command(item.command)))
        lines.append(f'  Write-Host "==> {item.variant_id}"')
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


def execute_commands(commands: tuple[RunCommand, ...]) -> list[dict[str, Any]]:
    execution_log: list[dict[str, Any]] = []
    for item in commands:
        item.output_root.mkdir(parents=True, exist_ok=True)
        stdout_log = item.output_root / "matrix_stdout.log"
        stderr_log = item.output_root / "matrix_stderr.log"
        with stdout_log.open("w", encoding="utf-8") as stdout_handle, stderr_log.open("w", encoding="utf-8") as stderr_handle:
            completed = subprocess.run(
                list(item.command),
                cwd=PROJECT_ROOT,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
                check=False,
            )
        execution_log.append(
            {
                "variant_id": item.variant_id,
                "returncode": completed.returncode,
                "status": "completed" if completed.returncode == 0 else "failed",
                "output_root": str(item.output_root),
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
            }
        )
    return execution_log


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prépare une mini-matrice ciblée de recalibration du régime (R11a → R11c).")
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

    config_paths = write_variant_configs(base_payload=base_payload, output_root=output_root)
    commands = build_run_commands(args, config_paths=config_paths, output_root=output_root)
    manifest_path = write_manifest(output_root=output_root, base_config=args.base_config.resolve(), commands=commands)
    launcher_path = write_launcher(output_root=output_root, commands=commands)

    overview_path = output_root / "matrix_overview.json"
    overview_path.write_text(
        json.dumps(
            {
                "manifest_path": str(manifest_path),
                "launcher_path": str(launcher_path),
                "variant_count": len(commands),
                "variants": [item.variant_id for item in commands],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Configs écrites : {len(config_paths)}")
    print(f"Manifest écrit : {manifest_path}")
    print(f"Launcher écrit : {launcher_path}")
    print(f"Overview écrit : {overview_path}")

    if args.execute:
        execution_log = execute_commands(commands)
        execution_log_path = output_root / "execution_log.json"
        execution_log_path.write_text(json.dumps(execution_log, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Execution log écrit : {execution_log_path}")
        return 0 if all(item["returncode"] == 0 for item in execution_log) else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

