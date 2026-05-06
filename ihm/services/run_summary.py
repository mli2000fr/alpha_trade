"""Helpers de normalisation / agrégation / présentation des run_summary IHM."""
from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from typing import Any, Iterable, Mapping, Sequence, cast

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
        ("Repris", "symbols_skipped_resume"),
        ("À rejouer", "symbols_remaining"),
        ("Rows upsert", "rows_upserted"),
        ("Batch", "batch_size"),
        ("KO", "failed_symbols"),
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
    "execution_protection_watch": [
        ("Surveillés", "watched_items"),
        ("Triggers", "triggered_items"),
        ("Transitions", "transitioned_items"),
        ("En attente", "pending_items"),
        ("Déjà terminés", "terminal_items"),
        ("Trailing déjà là", "skipped_existing_trailing"),
        ("Annulations KO", "cancel_failed_items"),
        ("Checks", "trigger_check_count"),
    ],
    "execution_protection_watch_service": [
        ("Itérations", "iterations"),
        ("Cycles actifs", "cycles_with_work"),
        ("Idle", "idle_cycles"),
        ("Heartbeats", "heartbeat_count"),
        ("Transitions", "transitioned_items"),
        ("Échecs conséc.", "consecutive_failures"),
        ("Limite échecs", "max_consecutive_failures"),
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
    "provider",
    "current_symbol",
    "current_symbol_index",
    "current_symbol_total",
    "write_commit_every_symbols",
    "batch_commits",
    "symbols_committed",
    "last_commit_symbol_index",
    "last_commit_reason",
    "pending_rows_stock_bars_daily",
    "pending_rows_stock_bars",
    "workflow_step_summaries",
    "workflow_child_run_ids_with_summary",
    "workflow_timeframes",
    "workflow_market_dates",
    "progress_live",
    "progress_current",
    "progress_total",
    "progress_ratio",
    "progress_label",
    "progress_phase",
    "progress_unit",
    "progress_item",
    "stooq_cross_check_enabled",
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


def get_stooq_cross_check_status(record: Mapping[str, object] | None) -> str | None:
    if _step_key(record) != "import_alpaca_bar" or not record:
        return None

    summary = get_run_summary(record)
    enabled_value = summary.get("stooq_cross_check_enabled")
    if isinstance(enabled_value, bool):
        return "activé" if enabled_value else "désactivé"

    command = record.get("command")
    tokens = [str(token).strip().lower() for token in command] if isinstance(command, SequenceABC) else []
    command_display = str(record.get("command_display") or "").strip().lower()
    searchable = " ".join(tokens + ([command_display] if command_display else []))
    if "import_eodhd_bar" not in searchable:
        return None
    return "désactivé" if "--no-stooq-cross-check" in searchable else "activé"


def get_run_summary_metric_items(record: Mapping[str, object] | None) -> list[tuple[str, object]]:
    summary = get_run_summary(record)
    if not summary:
        return []

    specs = RUN_SUMMARY_METRICS.get(_step_key(record), [])
    if specs:
        items = [(label, summary.get(key)) for label, key in specs if summary.get(key) not in (None, "")]
        stooq_status = get_stooq_cross_check_status(record)
        if _step_key(record) == "import_alpaca_bar" and stooq_status is not None:
            items.append(("Stooq", stooq_status))
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


def get_run_summary_detail_lines(record: Mapping[str, object] | None) -> list[str]:
    summary = get_run_summary(record)
    if not summary:
        return []

    step_key = _step_key(record)
    lines: list[str] = []

    if step_key == "import_alpaca_bar":
        stooq_status = get_stooq_cross_check_status(record)
        if stooq_status is not None:
            lines.append(f"Cross-check Stooq : {stooq_status}.")
            cross_payload = summary.get("cross_check_stooq")
            if isinstance(cross_payload, Mapping):
                failed = bool(cross_payload.get("failed", False))
                skipped = bool(cross_payload.get("skipped", False))
                anomalies = int(cross_payload.get("anomalies_count", 0) or 0)
                if failed:
                    lines.append("Audit Stooq terminé en échec non bloquant (warnings réseau / timeout possibles).")
                elif skipped and stooq_status == "activé":
                    lines.append("Audit Stooq sauté faute de données ingérées exploitables pour le contrôle.")
                elif stooq_status == "activé":
                    lines.append(f"Audit Stooq : {anomalies} anomalie(s) détectée(s).")

    if step_key != "sync_earnings_calendar":
        return lines

    resumed = int(summary.get("symbols_skipped_resume", 0) or 0)
    remaining = int(summary.get("symbols_remaining", 0) or 0)
    lines.append(f"Reprise bookmark : {resumed} symbole(s) déjà traité(s), {remaining} restant(s) à rejouer.")
    bookmark_path = str(summary.get("bookmark_path", "") or "").strip()
    if bookmark_path:
        lines.append(f"Bookmark local : {bookmark_path}")
    return lines


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


def _to_float(value: object) -> float | None:
    if not _is_number(value):
        return None
    return float(cast(int | float, value))


def _merge_nested_counts(target: dict[str, object], key: str, value: Mapping[str, object]) -> None:
    current = target.get(key)
    merged = dict(cast(Mapping[str, object], current)) if isinstance(current, Mapping) else {}
    for nested_key, nested_value in value.items():
        if _is_number(nested_value):
            merged[nested_key] = int(_to_float(merged.get(nested_key, 0)) or 0) + int(cast(int | float, nested_value))
    if merged:
        target[key] = merged


def _merge_scalar_metric(target: dict[str, object], key: str, value: int | float) -> None:
    if key.endswith("_threshold"):
        target[key] = value
        return
    if key.startswith("max_"):
        current_value = _to_float(target.get(key))
        target[key] = value if current_value is None else max(current_value, float(value))
        return
    if key == "duration_seconds":
        current = float(target.get("children_duration_seconds", 0.0) or 0.0)
        target["children_duration_seconds"] = round(current + float(value), 2)
        return
    current_value = _to_float(target.get(key))
    if current_value is not None:
        total = current_value + float(value)
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
        candidate_value = _to_float(summary.get(candidate))
        if candidate_value is not None and candidate_value > 0:
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
                    numeric_value = float(cast(int | float, value))
                    weight_value = _to_float(summary.get(weight_key)) if weight_key else None
                    if weight_value is not None and weight_value > 0:
                        weighted_totals[key] = weighted_totals.get(key, 0.0) + (numeric_value * weight_value)
                        weighted_weights[key] = weighted_weights.get(key, 0.0) + weight_value
                    else:
                        weighted_totals[key] = weighted_totals.get(key, 0.0) + numeric_value
                        weighted_counts[key] = weighted_counts.get(key, 0) + 1
                    continue
                _merge_scalar_metric(aggregated, key, cast(int | float, value))
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
