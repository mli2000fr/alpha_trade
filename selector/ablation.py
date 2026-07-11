from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from selector.config import (
    ABLATION_MODE_SHADOW,
    AlphaScannerConfig,
    SelectorAblationPlan,
    apply_variant_spec_to_config,
    compute_config_diff,
    is_filter_effectively_enabled,
)

_PRIMARY_VARIANT_ID = "primary"
_DATA_QUALITY_GATED_FILTERS = {"spread", "earnings_blackout", "market_cap_ttl"}


@dataclass(frozen=True, slots=True)
class RuntimeSelectorVariant:
    variant_id: str
    description: str | None
    config: AlphaScannerConfig
    disabled_filters: tuple[str, ...]
    skipped_filters: tuple[str, ...]
    config_diff: dict[str, object]
    is_primary: bool = False


def resolve_runtime_variants(
    *,
    base_config: AlphaScannerConfig,
    primary_runtime_config: AlphaScannerConfig,
    data_quality_gate: dict[str, object] | None = None,
) -> tuple[RuntimeSelectorVariant, ...]:
    raw_skipped_filters = (data_quality_gate or {}).get("skipped_filters") or []
    skipped_iterable = raw_skipped_filters if isinstance(raw_skipped_filters, (list, tuple)) else []
    primary_skipped_filters = tuple(
        str(value).strip() for value in skipped_iterable if str(value).strip()
    )
    primary_variant = RuntimeSelectorVariant(
        variant_id=_PRIMARY_VARIANT_ID,
        description="baseline",
        config=primary_runtime_config,
        disabled_filters=(),
        skipped_filters=primary_skipped_filters,
        config_diff=compute_config_diff(base_config, primary_runtime_config),
        is_primary=True,
    )
    plan = getattr(base_config, "ablation_plan", None)
    if plan is None or plan.mode != ABLATION_MODE_SHADOW or not plan.variants:
        return (primary_variant,)

    resolved_variants: list[RuntimeSelectorVariant] = [primary_variant]
    inherited_skipped = set(primary_skipped_filters)
    for variant in plan.variants:
        variant_config = apply_variant_spec_to_config(primary_runtime_config, variant)
        for filter_key in inherited_skipped.intersection(_DATA_QUALITY_GATED_FILTERS):
            if is_filter_effectively_enabled(variant_config, filter_key):
                raise ValueError(
                    f"La variante `{variant.variant_id}` réactive le filtre `{filter_key}` alors qu'il a été désactivé par le data quality gate primaire."
                )
        config_diff = compute_config_diff(primary_runtime_config, variant_config)
        if not config_diff:
            raise ValueError(
                f"La variante `{variant.variant_id}` ne modifie effectivement aucun paramètre par rapport au primaire."
            )
        effective_skipped = tuple(dict.fromkeys([*primary_skipped_filters, *variant.disabled_filters]))
        resolved_variants.append(
            RuntimeSelectorVariant(
                variant_id=variant.variant_id,
                description=variant.description,
                config=variant_config,
                disabled_filters=variant.disabled_filters,
                skipped_filters=effective_skipped,
                config_diff=config_diff,
            )
        )
    return tuple(resolved_variants)


def _extract_selected_symbols(selected_df: pd.DataFrame) -> list[str]:
    if selected_df.empty or "symbol" not in selected_df.columns:
        return []
    symbols = [str(symbol).strip() for symbol in selected_df["symbol"].astype(str).tolist()]
    return [symbol for symbol in symbols if symbol]


