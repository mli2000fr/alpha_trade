from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MATRIX_ROOT = PROJECT_ROOT / "artifacts" / "ablation" / "regime_recalibration_matrix"
DEFAULT_PROMPT_PATH = PROJECT_ROOT / "prompt" / "regime.md"
DEFAULT_BASELINE_ROOT = PROJECT_ROOT / "artifacts" / "ablation" / "ml_regime_objective_structural_fix_full"
DEFAULT_VARIANTS = ("R1", "R2", "R3", "R4", "R5")
WINDOW_ORDER = (
    "2020_q1_crash",
    "2020_q2_rebound",
    "2020_q3_momentum",
    "2020_q4_rotation",
    "2020_full_year",
)
WINDOW_LABELS = {
    "2020_q1_crash": "Q1 crash",
    "2020_q2_rebound": "Q2 rebound",
    "2020_q3_momentum": "Q3 momentum",
    "2020_q4_rotation": "Q4 rotation",
    "2020_full_year": "Full year",
}
SECTION_11_PREFIX = "## 11."


@dataclass(frozen=True, slots=True)
class VariantResult:
    variant_id: str
    title: str
    hypothesis: str
    output_root: Path
    summary_path: Path
    decision_path: Path
    summary: dict[str, Any]
    mode_by_window: dict[str, dict[str, int]]
    blocked_by_window: dict[str, int]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_float(value: float | int | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def format_signed(value: float | int | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):+.{digits}f}"


def total_mode_counts(mode_by_window: dict[str, dict[str, int]]) -> dict[str, int]:
    totals = {"normal": 0, "capital_preservation": 0, "cash_only": 0}
    for modes in mode_by_window.values():
        for key in totals:
            totals[key] += int(modes.get(key, 0))
    return totals


def load_control_phase2(output_root: Path) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    mode_by_window: dict[str, dict[str, int]] = {}
    blocked_by_window: dict[str, int] = {}
    runs_root = output_root / "runs"
    for window_id in WINDOW_ORDER:
        phase2_path = runs_root / window_id / "control" / "phase2_risk_summary.json"
        if not phase2_path.is_file():
            continue
        payload = load_json(phase2_path)
        mode_by_window[window_id] = {
            "normal": int(payload.get("regime_mode_distribution", {}).get("normal", 0)),
            "capital_preservation": int(payload.get("regime_mode_distribution", {}).get("capital_preservation", 0)),
            "cash_only": int(payload.get("regime_mode_distribution", {}).get("cash_only", 0)),
        }
        blocked_by_window[window_id] = int(payload.get("entries_blocked_by_regime", 0))
    return mode_by_window, blocked_by_window


def wait_for_variant_outputs(variant_roots: dict[str, Path], *, poll_seconds: int, timeout_seconds: int | None) -> None:
    deadline = None if timeout_seconds is None else time.monotonic() + timeout_seconds
    while True:
        missing = [
            variant_id
            for variant_id, root in variant_roots.items()
            if not (root / "ablation_summary.json").is_file() or not (root / "ablation_decision.md").is_file()
        ]
        if not missing:
            return
        if deadline is not None and time.monotonic() >= deadline:
            missing_str = ", ".join(missing)
            raise TimeoutError(f"Sorties manquantes après attente: {missing_str}")
        time.sleep(poll_seconds)


def load_variant_results(matrix_root: Path, *, wait: bool, poll_seconds: int, timeout_seconds: int | None) -> tuple[list[VariantResult], list[dict[str, Any]]]:
    manifest_path = matrix_root / "regime_recalibration_manifest.json"
    manifest = load_json(manifest_path)
    variants: list[dict[str, Any]] = manifest.get("variants", [])
    variant_roots = {item["variant_id"]: Path(item["output_root"]) for item in variants}
    if wait:
        wait_for_variant_outputs(variant_roots, poll_seconds=poll_seconds, timeout_seconds=timeout_seconds)

    results: list[VariantResult] = []
    for item in variants:
        output_root = Path(item["output_root"])
        summary_path = output_root / "ablation_summary.json"
        decision_path = output_root / "ablation_decision.md"
        if not summary_path.is_file() or not decision_path.is_file():
            raise FileNotFoundError(f"Sorties incomplètes pour {item['variant_id']}: {output_root}")
        mode_by_window, blocked_by_window = load_control_phase2(output_root)
        results.append(
            VariantResult(
                variant_id=item["variant_id"],
                title=str(item.get("title", item["variant_id"])),
                hypothesis=str(item.get("hypothesis", "")),
                output_root=output_root,
                summary_path=summary_path,
                decision_path=decision_path,
                summary=load_json(summary_path),
                mode_by_window=mode_by_window,
                blocked_by_window=blocked_by_window,
            )
        )
    return results, variants


