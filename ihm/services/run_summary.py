"""Helpers de normalisation / agrégation / présentation des run_summary IHM."""
from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from typing import Any, Iterable, Mapping, Sequence

from ihm.services.pipeline_runner import get_pipeline_auxiliary_steps, get_pipeline_steps


RUN_SUMMARY_METRICS: dict[str, list[tuple[str, str]]] = {
    "import_alpaca_assets": [
        ("Assets", "assets_fetched"),
        ("Rows upsert", "rows_upserted"),
    ],
    "import_alpaca_bar": [
        ("Cibles", "targeted_symbols"),
        ("Succès", "successful_symbols"),
        ("No data", "no_data_symbols"),
        ("Stale", "stale_symbols"),
        ("Err. provider", "provider_error_symbols"),
        ("Bars insérées", "inserted_bars"),
    ],
    "update_sector": [
        ("Cibles", "total"),
        ("Mises à jour", "updated"),
        ("Skip", "skipped"),
        ("Échecs", "failed"),
    ],
    "data_sanitizer_daily": [
        ("Cibles", "targeted_symbols"),
        ("Succès", "successful_symbols"),
        ("Skip", "skipped_symbols"),
        ("Échecs", "failed_symbols"),
        ("Dégradés", "degraded_symbols"),
        ("Rows upsert", "upserted_rows"),
    ],
    "stock_screener": [
        ("Cibles", "targeted_symbols"),
        ("Final", "symbols_final"),
        ("Pass hist.", "symbols_pass_history"),
        ("Pass liq.", "symbols_pass_liquidity"),
        ("Pass RS", "symbols_pass_relative_strength"),
        ("Chunks KO", "chunk_failures"),
    ],
    "sync_latest_quotes": [
        ("Symboles", "symbols"),
        ("Rows upsert", "rows_upserted"),
        ("Batch", "batch_size"),
    ],
    "sync_earnings_calendar": [
        ("Symboles", "symbols"),
        ("Rows upsert", "rows_upserted"),
        ("Limite", "requested_limit"),
    ],
    "alpha_scanner": [
        ("Demandé", "requested_selection_size"),
        ("Retenus", "selected_candidates"),
        ("Secteurs", "selected_sectors"),
        ("Fill", "selection_fill_ratio"),
        ("Workers", "workers"),
        ("Cap sec.", "sector_cap_ratio"),
    ],
    "sentiment_pipeline": [
        ("Symboles", "resolved_symbols"),
        ("Fetch", "fetched_articles"),
        ("Landed", "landed_articles"),
        ("Sentiments", "sentiment_inferred"),
        ("Macro", "macro_rows"),
        ("Ticker jours", "ticker_day_rows"),
        ("Secteur jours", "sector_day_rows"),
    ],
    "signal_aggregator": [
        ("Chargés", "loaded_symbols"),
        ("MAJ", "updated_symbols"),
        ("Sent. actifs", "signal_active_symbols"),
        ("News", "total_news"),
        ("Score moy.", "avg_final_score_sentiment"),
        ("Score max.", "max_final_score_sentiment"),
    ],
    "pipeline_workflow": [
        ("Étapes résumées", "workflow_steps_with_summary"),
        ("Cibles", "targeted_symbols"),
        ("Succès", "successful_symbols"),
        ("Échecs", "failed_symbols"),
        ("Skip", "skipped_symbols"),
        ("No data", "no_data_symbols"),
    ],
    "risk_management": [
        ("Cibles", "targeted_symbols"),
        ("Acceptés", "accepted_symbols"),
        ("Réduits", "reduced_symbols"),
        ("Rejetés", "rejected_symbols"),
        ("Expo brute", "gross_exposure_pct"),
        ("Poids max", "max_target_weight"),
        ("Risque init.", "total_initial_risk_dollars"),
        ("Couverture ATR", "atr_coverage_pct"),
        ("Couverture ML", "prediction_coverage_pct"),
    ],
    "execution": [
        ("Cibles", "targeted_symbols"),
        ("Soumis", "submitted_orders"),
        ("Remplis", "filled_orders"),
        ("Échecs", "failed_orders"),
        ("Ignorés", "skipped_orders"),
        ("Taux d'exécution", "fill_rate"),
        ("Notional cible", "total_target_notional"),
        ("Risque init.", "total_initial_risk_dollars"),
        ("Stops broker", "targets_with_broker_initial_stop"),
    ],
    "corporate_actions_sync": [
        ("Cibles", "targeted_symbols"),
        ("Récupérés", "fetched_events"),
        ("Insérés", "inserted_events"),
        ("Doublons", "duplicate_events"),
        ("Invalides", "invalid_events"),
    ],
    "corporate_actions_apply": [
        ("En attente", "pending_events"),
        ("Appliqués", "applied_events"),
        ("Ignorés", "skipped_events"),
        ("Échecs", "failed_events"),
        ("Dividendes", "dividend_credits"),
        ("Splits", "split_applications"),
    ],
    "corporate_actions_run": [
        ("Étapes résumées", "workflow_steps_with_summary"),
        ("Récupérés", "fetched_events"),
        ("Appliqués", "applied_events"),
        ("Échecs", "failed_events"),
        ("Ignorés", "skipped_events"),
        ("Doublons", "duplicate_events"),
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


def build_latest_run_summary_rows(
    records: Sequence[Mapping[str, object]],
    scopes: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for scope in scopes:
        label = str(scope.get("label", "") or "").strip()
        if not label:
            continue
        run_kind_raw = scope.get("run_kind")
        run_kind = str(run_kind_raw).strip() if run_kind_raw not in (None, "") else None
        step_keys_raw = scope.get("step_keys")
        step_keys = step_keys_raw if isinstance(step_keys_raw, SequenceABC) and not isinstance(step_keys_raw, (str, bytes)) else None
        record = find_latest_run_with_summary(records, run_kind=run_kind, step_keys=step_keys)
        if not record:
            continue
        rows.append(
            {
                "scope": label,
                "statut": str(record.get("status", "—") or "—"),
                "run_id": str(record.get("run_id", "—") or "—"),
                "résumé métier": build_run_summary_caption(record),
            }
        )
    return rows


def build_ordered_pipeline_step_scopes(
    *,
    include_auxiliary: bool = True,
    max_main_step: int | None = None,
) -> list[dict[str, object]]:
    scopes: list[dict[str, object]] = []
    if include_auxiliary:
        scopes.extend(
            {"label": f"{step.num}. {step.name}", "step_keys": [step.key]}
            for step in get_pipeline_auxiliary_steps()
        )
    for step in get_pipeline_steps():
        step_number = int(step.num)
        if max_main_step is not None and step_number > max_main_step:
            break
        scopes.append({"label": f"{step.num}. {step.name}", "step_keys": [step.key]})
    return scopes


def build_pipeline_flow_caption(*, include_auxiliary: bool = True, max_main_step: int | None = None) -> str:
    scopes = build_ordered_pipeline_step_scopes(
        include_auxiliary=include_auxiliary,
        max_main_step=max_main_step,
    )
    return " → ".join(str(scope.get("label") or "").strip() for scope in scopes if str(scope.get("label") or "").strip())


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
    if key.endswith("_threshold"):
        target[key] = value
        return
    if key.startswith("max_"):
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


def _metric_rule(key: str, value: object) -> str:
    if isinstance(value, bool):
        return "bool_or"
    if key.endswith("_threshold"):
        return "latest"
    if key.startswith("max_"):
        return "max"
    if key == "duration_seconds":
        return "sum_duration"
    if key.startswith("avg_") or key.endswith("_rate"):
        return "weighted_avg"
    if key.endswith("_pct") and key not in {"profit_taker_pct", "trailing_stop_pct"}:
        return "weighted_avg"
    return "sum"


def _infer_weight_key(summary: Mapping[str, object], key: str) -> str | None:
    candidates_by_key: dict[str, tuple[str, ...]] = {
        "avg_slippage_bps": ("filled_orders", "filled", "successful_symbols"),
        "avg_implementation_shortfall": ("filled_orders", "filled"),
        "fill_rate": ("submitted_orders", "submitted", "targeted_symbols", "targets"),
        "success_rate": ("targeted_symbols", "targets", "pending_events"),
        "failure_rate": ("targeted_symbols", "targets", "pending_events"),
    }
    generic_candidates = (
        "filled_orders",
        "filled",
        "submitted_orders",
        "submitted",
        "successful_symbols",
        "targeted_symbols",
        "targets",
        "pending_events",
        "fetched_events",
    )
    for candidate in (*candidates_by_key.get(key, ()), *generic_candidates):
        if candidate in summary and _is_number(summary[candidate]) and float(summary[candidate]) > 0:
            return candidate
    return None


def aggregate_workflow_run_summary(child_runs: Iterable[Mapping[str, object]]) -> dict[str, object]:
    aggregated: dict[str, object] = {}
    step_summaries: list[dict[str, object]] = []
    timeframes: set[str] = set()
    market_dates: set[str] = set()
    list_unions: dict[str, set[str]] = {}
    weighted_totals: dict[str, float] = {}
    weighted_weights: dict[str, float] = {}
    weighted_counts: dict[str, int] = {}

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
            elif isinstance(value, (list, tuple, set)):
                union_target = list_unions.setdefault(key, set())
                union_target.update(str(item) for item in value if str(item).strip())
            elif isinstance(value, bool):
                aggregated[key] = bool(aggregated.get(key, False) or value)
            elif _is_number(value):
                rule = _metric_rule(key, value)
                if rule == "weighted_avg":
                    weight_key = _infer_weight_key(summary, key)
                    weight_value = summary.get(weight_key) if weight_key else None
                    if _is_number(weight_value) and float(weight_value) > 0:
                        weighted_totals[key] = weighted_totals.get(key, 0.0) + (float(value) * float(weight_value))
                        weighted_weights[key] = weighted_weights.get(key, 0.0) + float(weight_value)
                    else:
                        weighted_totals[key] = weighted_totals.get(key, 0.0) + float(value)
                        weighted_counts[key] = weighted_counts.get(key, 0) + 1
                    continue
                _merge_scalar_metric(aggregated, key, value)
            elif key.endswith("_mode") or key.endswith("_id") or key.endswith("_date"):
                aggregated[key] = value

    for key, total in weighted_totals.items():
        weight = weighted_weights.get(key, 0.0)
        if weight > 0:
            aggregated[key] = round(total / weight, 4)
        else:
            count = max(weighted_counts.get(key, 1), 1)
            aggregated[key] = round(total / count, 4)

    for key, values in list_unions.items():
        if values:
            aggregated[key] = sorted(values)

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