def _build_variant_payload(
    *,
    variant: RuntimeSelectorVariant,
    selected_df: pd.DataFrame,
    rejected_by_filter: dict[str, int],
    primary_symbols: list[str] | None = None,
    include_selected_symbols: bool,
) -> dict[str, object]:
    selected_symbols = _extract_selected_symbols(selected_df)
    payload: dict[str, object] = {
        "variant_id": variant.variant_id,
        "description": variant.description,
        "disabled_filters": list(variant.disabled_filters),
        "skipped_filters": list(variant.skipped_filters),
        "config_diff": dict(sorted(variant.config_diff.items())),
        "selection_size": int(variant.config.selection_size),
        "selected_selections": int(len(selected_symbols)),
        "selection_fill_ratio": round((len(selected_symbols) / variant.config.selection_size), 4)
        if variant.config.selection_size > 0
        else 0.0,
        "top_symbols": selected_symbols[:5],
        "rejected_by_filter": dict(sorted(rejected_by_filter.items())),
    }
    if include_selected_symbols:
        payload["selected_symbols"] = selected_symbols
    if primary_symbols is None:
        return payload
    primary_set = set(primary_symbols)
    selected_set = set(selected_symbols)
    shared_symbols = [symbol for symbol in selected_symbols if symbol in primary_set]
    added_symbols = [symbol for symbol in selected_symbols if symbol not in primary_set]
    removed_symbols = [symbol for symbol in primary_symbols if symbol not in selected_set]
    payload["overlap_with_primary"] = {
        "count": int(len(shared_symbols)),
        "ratio_vs_primary": round((len(shared_symbols) / len(primary_symbols)), 4) if primary_symbols else 0.0,
        "ratio_vs_variant": round((len(shared_symbols) / len(selected_symbols)), 4) if selected_symbols else 0.0,
        "shared_top_symbols": shared_symbols[:5],
    }
    payload["selection_diff"] = {
        "added_symbols": added_symbols[:10],
        "removed_symbols": removed_symbols[:10],
        "added_count": int(len(added_symbols)),
        "removed_count": int(len(removed_symbols)),
    }
    return payload


def build_ablation_summary_and_artifact(
    *,
    plan: SelectorAblationPlan,
    runtime_variants: tuple[RuntimeSelectorVariant, ...],
    selected_by_variant: dict[str, pd.DataFrame],
    rejected_by_filter_by_variant: dict[str, dict[str, int]],
    artifact_path: str | None,
) -> tuple[dict[str, object], dict[str, object]]:
    primary_variant = runtime_variants[0]
    primary_selected = selected_by_variant.get(primary_variant.variant_id, pd.DataFrame())
    primary_rejections = rejected_by_filter_by_variant.get(primary_variant.variant_id, {})
    primary_symbols = _extract_selected_symbols(primary_selected)

    summary_variants: list[dict[str, object]] = []
    artifact_variants: list[dict[str, object]] = []
    for variant in runtime_variants[1:]:
        selected_df = selected_by_variant.get(variant.variant_id, pd.DataFrame())
        rejections = rejected_by_filter_by_variant.get(variant.variant_id, {})
        summary_variants.append(
            _build_variant_payload(
                variant=variant,
                selected_df=selected_df,
                rejected_by_filter=rejections,
                primary_symbols=primary_symbols,
                include_selected_symbols=False,
            )
        )
        artifact_variants.append(
            _build_variant_payload(
                variant=variant,
                selected_df=selected_df,
                rejected_by_filter=rejections,
                primary_symbols=primary_symbols,
                include_selected_symbols=True,
            )
        )

    primary_summary = _build_variant_payload(
        variant=primary_variant,
        selected_df=primary_selected,
        rejected_by_filter=primary_rejections,
        include_selected_symbols=False,
    )
    primary_artifact = _build_variant_payload(
        variant=primary_variant,
        selected_df=primary_selected,
        rejected_by_filter=primary_rejections,
        include_selected_symbols=True,
    )
    summary = {
        "mode": plan.mode,
        "variant_count": len(summary_variants),
        "artifact_path": artifact_path,
        "primary": primary_summary,
        "variants": summary_variants,
    }
    artifact = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "mode": plan.mode,
        "artifact_path": artifact_path,
        "primary": primary_artifact,
        "variants": artifact_variants,
    }
    return summary, artifact


def write_ablation_artifact(
    *,
    plan: SelectorAblationPlan,
    artifact_payload: dict[str, object],
    artifact_stem: str,
) -> str:
    artifact_dir = Path(plan.artifact_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = Path.cwd() / artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{artifact_stem}.json"
    payload_to_write = dict(artifact_payload)
    payload_to_write["artifact_path"] = str(artifact_path)
    artifact_path.write_text(
        json.dumps(payload_to_write, ensure_ascii=False, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return str(artifact_path)


__all__ = [
    "RuntimeSelectorVariant",
    "build_ablation_summary_and_artifact",
    "resolve_runtime_variants",
    "write_ablation_artifact",
]