def extract_effect(summary: dict[str, Any], effect_key: str = "regime_on_effect") -> dict[str, Any]:
    return summary.get("factorial_effects", {}).get(effect_key, {})


def extract_per_window(summary: dict[str, Any], window_id: str, effect_key: str = "regime_on_effect") -> dict[str, float | None]:
    window_payload = summary.get("factorial_effects", {}).get("per_window", {}).get(window_id, {})
    return {
        "return": window_payload.get("total_return_pct", {}).get(effect_key),
        "sharpe": window_payload.get("sharpe_ratio", {}).get(effect_key),
        "dd": window_payload.get("max_drawdown_pct", {}).get(effect_key),
    }


def variant_score(variant: VariantResult, baseline_blocked: dict[str, int]) -> tuple[int, float, float, float]:
    summary = extract_effect(variant.summary)
    per_window_q1 = extract_per_window(variant.summary, "2020_q1_crash")
    per_window_q2 = extract_per_window(variant.summary, "2020_q2_rebound")
    per_window_q4 = extract_per_window(variant.summary, "2020_q4_rotation")
    per_window_fy = extract_per_window(variant.summary, "2020_full_year")

    score = 0
    if (per_window_q1["dd"] or 0.0) >= -0.5:
        score += 1
    if (variant.blocked_by_window.get("2020_q2_rebound", 10**9) < baseline_blocked.get("2020_q2_rebound", 10**9)) and ((per_window_q2["return"] or -10**9) >= -0.5):
        score += 1
    if (variant.blocked_by_window.get("2020_q4_rotation", 10**9) < baseline_blocked.get("2020_q4_rotation", 10**9)) and ((per_window_q4["return"] or -10**9) >= -0.5):
        score += 1
    fy_return = per_window_fy["return"] or -10**9
    fy_dd = per_window_fy["dd"] or -10**9
    if fy_return >= 0.0 or (fy_return >= -0.25 and fy_dd > 0.25):
        score += 1

    return (
        score,
        float(summary.get("total_return_pct", {}).get("mean", float("-inf"))),
        float(summary.get("sharpe_ratio", {}).get("mean", float("-inf"))),
        float(summary.get("drawdown_improvement", {}).get("mean", float("-inf"))),
    )


