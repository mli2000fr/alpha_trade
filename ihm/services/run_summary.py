"""Helpers de normalisation / agrégation / présentation des run_summary IHM."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Sequence as SequenceABC
from typing import Any, cast

from ihm.services.pipeline_runner import (
    get_pipeline_auxiliary_steps,
    get_pipeline_steps,
    parse_pipeline_step_number,
)

RUN_SUMMARY_METRICS: dict[str, list[tuple[str, str]]] = {
    "ml_train": [
        ("Cibles", "symbols_total"),
        ("Complétés", "symbols_completed"),
        ("Skips", "symbols_skipped"),
        ("Échecs", "symbols_failed"),
        ("Quarantaine", "symbols_quarantined"),
    ],
    "ml_predict": [
        ("Cibles", "symbols_total"),
        ("Servis", "symbols_completed"),
        ("Skips", "symbols_skipped"),
        ("Drift", "ml_drift_status"),
        ("Issues artefacts", "prediction_artifact_issue_count"),
        ("Fallbacks", "prediction_fallback_count"),
    ],
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
        ("Ticker map", "ticker_maps"),
        ("Sentiments", "sentiment_inferred"),
        ("Contextuel", "contextual_scored"),
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
        ("Ranks selector", "selector_rank_available"),
        ("Couverture selector", "selector_rank_coverage_pct"),
        ("Blackout selector", "selector_earnings_blackout_candidates"),
        ("Expo brute", "gross_exposure_pct"),
        ("Poids max", "max_target_weight"),
        ("Risque init.", "total_initial_risk_dollars"),
        ("Couverture ATR", "atr_coverage_pct"),
        ("Couverture ML", "prediction_coverage_pct"),
        ("Gate ML", "ml_gate_action"),
        ("Drift ML", "ml_gate_drift_status"),
    ],
    "execution": [
        ("Cibles", "targeted_symbols"),
        ("Soumis", "submitted_orders"),
        ("Remplis", "filled_orders"),
        ("Échecs", "failed_orders"),
        ("Ignorés", "skipped_orders"),
        ("Taux d'exécution", "fill_rate"),
        ("Ranks selector", "selector_rank_available"),
        ("Couverture selector", "selector_rank_coverage_pct"),
        ("Blackout selector", "selector_earnings_blackout_targets"),
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

_SCREENER_PERSISTENCE_STATUS_LABELS = {
    "pending": "persistance en attente",
    "replaced_scores_full_run": "snapshot remplacé",
    "preserved_previous_scores_empty_run": "snapshot préservé (run vide)",
    "preserved_previous_scores_partial_run": "snapshot préservé (run partiel)",
}
_SCREENER_DETAIL_SAMPLE_LIMIT = 3


def _get_screener_persistence_status(summary: Mapping[str, object]) -> str:
    return str(summary.get("persistence_status") or "").strip()


def _get_screener_persistence_label(summary: Mapping[str, object]) -> str | None:
    raw_status = _get_screener_persistence_status(summary)
    if not raw_status:
        return None
    return _SCREENER_PERSISTENCE_STATUS_LABELS.get(raw_status, raw_status)


def _get_screener_chunk_error_samples(summary: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw_samples = summary.get("chunk_error_samples")
    if not isinstance(raw_samples, list):
        return []
    return [sample for sample in raw_samples if isinstance(sample, Mapping)]


def _format_alpha_scanner_candidate_detail_line(candidate: Mapping[str, object]) -> str | None:
    explainability = candidate.get("candidate_explainability_payload")
    payload = dict(cast(Mapping[str, object], explainability)) if isinstance(explainability, Mapping) else {}
    identity = payload.get("identity") if isinstance(payload.get("identity"), Mapping) else {}
    selection = payload.get("selection_context") if isinstance(payload.get("selection_context"), Mapping) else {}
    components = payload.get("score_components") if isinstance(payload.get("score_components"), Mapping) else {}
    outputs = payload.get("score_outputs") if isinstance(payload.get("score_outputs"), Mapping) else {}

    rank = _to_int(identity.get("rank") or candidate.get("rank"))
    symbol = str(identity.get("symbol") or candidate.get("symbol") or "").strip()
    if not symbol:
        return None
    mode = str(selection.get("selector_signal_mode") or candidate.get("selector_signal_mode") or "").strip()
    final_score = _to_float(outputs.get("final_score") or candidate.get("final_score"))
    trend_component = _to_float(components.get("trend_vcp_component") or candidate.get("trend_vcp_component"))
    total_component = _to_float(components.get("total_score_component") or candidate.get("total_score_component"))
    rsi_component = _to_float(components.get("rsi_component") or candidate.get("rsi_component"))
    explanation = str(selection.get("selection_explanation") or candidate.get("selection_explanation") or "").strip()

    parts = [f"Top #{rank or '—'} {symbol}"]
    if mode:
        parts.append(f"mode={mode}")
    if final_score is not None:
        parts.append(f"final={final_score:.4f}")
    if trend_component is not None:
        parts.append(f"trend/VCP={trend_component:.4f}")
    if total_component is not None:
        parts.append(f"total={total_component:.4f}")
    if rsi_component is not None:
        parts.append(f"RSI={rsi_component:.4f}")
    line = " — ".join(parts) + "."
    if explanation:
        line += f" Explication : {explanation}."
    return line


def _format_alpha_scanner_preselection_detail_line(summary: Mapping[str, object]) -> str | None:
    payload = summary.get("preselection_rejections")
    if not isinstance(payload, Mapping):
        return None
    status = str(payload.get("status") or "").strip().lower()
    if status == "unavailable":
        reason = str(payload.get("reason") or "unknown").strip()
        return f"Préselection SQL : audit indisponible ({reason})."

    input_symbols = _to_int(payload.get("input_symbols"))
    eligible_symbols = _to_int(payload.get("eligible_symbols"))
    rejected_symbols = _to_int(payload.get("rejected_symbols"))
    eligible_ratio = _to_float(payload.get("eligible_ratio"))
    parts = [f"Préselection SQL : éligibles={eligible_symbols}/{input_symbols}"]
    if eligible_ratio is not None:
        parts.append(f"ratio={eligible_ratio * 100.0:.2f}%")
    if rejected_symbols > 0:
        parts.append(f"rejets={rejected_symbols}")

    top_reasons = payload.get("top_reasons")
    top_reason_parts: list[str] = []
    if isinstance(top_reasons, list):
        for item in top_reasons[:3]:
            if not isinstance(item, Mapping):
                continue
            label = str(item.get("label") or item.get("reason") or "").strip()
            count = _to_int(item.get("count"))
            sample_symbols_raw = item.get("sample_symbols")
            sample_symbols = (
                ", ".join(str(symbol) for symbol in sample_symbols_raw if str(symbol).strip())
                if isinstance(sample_symbols_raw, SequenceABC) and not isinstance(sample_symbols_raw, (str, bytes))
                else ""
            )
            if not label or count <= 0:
                continue
            suffix = f" [{sample_symbols}]" if sample_symbols else ""
            top_reason_parts.append(f"{label}={count}{suffix}")
    line = " — ".join(parts) + "."
    if top_reason_parts:
        line += f" Principaux rejets : {'; '.join(top_reason_parts)}."
    return line


def _format_alpha_scanner_ablation_detail_lines(summary: Mapping[str, object]) -> list[str]:
    payload = summary.get("ablation")
    if not isinstance(payload, Mapping):
        return []
    mode = str(payload.get("mode") or "").strip()
    variants = payload.get("variants")
    if mode != "shadow" or not isinstance(variants, list) or not variants:
        return []
    artifact_path = str(payload.get("artifact_path") or "").strip()
    lines = [f"Ablation selector : {len(variants)} variante(s) shadow comparées au primaire."]
    if artifact_path:
        lines.append(f"Artefact ablation : {artifact_path}")
    for variant in variants[:3]:
        if not isinstance(variant, Mapping):
            continue
        variant_id = str(variant.get("variant_id") or "").strip()
        selected_candidates = _to_int(variant.get("selected_candidates"))
        disabled_filters_raw = variant.get("disabled_filters")
        disabled_filters = (
            [str(value).strip() for value in disabled_filters_raw if str(value).strip()]
            if isinstance(disabled_filters_raw, SequenceABC) and not isinstance(disabled_filters_raw, (str, bytes))
            else []
        )
        overlap = variant.get("overlap_with_primary") if isinstance(variant.get("overlap_with_primary"), Mapping) else {}
        overlap_count = _to_int(overlap.get("count"))
        overlap_ratio = _to_float(overlap.get("ratio_vs_primary"))
        selection_diff = variant.get("selection_diff") if isinstance(variant.get("selection_diff"), Mapping) else {}
        added_symbols = selection_diff.get("added_symbols")
        removed_symbols = selection_diff.get("removed_symbols")
        added_text = (
            ", ".join(str(symbol) for symbol in added_symbols if str(symbol).strip())
            if isinstance(added_symbols, SequenceABC) and not isinstance(added_symbols, (str, bytes))
            else ""
        )
        removed_text = (
            ", ".join(str(symbol) for symbol in removed_symbols if str(symbol).strip())
            if isinstance(removed_symbols, SequenceABC) and not isinstance(removed_symbols, (str, bytes))
            else ""
        )
        line = f"Variante `{variant_id}` : retenus={selected_candidates}"
        if disabled_filters:
            line += f", filtres désactivés={', '.join(disabled_filters)}"
        if overlap_count > 0:
            if overlap_ratio is not None:
                line += f", overlap primaire={overlap_count} ({overlap_ratio * 100.0:.2f}%)"
            else:
                line += f", overlap primaire={overlap_count}"
        if added_text:
            line += f", ajouts={added_text}"
        if removed_text:
            line += f", retraits={removed_text}"
        lines.append(line + ".")
    return lines


def _format_selector_mode_counts_line(label: str, payload: object) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    parts: list[str] = []
    for mode, value in payload.items():
        mode_label = str(mode or "unknown").strip() or "unknown"
        count = _to_int(value)
        if count <= 0:
            continue
        parts.append(f"{mode_label}={count}")
    if not parts:
        return None
    return f"{label} : {', '.join(parts)}."


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
        if _step_key(record) == "stock_screener":
            failure_ratio = _to_float(summary.get("chunk_failure_ratio"))
            if failure_ratio is not None and failure_ratio > 0:
                items.append(("Ratio KO", f"{failure_ratio * 100.0:.2f}%"))
            persistence_label = _get_screener_persistence_label(summary)
            if persistence_label:
                items.append(("Persistance", persistence_label))
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

    if bool(summary.get("progress_live")):
        progress_label = str(summary.get("progress_label") or "Progression en cours").strip()
        progress_current = _to_int(summary.get("progress_current"))
        progress_total = _to_int(summary.get("progress_total"))
        progress_unit = str(summary.get("progress_unit") or "éléments").strip()
        progress_item = str(summary.get("progress_item") or "").strip()
        progress_line = f"{progress_label} : {progress_current}/{progress_total} {progress_unit}."
        if progress_item:
            progress_line = f"{progress_line[:-1]} — {progress_item}."
        lines.append(progress_line)

    if str(summary.get("progress_phase") or "").strip() == "contextual_scoring":
        batch_index = _to_int(summary.get("contextual_current_batch"))
        batch_total = _to_int(summary.get("contextual_estimated_batches"))
        batch_size = _to_int(summary.get("contextual_last_batch_size"))
        remaining_pairs = _to_int(summary.get("contextual_pairs_remaining"))
        if batch_index > 0:
            batch_label = (
                f"Lot contextuel {batch_index}/{batch_total}"
                if batch_total > 0
                else f"Lot contextuel {batch_index}"
            )
            lines.append(
                f"{batch_label} — taille du dernier lot : {batch_size} paire(s), reste : {remaining_pairs}."
            )

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

    if step_key == "risk_management":
        gate_enabled = summary.get("ml_gate_enabled")
        gate_reason = str(summary.get("ml_gate_reason") or "unknown").strip()
        gate_action = str(summary.get("ml_gate_action") or "allow").strip()
        drift_status = str(summary.get("ml_gate_drift_status") or "n/a").strip()
        coverage = _to_float(summary.get("prediction_coverage_pct"))
        equity_source = str(summary.get("equity_source") or "").strip()
        equity_fallback_used = bool(summary.get("equity_fallback_used"))
        snapshot_freshness_days = _to_int(summary.get("snapshot_freshness_days"))
        selector_rank_available = _to_int(summary.get("selector_rank_available"))
        selector_rank_coverage_pct = _to_float(summary.get("selector_rank_coverage_pct"))
        selector_blackout = _to_int(summary.get("selector_earnings_blackout_candidates"))
        preflight_payload = summary.get("preflight_data_quality") if isinstance(summary.get("preflight_data_quality"), Mapping) else {}
        rejection_reason_code_counts = summary.get("rejection_reason_code_counts")
        reduction_reason_code_counts = summary.get("reduction_reason_code_counts")
        empirical_calibration_payload = summary.get("empirical_risk_calibration") if isinstance(summary.get("empirical_risk_calibration"), Mapping) else {}
        shadow_compare_payload = summary.get("shadow_compare") if isinstance(summary.get("shadow_compare"), Mapping) else {}
        postmortem_payload = summary.get("postmortem_artifacts") if isinstance(summary.get("postmortem_artifacts"), Mapping) else {}
        if gate_enabled is False:
            lines.append(
                f"Gate ML désactivé : action={gate_action}, drift={drift_status}, raison={gate_reason}."
            )
            if coverage == 0.0:
                lines.append(
                    "Couverture ML nulle attendue : `risk_management` a volontairement ignoré `model_predictions`."
                )
        elif drift_status not in {"", "n/a", "N/A", "OK"}:
            lines.append(
                f"Gate ML actif avec drift={drift_status} (action={gate_action}, raison={gate_reason})."
            )
        if equity_source:
            equity_line = f"Equity source : {equity_source}"
            if equity_fallback_used:
                equity_line += " (fallback actif)"
            elif snapshot_freshness_days is not None and snapshot_freshness_days > 0:
                equity_line += f" (fraîcheur=J-{snapshot_freshness_days})"
            lines.append(equity_line + ".")
        if preflight_payload:
            preflight_status = str(preflight_payload.get("status") or "ok").strip()
            warnings_payload = preflight_payload.get("warnings")
            warning_text = (
                "; ".join(str(item).strip() for item in warnings_payload if str(item).strip())
                if isinstance(warnings_payload, SequenceABC) and not isinstance(warnings_payload, (str, bytes))
                else ""
            )
            line = f"Préflight data-quality risk : status={preflight_status}"
            if warning_text:
                line += f" — {warning_text}"
            lines.append(line + ".")
        if selector_rank_available > 0:
            selector_line = f"Selector : rang disponible pour {selector_rank_available} symbole(s)"
            if selector_rank_coverage_pct is not None:
                selector_line += f" (couverture={selector_rank_coverage_pct:.2f})"
            selector_line += "."
            lines.append(selector_line)
        if selector_blackout > 0:
            lines.append(f"Selector : {selector_blackout} candidat(s) tagué(s) earnings blackout.")
        selector_modes_line = _format_selector_mode_counts_line(
            "Selector modes candidats",
            summary.get("selector_signal_mode_counts"),
        )
        if selector_modes_line:
            lines.append(selector_modes_line)
        retained_selector_modes_line = _format_selector_mode_counts_line(
            "Selector modes retenus",
            summary.get("retained_selector_signal_mode_counts"),
        )
        if retained_selector_modes_line:
            lines.append(retained_selector_modes_line)
        rejection_codes_line = _format_selector_mode_counts_line(
            "Motifs structurés de rejet",
            rejection_reason_code_counts,
        )
        if rejection_codes_line:
            lines.append(rejection_codes_line)
        reduction_codes_line = _format_selector_mode_counts_line(
            "Motifs structurés de réduction",
            reduction_reason_code_counts,
        )
        if reduction_codes_line:
            lines.append(reduction_codes_line)
        if empirical_calibration_payload:
            calibration_run_id = str(empirical_calibration_payload.get("run_id") or "—").strip()
            metric_name = str(empirical_calibration_payload.get("metric_name") or "unknown").strip()
            metric_value = _to_float(empirical_calibration_payload.get("metric_value"))
            resolved_regime_mode = str(empirical_calibration_payload.get("market_regime_mode") or "all").strip()
            requested_regime_mode = str(
                empirical_calibration_payload.get("requested_market_regime_mode") or resolved_regime_mode or "all"
            ).strip()
            fallback_used = bool(empirical_calibration_payload.get("market_regime_fallback_used"))
            best_weights = empirical_calibration_payload.get("best_weights")
            line = f"Calibration empirique risk appliquée : run={calibration_run_id}, métrique={metric_name}"
            if metric_value is not None:
                line += f", valeur={metric_value:.4f}"
            if requested_regime_mode:
                if fallback_used and resolved_regime_mode:
                    line += f", régime={requested_regime_mode}→{resolved_regime_mode}"
                elif resolved_regime_mode:
                    line += f", régime={resolved_regime_mode}"
            if isinstance(best_weights, Mapping):
                score_weight = _to_float(best_weights.get("score_weight"))
                prediction_weight = _to_float(best_weights.get("prediction_weight"))
                kelly_fraction_multiplier = _to_float(best_weights.get("kelly_fraction_multiplier"))
                if score_weight is not None and prediction_weight is not None:
                    line += f", conviction={score_weight:.2f}/{prediction_weight:.2f}"
                if kelly_fraction_multiplier is not None:
                    line += f", kelly_mult={kelly_fraction_multiplier:.2f}"
            lines.append(line + ".")
        if shadow_compare_payload:
            shadow_status = str(shadow_compare_payload.get("status") or "").strip()
            if shadow_status == "compared":
                reference_run_id = str(shadow_compare_payload.get("reference_run_id") or "—").strip()
                qty_drift = _to_float(shadow_compare_payload.get("avg_qty_drift_pct"))
                price_drift = _to_float(shadow_compare_payload.get("avg_price_drift_pct"))
                conviction_drift = _to_float(shadow_compare_payload.get("avg_conviction_drift"))
                line = f"Shadow compare risk : référence={reference_run_id}"
                if qty_drift is not None:
                    line += f", qty={qty_drift:.4f}"
                if price_drift is not None:
                    line += f", prix={price_drift:.4f}"
                if conviction_drift is not None:
                    line += f", conviction={conviction_drift:.4f}"
                lines.append(line + ".")
            elif shadow_status == "missing_reference":
                lines.append("Shadow compare risk : aucun run de référence disponible.")
            elif shadow_status == "unavailable":
                lines.append(
                    f"Shadow compare risk indisponible : {str(shadow_compare_payload.get('error') or 'erreur inconnue').strip()}."
                )
        if postmortem_payload:
            top_rejections = postmortem_payload.get("top_rejection_reason_codes")
            if isinstance(top_rejections, SequenceABC) and not isinstance(top_rejections, (str, bytes)):
                formatted_rejections: list[str] = []
                for item in top_rejections[:3]:
                    if not isinstance(item, Mapping):
                        continue
                    code = str(item.get("code") or "").strip()
                    count = _to_int(item.get("count"))
                    if code and count > 0:
                        formatted_rejections.append(f"{code}={count}")
                if formatted_rejections:
                    lines.append("Post-mortem risk — top rejets : " + ", ".join(formatted_rejections) + ".")
            sector_breakdown = postmortem_payload.get("sector_breakdown")
            if isinstance(sector_breakdown, SequenceABC) and not isinstance(sector_breakdown, (str, bytes)):
                sector_parts: list[str] = []
                for item in sector_breakdown[:3]:
                    if not isinstance(item, Mapping):
                        continue
                    sector = str(item.get("sector") or "UNKNOWN").strip() or "UNKNOWN"
                    retained = _to_int(item.get("retained"))
                    target_weight = _to_float(item.get("target_weight"))
                    piece = f"{sector}: retenus={retained}"
                    if target_weight is not None:
                        piece += f", poids={target_weight:.2%}"
                    sector_parts.append(piece)
                if sector_parts:
                    lines.append("Post-mortem risk — secteurs : " + " | ".join(sector_parts) + ".")

    if step_key == "ml_train":
        training_start_date = str(summary.get("training_start_date") or "").strip()
        feature_fp = str(summary.get("feature_fingerprint") or "").strip()
        quarantined = _to_int(summary.get("symbols_quarantined", 0))
        if training_start_date:
            lines.append(f"Fenêtre training bornée depuis {training_start_date}.")
        if feature_fp:
            lines.append(f"Feature fingerprint actif : {feature_fp}.")
        if quarantined > 0:
            lines.append(f"{quarantined} symbole(s) restent sous quarantaine champion.")

    if step_key == "ml_predict":
        drift_status = str(summary.get("ml_drift_status") or "n/a").strip()
        kill_switch_active = bool(summary.get("ml_kill_switch_active"))
        kill_reason = str(summary.get("ml_kill_switch_reason") or "").strip()
        artifact_issues = _to_int(summary.get("prediction_artifact_issue_count", 0))
        fallback_count = _to_int(summary.get("prediction_fallback_count", 0))
        calibration_fallback_count = _to_int(summary.get("prediction_calibration_fallback_count", 0))
        last_fallback_reason = str(summary.get("last_fallback_reason") or "").strip()
        last_requested_model = str(summary.get("last_requested_model") or "").strip()
        last_served_model = str(summary.get("last_served_model") or "").strip()
        last_artifact_issue_reason = str(summary.get("last_artifact_issue_reason") or "").strip()
        last_artifact_issue_path = str(summary.get("last_artifact_issue_path") or "").strip()
        resolved_device_name = str(summary.get("resolved_device_name") or "").strip()
        if kill_switch_active:
            lines.append(
                f"Drift ML : kill-switch actif (drift={drift_status}, raison={kill_reason or 'unknown'})."
            )
        elif drift_status not in {"", "n/a", "N/A", "OK"}:
            lines.append(f"Drift ML observé côté prédiction : {drift_status}.")
        if fallback_count > 0:
            lines.append(f"Serving dégradé : {fallback_count} fallback(s) architecture sur ce run.")
            if last_fallback_reason:
                lines.append(
                    f"Dernier fallback : demandé `{last_requested_model or '—'}` → servi `{last_served_model or '—'}` ({last_fallback_reason})."
                )
        if artifact_issues > 0:
            issue_line = f"{artifact_issues} incident(s) artefact détecté(s) pendant le serving."
            if last_artifact_issue_reason:
                issue_line += f" Dernier incident : {last_artifact_issue_reason}."
            lines.append(issue_line)
            if last_artifact_issue_path:
                lines.append(f"Dernier chemin artefact en défaut : {last_artifact_issue_path}")
        if calibration_fallback_count > 0:
            lines.append(
                f"{calibration_fallback_count} fallback(s) de calibrateur : serving poursuivi sans calibration quand nécessaire."
            )
        if resolved_device_name:
            lines.append(f"Device d'inférence résolu : {resolved_device_name}.")

    if step_key == "stock_screener":
        persistence_status = _get_screener_persistence_status(summary)
        persistence_label = _get_screener_persistence_label(summary)
        chunk_failures = _to_int(summary.get("chunk_failures", 0))
        chunks_total = _to_int(summary.get("chunks_total", 0))
        chunk_failure_ratio = _to_float(summary.get("chunk_failure_ratio")) or 0.0
        chunk_error_samples = _get_screener_chunk_error_samples(summary)
        sample_count = len(chunk_error_samples)

        if persistence_status == "replaced_scores_full_run":
            persisted_rows = _to_int(summary.get("persisted_rows", 0))
            lines.append(
                "Persistance screener : snapshot `stock_scores` remplacé et archivé "
                f"(`persistence_status={persistence_status}`, lignes persistées={persisted_rows})."
            )
        elif persistence_status == "preserved_previous_scores_partial_run":
            lines.append(
                "Persistance screener : snapshot précédent conservé car le run est partiel "
                f"(`persistence_status={persistence_status}`, pas de purge sur `stock_scores`)."
            )
        elif persistence_status == "preserved_previous_scores_empty_run":
            lines.append(
                "Persistance screener : snapshot précédent conservé car le run est vide "
                f"(`persistence_status={persistence_status}`, pas de purge sur `stock_scores`)."
            )
        elif persistence_label:
            lines.append(
                f"Persistance screener : {persistence_label} (`persistence_status={persistence_status}`)."
            )

        if chunk_failures > 0:
            lines.append(
                "Chunks screener en échec : "
                f"{chunk_failures}/{chunks_total} ({chunk_failure_ratio * 100.0:.2f}%)."
            )
            if sample_count > 0:
                lines.append(
                    "Échantillons d'erreur conservés dans `chunk_error_samples` : "
                    f"{sample_count}."
                )
                for index, sample in enumerate(chunk_error_samples[:_SCREENER_DETAIL_SAMPLE_LIMIT], start=1):
                    input_symbols = _to_int(sample.get("input_symbols", 0))
                    error_message = str(sample.get("error_message") or "inconnue").strip()
                    sample_symbols_raw = sample.get("sample_symbols")
                    if isinstance(sample_symbols_raw, SequenceABC) and not isinstance(sample_symbols_raw, (str, bytes)):
                        sample_symbols = ", ".join(str(symbol) for symbol in sample_symbols_raw if str(symbol).strip())
                    else:
                        sample_symbols = ""
                    sample_suffix = f" — symboles={sample_symbols}" if sample_symbols else ""
                    lines.append(
                        f"Chunk KO {index}/{sample_count} — input={input_symbols}{sample_suffix} — erreur={error_message}."
                    )
                if sample_count > _SCREENER_DETAIL_SAMPLE_LIMIT:
                    remaining_samples = sample_count - _SCREENER_DETAIL_SAMPLE_LIMIT
                    lines.append(
                        f"{remaining_samples} autre(s) échantillon(s) restent disponibles dans le payload brut."
                    )

    if step_key == "alpha_scanner":
        data_quality_gate = summary.get("data_quality_gate")
        if isinstance(data_quality_gate, Mapping):
            skipped_filters = data_quality_gate.get("skipped_filters")
            if isinstance(skipped_filters, SequenceABC) and not isinstance(skipped_filters, (str, bytes)):
                skipped_labels = [str(value).strip() for value in skipped_filters if str(value).strip()]
                if skipped_labels:
                    lines.append(
                        "Fallback data-quality appliqué : filtres sautés = "
                        + ", ".join(skipped_labels)
                        + "."
                    )
        preselection_line = _format_alpha_scanner_preselection_detail_line(summary)
        if preselection_line:
            lines.append(preselection_line)
        lines.extend(_format_alpha_scanner_ablation_detail_lines(summary))
        top_candidates = summary.get("top_candidate_explanations")
        if isinstance(top_candidates, list):
            for candidate in top_candidates[:3]:
                if not isinstance(candidate, Mapping):
                    continue
                detail_line = _format_alpha_scanner_candidate_detail_line(candidate)
                if detail_line:
                    lines.append(detail_line)

    if step_key == "execution":
        selector_rank_available = _to_int(summary.get("selector_rank_available"))
        selector_rank_coverage_pct = _to_float(summary.get("selector_rank_coverage_pct"))
        selector_blackout = _to_int(summary.get("selector_earnings_blackout_targets"))
        if selector_rank_available > 0:
            selector_line = f"Selector transporté jusqu'à l'exécution pour {selector_rank_available} cible(s)"
            if selector_rank_coverage_pct is not None:
                selector_line += f" (couverture={selector_rank_coverage_pct:.2f})"
            selector_line += "."
            lines.append(selector_line)
        if selector_blackout > 0:
            lines.append(f"Execution : {selector_blackout} cible(s) marquée(s) earnings blackout côté selector.")
        selector_modes_line = _format_selector_mode_counts_line(
            "Selector modes exécutés",
            summary.get("selector_signal_mode_counts"),
        )
        if selector_modes_line:
            lines.append(selector_modes_line)

    if step_key != "sync_earnings_calendar":
        return lines

    resumed = _to_int(summary.get("symbols_skipped_resume", 0))
    remaining = _to_int(summary.get("symbols_remaining", 0))
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
        step_number = parse_pipeline_step_number(step.num)
        if step_number is None:
            continue
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


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return int(value)
    return 0


def _coerce_float(value: object) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float, str)):
        return float(value)
    return 0.0


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
        normalized_value = float(value)
        target[key] = normalized_value if current_value is None else max(current_value, normalized_value)
        return
    if key == "duration_seconds":
        current = _coerce_float(target.get("children_duration_seconds", 0.0))
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
