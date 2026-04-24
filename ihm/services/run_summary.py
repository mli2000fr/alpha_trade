"""Helpers de normalisation / agrégation / présentation des run_summary IHM."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


RUN_SUMMARY_METRICS: dict[str, list[tuple[str, str]]] = {
    "import_alpaca_bar": [
        ("Cibles", "targeted_symbols"),
        ("Succès", "successful_symbols"),
        ("No data", "no_data_symbols"),
        ("Stale", "stale_symbols"),
        ("Err. provider", "provider_error_symbols"),
        ("Bars insérées", "inserted_bars"),
    ],
    "data_sanitizer_daily": [
        ("Cibles", "targeted_symbols"),
        ("Succès", "successful_symbols"),
        ("Skip", "skipped_symbols"),
        ("Échecs", "failed_symbols"),
        ("Dégradés", "degraded_symbols"),
        ("Rows upsert", "upserted_rows"),
    ],
    "pipeline_workflow": [
        ("Étapes résumées", "workflow_steps_with_summary"),
        ("Cibles", "targeted_symbols"),
        ("Succès", "successful_symbols"),
        ("Échecs", "failed_symbols"),
        ("Skip", "skipped_symbols"),
        ("No data", "no_data_symbols"),
    ],
}

_SUMMARY_METADATA_KEYS = {
    "run_id",
    "started_at",
    "finished_at",
    "timeframe",
    "market_date",
    "workflow_step_summaries",
    "workflow_child_run_ids_with_summary",
    "workflow_timeframes",
    "workflow_market_dates",
}
_CAPTION_EXCLUDED_KEYS = _SUMMARY_METADATA_KEYS | {"history_status_counts", "status_breakdown"}


def get_run_summary(record: Mapping[str, object] | None) -> dict[str, object]:
    if not record:
        return {}
    payload = record.get("run_summary")
    return dict(payload) if isinstance(payload, Mapping) else {}


def _step_key(record: Mapping[str, object] | None) -> str:
    if not record:
        return ""
    return str(record.get("step_key", "") or "")


def get_run_summary_metric_items(record: Mapping[str, object] | None) -> list[tuple[str, object]]:
    summary = get_run_summary(record)
    if not summary:
        return []

    specs = RUN_SUMMARY_METRICS.get(_step_key(record), [])
    if specs:
        items = [(label, summary.get(key)) for label, key in specs if summary.get(key) not in (None, "")]
        if items:
            return items

    generic_items: list[tuple[str, object]] = []
    for key, value in summary.items():
        if key in _CAPTION_EXCLUDED_KEYS:
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        generic_items.append((key, value))
    return generic_items[:6]


def build_run_summary_caption(record: Mapping[str, object] | None) -> str:
    items = get_run_summary_metric_items(record)
    if not items:
        return "—"
    return " | ".join(f"{label.lower()}={value}" for label, value in items)


def find_latest_run_with_summary(
    records: Sequence[Mapping[str, object]],
    *,
    step_keys: Iterable[str] | None = None,
    run_kind: str | None = None,
) -> dict[str, object] | None:
    allowed_step_keys = {str(step_key) for step_key in step_keys or [] if str(step_key).strip()}
    for record in records:
        if run_kind is not None and str(record.get("run_kind", "step")) != run_kind:
            continue
        if allowed_step_keys and str(record.get("step_key", "")) not in allowed_step_keys:
            continue
        if get_run_summary(record):
            return dict(record)
    return None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _merge_nested_counts(target: dict[str, object], key: str, value: Mapping[str, object]) -> None:
    merged = dict(target.get(key, {})) if isinstance(target.get(key), Mapping) else {}
    for nested_key, nested_value in value.items():
        if _is_number(nested_value):
            merged[nested_key] = int(merged.get(nested_key, 0)) + int(nested_value)
    if merged:
        target[key] = merged


def _merge_scalar_metric(target: dict[str, object], key: str, value: int | float) -> None:
    if key.startswith("max_") or key.endswith("_threshold"):
        current = target.get(key)
        target[key] = value if not _is_number(current) else max(float(current), float(value))
        return
    if key == "duration_seconds":
        current = float(target.get("children_duration_seconds", 0.0) or 0.0)
        target["children_duration_seconds"] = round(current + float(value), 2)
        return
    current = target.get(key)
    if _is_number(current):
        total = float(current) + float(value)
        target[key] = int(total) if float(total).is_integer() else round(total, 2)
    else:
        target[key] = int(value) if float(value).is_integer() else round(float(value), 2)


def aggregate_workflow_run_summary(child_runs: Iterable[Mapping[str, object]]) -> dict[str, object]:
    aggregated: dict[str, object] = {}
    step_summaries: list[dict[str, object]] = []
    timeframes: set[str] = set()
    market_dates: set[str] = set()

    for child_run in child_runs:
        summary = get_run_summary(child_run)
        if not summary:
            continue

        step_summary = {
            "run_id": str(child_run.get("run_id", "") or ""),
            "step_key": str(child_run.get("step_key", "") or ""),
            "step_label": str(child_run.get("step_label", child_run.get("step_key", "")) or ""),
            "status": str(child_run.get("status", "") or ""),
            "caption": build_run_summary_caption(child_run),
            "summary": summary,
        }
        step_summaries.append(step_summary)

        timeframe = summary.get("timeframe")
        if timeframe not in (None, ""):
            timeframes.add(str(timeframe))
        market_date = summary.get("market_date")
        if market_date not in (None, ""):
            market_dates.add(str(market_date))

        for key, value in summary.items():
            if key in _SUMMARY_METADATA_KEYS:
                continue
            if isinstance(value, Mapping):
                _merge_nested_counts(aggregated, key, value)
            elif _is_number(value):
                _merge_scalar_metric(aggregated, key, value)

    if not step_summaries:
        return {}

    aggregated["workflow_steps_with_summary"] = len(step_summaries)
    aggregated["workflow_child_run_ids_with_summary"] = [entry["run_id"] for entry in step_summaries if entry["run_id"]]
    aggregated["workflow_step_summaries"] = step_summaries
    if timeframes:
        aggregated["workflow_timeframes"] = sorted(timeframes)
    if market_dates:
        aggregated["workflow_market_dates"] = sorted(market_dates)
    return aggregated