def build_overview_table(variant_results: list[VariantResult], baseline_summary: dict[str, Any], baseline_modes: dict[str, dict[str, int]], baseline_blocked: dict[str, int]) -> str:
    lines = [
        "| Variante | Return moyen effet régime | Sharpe moyen effet régime | DD moyen effet régime | Fenêtres return + | Fenêtres DD + | Q1 DD | FY return | Cash-only total | Entrées bloquées Q2/Q4/FY |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]

    base_effect = extract_effect(baseline_summary)
    base_totals = total_mode_counts(baseline_modes)
    base_q1 = extract_per_window(baseline_summary, "2020_q1_crash")
    base_fy = extract_per_window(baseline_summary, "2020_full_year")
    lines.append(
        "| Baseline actuelle | "
        f"{format_signed(base_effect.get('total_return_pct', {}).get('mean'))} | "
        f"{format_signed(base_effect.get('sharpe_ratio', {}).get('mean'))} | "
        f"{format_signed(base_effect.get('drawdown_improvement', {}).get('mean'))} | "
        f"{base_effect.get('total_return_pct', {}).get('positive_windows', 'n/a')} | "
        f"{base_effect.get('drawdown_improvement', {}).get('positive_windows', 'n/a')} | "
        f"{format_signed(base_q1['dd'])} | "
        f"{format_signed(base_fy['return'])} | "
        f"{base_totals.get('cash_only', 0)} | "
        f"{baseline_blocked.get('2020_q2_rebound', 0)}/{baseline_blocked.get('2020_q4_rotation', 0)}/{baseline_blocked.get('2020_full_year', 0)} |"
    )

    for item in variant_results:
        effect = extract_effect(item.summary)
        totals = total_mode_counts(item.mode_by_window)
        q1 = extract_per_window(item.summary, "2020_q1_crash")
        fy = extract_per_window(item.summary, "2020_full_year")
        lines.append(
            f"| {item.variant_id} | "
            f"{format_signed(effect.get('total_return_pct', {}).get('mean'))} | "
            f"{format_signed(effect.get('sharpe_ratio', {}).get('mean'))} | "
            f"{format_signed(effect.get('drawdown_improvement', {}).get('mean'))} | "
            f"{effect.get('total_return_pct', {}).get('positive_windows', 'n/a')} | "
            f"{effect.get('drawdown_improvement', {}).get('positive_windows', 'n/a')} | "
            f"{format_signed(q1['dd'])} | "
            f"{format_signed(fy['return'])} | "
            f"{totals.get('cash_only', 0)} | "
            f"{item.blocked_by_window.get('2020_q2_rebound', 0)}/{item.blocked_by_window.get('2020_q4_rotation', 0)}/{item.blocked_by_window.get('2020_full_year', 0)} |"
        )
    return "\n".join(lines)


def build_per_window_table(variant_results: list[VariantResult]) -> str:
    lines = [
        "| Variante | Fenêtre | Effet return | Effet Sharpe | Effet DD | Normal | Capital preservation | Cash only | Entrées bloquées |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in variant_results:
        for window_id in WINDOW_ORDER:
            effect = extract_per_window(item.summary, window_id)
            modes = item.mode_by_window.get(window_id, {})
            lines.append(
                f"| {item.variant_id} | {WINDOW_LABELS[window_id]} | "
                f"{format_signed(effect['return'])} | "
                f"{format_signed(effect['sharpe'])} | "
                f"{format_signed(effect['dd'])} | "
                f"{modes.get('normal', 0)} | "
                f"{modes.get('capital_preservation', 0)} | "
                f"{modes.get('cash_only', 0)} | "
                f"{item.blocked_by_window.get(window_id, 0)} |"
            )
    return "\n".join(lines)


def build_mode_summary_table(variant_results: list[VariantResult], baseline_modes: dict[str, dict[str, int]], baseline_blocked: dict[str, int]) -> str:
    lines = [
        "| Variante | Normal total | Capital preservation total | Cash only total | Entrées bloquées total |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    baseline_totals = total_mode_counts(baseline_modes)
    lines.append(
        f"| Baseline actuelle | {baseline_totals.get('normal', 0)} | {baseline_totals.get('capital_preservation', 0)} | {baseline_totals.get('cash_only', 0)} | {sum(baseline_blocked.values())} |"
    )
    for item in variant_results:
        totals = total_mode_counts(item.mode_by_window)
        lines.append(
            f"| {item.variant_id} | {totals.get('normal', 0)} | {totals.get('capital_preservation', 0)} | {totals.get('cash_only', 0)} | {sum(item.blocked_by_window.values())} |"
        )
    return "\n".join(lines)


def build_recommendation(best_variant: VariantResult, variant_results: list[VariantResult], baseline_blocked: dict[str, int]) -> str:
    best_effect = extract_effect(best_variant.summary)
    best_totals = total_mode_counts(best_variant.mode_by_window)
    q2_blocked_delta = best_variant.blocked_by_window.get("2020_q2_rebound", 0) - baseline_blocked.get("2020_q2_rebound", 0)
    q4_blocked_delta = best_variant.blocked_by_window.get("2020_q4_rotation", 0) - baseline_blocked.get("2020_q4_rotation", 0)
    fy_blocked_delta = best_variant.blocked_by_window.get("2020_full_year", 0) - baseline_blocked.get("2020_full_year", 0)

    ordered = sorted(variant_results, key=lambda item: variant_score(item, baseline_blocked), reverse=True)
    ranking = ", ".join(item.variant_id for item in ordered)

    lines = [
        f"- Variante en tête selon les critères A→D : **{best_variant.variant_id}** — {best_variant.title}.",
        f"- Effet moyen du régime sur cette variante : return `{format_signed(best_effect.get('total_return_pct', {}).get('mean'))}`, Sharpe `{format_signed(best_effect.get('sharpe_ratio', {}).get('mean'))}`, amélioration DD `{format_signed(best_effect.get('drawdown_improvement', {}).get('mean'))}`.",
        f"- Réduction des blocages sur les fenêtres sensibles : Q2 `{q2_blocked_delta:+d}`, Q4 `{q4_blocked_delta:+d}`, full year `{fy_blocked_delta:+d}` vs baseline actuelle (valeur négative = moins de blocages).",
        f"- Distribution agrégée des modes pour {best_variant.variant_id} : normal `{best_totals.get('normal', 0)}`, capital_preservation `{best_totals.get('capital_preservation', 0)}`, cash_only `{best_totals.get('cash_only', 0)}`.",
        f"- Classement synthétique observé : `{ranking}`.",
    ]
    return "\n".join(lines)


def build_generated_section(*, matrix_root: Path, baseline_root: Path, variant_results: list[VariantResult], baseline_summary: dict[str, Any], baseline_modes: dict[str, dict[str, int]], baseline_blocked: dict[str, int]) -> str:
    ordered = sorted(variant_results, key=lambda item: variant_score(item, baseline_blocked), reverse=True)
    best_variant = ordered[0]
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    return "\n".join(
        [
            "## 11. Mise à jour après exécution (générée automatiquement)",
            "",
            f"- Généré le : `{generated_at}`",
            f"- Matrice : `{matrix_root}`",
            f"- Baseline de comparaison : `{baseline_root}`",
            "",
            "### Tableau comparatif R1→R5 vs baseline actuelle",
            "",
            build_overview_table(variant_results, baseline_summary, baseline_modes, baseline_blocked),
            "",
            "### Effets par fenêtre + distribution des modes (`control`)",
            "",
            build_per_window_table(variant_results),
            "",
            "### Distribution agrégée des modes",
            "",
            build_mode_summary_table(variant_results, baseline_modes, baseline_blocked),
            "",
            "### Recommandation finale",
            "",
            build_recommendation(best_variant, variant_results, baseline_blocked),
            "",
            "### Artefacts de référence",
            "",
            "- `ablation_summary.json` et `ablation_decision.md` de chaque variante dans `artifacts/ablation/regime_recalibration_matrix/variants/R{1..5}/`",
            "- `phase2_risk_summary.json` de chaque run `control` pour la lecture des modes",
            "",
        ]
    )


def replace_section_11(prompt_text: str, generated_section: str) -> str:
    marker = prompt_text.find(SECTION_11_PREFIX)
    if marker == -1:
        raise ValueError("Section 11 introuvable dans prompt/regime.md")
    return prompt_text[:marker].rstrip() + "\n\n" + generated_section.rstrip() + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Attend la fin de la matrice R1→R5 puis met à jour prompt/regime.md.")
    parser.add_argument("--matrix-root", type=Path, default=DEFAULT_MATRIX_ROOT)
    parser.add_argument("--prompt-path", type=Path, default=DEFAULT_PROMPT_PATH)
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--timeout-seconds", type=int, default=None)
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    matrix_root = args.matrix_root.resolve()
    prompt_path = args.prompt_path.resolve()
    baseline_root = args.baseline_root.resolve()

    if not (matrix_root / "regime_recalibration_manifest.json").is_file():
        parser.error(f"Manifest introuvable: {matrix_root / 'regime_recalibration_manifest.json'}")
    if not prompt_path.is_file():
        parser.error(f"Prompt introuvable: {prompt_path}")

    baseline_summary_path = baseline_root / "ablation_summary.json"
    if not baseline_summary_path.is_file():
        parser.error(f"Baseline summary introuvable: {baseline_summary_path}")

    variant_results, _ = load_variant_results(
        matrix_root,
        wait=args.wait,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    baseline_summary = load_json(baseline_summary_path)
    baseline_modes, baseline_blocked = load_control_phase2(baseline_root)

    generated_section = build_generated_section(
        matrix_root=matrix_root,
        baseline_root=baseline_root,
        variant_results=variant_results,
        baseline_summary=baseline_summary,
        baseline_modes=baseline_modes,
        baseline_blocked=baseline_blocked,
    )
    prompt_text = prompt_path.read_text(encoding="utf-8")
    updated_prompt = replace_section_11(prompt_text, generated_section)
    prompt_path.write_text(updated_prompt, encoding="utf-8")
    print(f"prompt mis à jour: {prompt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

