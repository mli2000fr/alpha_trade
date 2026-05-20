import pandas as pd
import json

from ihm.pages import backtesting


def test_pages_backtesting_importable() -> None:
    assert hasattr(backtesting, "__doc__")


def test_parameter_reference_rows_include_screener_commands() -> None:
    diagnose_rows = backtesting._parameter_reference_rows("diagnose-screener")
    recommend_rows = backtesting._parameter_reference_rows("recommend-screener")

    assert any(row["Paramètre"] == "output_dir" for row in diagnose_rows)
    assert any(row["Paramètre"] == "max_scenarios" for row in diagnose_rows)
    assert any(row["Paramètre"] == "input_dir" for row in recommend_rows)
    assert any(row["Paramètre"] == "target_horizon" for row in recommend_rows)


def test_parameter_reference_rows_include_walk_forward_run_options() -> None:
    run_rows = backtesting._parameter_reference_rows("run")

    assert any(row["Paramètre"] == "score_column" for row in run_rows)
    assert any(row["Paramètre"] == "walk_forward_artifacts_dir" for row in run_rows)
    assert any(row["Paramètre"] == "capital_preset_key" for row in run_rows)
    assert any(row["Paramètre"] == "engine_mode" for row in run_rows)
    assert any(row["Paramètre"] == "ml_pit_strategy" for row in run_rows)
    assert any(row["Paramètre"] == "phase2_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase3_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase4_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase5_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase7_mode" for row in run_rows)
    assert any(row["Paramètre"] == "fidelity_baseline_id" for row in run_rows)
    assert any(row["Paramètre"] == "fidelity_baseline_catalog" for row in run_rows)


def test_run_configuration_preset_pipeline_live_like_exposes_expected_phase_chain() -> None:
    preset = backtesting._get_run_configuration_preset("pipeline_live_like")

    assert preset is not None
    assert preset["label"] == "Replay le plus proche du pipeline live aujourd'hui"
    updates = preset["state_updates"]
    assert updates["bt_run_engine_mode"] == "pipeline"
    assert updates["bt_run_ml_pit_strategy"] == "use-persisted"
    assert updates["bt_run_phase2_mode"] == "risk_execution"
    assert updates["bt_run_phase3_mode"] == "execution_replay"
    assert updates["bt_run_phase4_mode"] == "protection_replay"
    assert updates["bt_run_phase5_mode"] == "watcher_replay"
    assert updates["bt_run_phase7_mode"] == "exit_lifecycle_replay"


def test_build_pipeline_pit_status_message_warns_when_history_is_missing() -> None:
    level, message = backtesting._build_pipeline_pit_status_message(
        {
            "status": "missing",
            "start": "2024-01-01",
            "end": "2024-01-31",
            "capital_preset_key": "capital_50001_100000",
            "capital_preset_filtered": True,
            "rows": 0,
            "snapshot_days": 0,
        }
    )

    assert level == "error"
    assert "stock_scores_history" in message
    assert "Backfill scores history" in message
    assert "capital_50001_100000" in message


def test_build_pipeline_pit_status_message_confirms_when_history_is_available() -> None:
    level, message = backtesting._build_pipeline_pit_status_message(
        {
            "status": "available",
            "start": "2024-01-01",
            "end": "2025-04-29",
            "capital_preset_key": "capital_50001_100000",
            "capital_preset_filtered": True,
            "rows": 42,
            "snapshot_days": 7,
            "first_snapshot_date": "2024-01-01",
            "last_snapshot_date": "2025-04-29",
        }
    )

    assert level == "success"
    assert "42 ligne(s)" in message
    assert "7 séance(s)" in message


def test_parameter_reference_rows_include_backfill_capital_preset_options() -> None:
    backfill_rows = backtesting._parameter_reference_rows("backfill")

    assert any(row["Paramètre"] == "capital" for row in backfill_rows)
    assert any(row["Paramètre"] == "capital_preset_key" for row in backfill_rows)


def test_build_fidelity_component_rows_formats_expected_columns() -> None:
    rows = backtesting._build_fidelity_component_rows(
        {
            "components": ["bars", "scores", "sentiment"],
            "component_status": {
                "bars": {"status": "ok", "enabled": True, "degraded_reasons": []},
                "scores": {
                    "status": "degraded",
                    "enabled": True,
                    "degraded_reasons": ["stock_scores_history_missing"],
                },
                "sentiment": {"status": "disabled", "enabled": False, "degraded_reasons": []},
            },
        }
    )

    assert list(rows.columns) == ["Composant", "État", "Activé", "Motifs"]
    assert rows.iloc[0]["État"] == "🟢 OK"
    assert rows.iloc[1]["Motifs"] == "stock_scores_history_missing"
    assert rows.iloc[2]["Activé"] == "non"


def test_build_fidelity_coverage_rows_exposes_missing_symbols() -> None:
    rows = backtesting._build_fidelity_coverage_rows(
        {
            "coverage": {
                "sentiment": {
                    "rows_input": 10,
                    "coverage_ratio_after": 0.9,
                    "rows_missing_after": 1,
                    "missing_symbols_after": ["AAPL"],
                },
                "ml": {
                    "rows_input": 10,
                    "coverage_ratio_after": 0.8,
                    "rows_missing_after": 2,
                    "missing_symbols_after": ["MSFT", "NVDA"],
                },
            }
        }
    )

    assert list(rows["Couverture"]) == ["sentiment", "ml"]
    assert rows.iloc[0]["Couverture finale"] == "90.0%"
    assert rows.iloc[1]["Symboles dégradants"] == "MSFT, NVDA"


def test_build_fidelity_provenance_rows_exposes_sources_and_tags() -> None:
    rows = backtesting._build_fidelity_provenance_rows(
        {
            "provenance": {
                "scores": {
                    "provenance_kind": "persisted_history",
                    "source_table": "stock_scores_history",
                    "score_column_requested": "auto",
                },
                "sentiment": {
                    "requested_mode": "auto",
                    "source_tags": ["persisted_scores_snapshot", "walk_forward_overlay"],
                    "walk_forward_artifact_path": "artifacts/wf/run_1/latest_best_weights.json",
                },
                "ml": {
                    "effective_strategy": "rebuild-missing",
                    "source_tags": ["persisted_predictions", "rebuilt_predictions"],
                },
            }
        }
    )

    assert list(rows["Composant"]) == ["scores", "sentiment", "ml"]
    assert rows.iloc[0]["Type"] == "persisted_history"
    assert "walk_forward_overlay" in rows.iloc[1]["Source / tags"]
    assert rows.iloc[2]["Détail clé"] == "rebuild-missing"


def test_build_fidelity_ml_cause_rows_exposes_breakdown() -> None:
    rows = backtesting._build_fidelity_ml_cause_rows(
        {
            "provenance": {
                "ml": {
                    "missing_cause_breakdown": {
                        "prediction_missing": 3,
                        "artifact_missing": 1,
                    }
                }
            }
        }
    )

    assert list(rows["Cause ML"]) == ["prediction_missing", "artifact_missing"]
    assert list(rows["Occurrences"]) == [3, 1]


def test_load_json_artifact_from_paths_reads_existing_payload(tmp_path) -> None:
    artifact_path = tmp_path / "replay_diagnostic_summary.json"
    artifact_path.write_text(json.dumps({"session_count": 2}), encoding="utf-8")

    payload = backtesting._load_json_artifact_from_paths(
        {"replay_diagnostic_summary_json": str(artifact_path)},
        "replay_diagnostic_summary_json",
    )

    assert payload == {"session_count": 2}


def test_build_replay_diagnostic_session_rows_formats_expected_columns() -> None:
    rows = backtesting._build_replay_diagnostic_session_rows(
        {
            "sessions": [
                {
                    "trade_date": "2025-01-02",
                    "candidate_rows": 5,
                    "score_source_counts": {"final_score_sentiment": 3, "final_score": 2},
                    "predictions_rows": 4,
                    "missing_sentiment_rows": 1,
                    "missing_ml_symbols": ["MSFT"],
                    "selected_count": 2,
                    "degraded_components": ["ml", "sentiment"],
                    "critical_symbol": {"symbol": "MSFT"},
                    "provenance_refs": {"scores_snapshot_id": "2025-01-02|stock_scores_history|capital_50001_100000|present"},
                    "degraded": True,
                }
            ]
        }
    )

    assert list(rows.columns) == [
        "Séance",
        "Candidats",
        "Sources score",
        "Prédictions",
        "Manquants sentiment",
        "Symboles ML manquants",
        "Sélections",
        "Composants dégradés",
        "Symbole critique",
        "Réf provenance",
        "Dégradée",
    ]
    assert rows.iloc[0]["Séance"] == "2025-01-02"
    assert rows.iloc[0]["Symbole critique"] == "MSFT"
    assert rows.iloc[0]["Dégradée"] == "oui"


def test_build_candidate_target_parity_rows_formats_expected_columns() -> None:
    rows = backtesting._build_candidate_target_parity_rows(
        {
            "sessions": [
                {
                    "trade_date": "2025-01-02",
                    "parity_status": "diverged",
                    "research_selected_count": 2,
                    "risk_target_count": 1,
                    "risk_rejected_count": 1,
                    "research_only_symbols": ["BBB"],
                    "risk_only_symbols": [],
                    "divergence_reasons": ["research_only_candidates", "risk_rejections"],
                }
            ]
        }
    )

    assert list(rows.columns) == [
        "Séance",
        "Statut",
        "Research sélectionnés",
        "Targets risk",
        "Rejets risk",
        "Research only",
        "Risk only",
        "Motifs divergence",
    ]
    assert rows.iloc[0]["Statut"] == "diverged"
    assert rows.iloc[0]["Research only"] == "BBB"


def test_build_compare_to_live_rows_formats_expected_columns() -> None:
    rows = backtesting._build_compare_to_live_rows(
        {
            "sessions": [
                {
                    "trade_date": "2025-01-02",
                    "fidelity_score": 0.625,
                    "candidate_compare": {"status": "diverged"},
                    "risk_compare": {"status": "aligned"},
                    "portfolio_compare": {"status": "missing_live"},
                    "execution_compare": {"status": "diverged"},
                    "fills_compare": {"status": "aligned"},
                    "exits_compare": {"status": "missing_replay"},
                    "pnl_compare": {"status": "aligned"},
                    "top_divergences": [
                        {"component": "candidates", "symbol": "BBB", "divergence_kind": "missing_live_candidate"},
                        {"component": "execution_targets", "symbol": "AAA", "divergence_kind": "qty_mismatch"},
                    ],
                }
            ]
        }
    )

    assert list(rows.columns) == [
        "Séance",
        "Score fidélité",
        "Candidats",
        "Risk live",
        "Targets live",
        "Exécution live",
        "Fills live",
        "Exits live",
        "PnL live",
        "Divergences clés",
    ]
    assert rows.iloc[0]["Séance"] == "2025-01-02"
    assert rows.iloc[0]["Score fidélité"] == "0.625"
    assert rows.iloc[0]["Candidats"] == "diverged"
    assert rows.iloc[0]["Fills live"] == "aligned"
    assert "candidates:BBB:missing_live_candidate" in rows.iloc[0]["Divergences clés"]


def test_build_execution_broker_like_session_rows_formats_expected_columns() -> None:
    rows = backtesting._build_execution_broker_like_session_rows(
        {
            "sessions": [
                {
                    "trade_date": "2025-01-02",
                    "symbols": ["AAA", "BBB"],
                    "selected_signals": 2,
                    "orders_total": 6,
                    "filled_orders": 2,
                    "partial_fill_orders": 1,
                    "retry_orders": 3,
                    "rejected_orders": 1,
                    "timed_out_orders": 1,
                    "working_orders": 2,
                    "held_orders": 1,
                    "canceled_orders": 1,
                    "stale_orders": 0,
                    "exit_filled_orders": 1,
                    "trigger_hits": 1,
                    "partial_fill_events": 1,
                    "retry_events": 3,
                    "cancel_events": 1,
                    "reject_events": 1,
                    "timeout_events": 1,
                    "oco_cancels": 1,
                }
            ]
        }
    )

    assert list(rows.columns) == [
        "Séance",
        "Symboles",
        "Sélections",
        "Ordres",
        "Filled",
        "Partial fills",
        "Retries",
        "Rejected",
        "Timed out",
        "Working",
        "Held",
        "Canceled",
        "Stale",
        "Exit fills",
        "Triggers",
        "Partial fill events",
        "Retry events",
        "Cancel events",
        "Reject events",
        "Timeout events",
        "OCO cancels",
    ]
    assert rows.iloc[0]["Séance"] == "2025-01-02"
    assert rows.iloc[0]["Symboles"] == "AAA, BBB"
    assert rows.iloc[0]["Partial fills"] == 1
    assert rows.iloc[0]["Retries"] == 3
    assert rows.iloc[0]["Rejected"] == 1
    assert rows.iloc[0]["Timed out"] == 1
    assert rows.iloc[0]["Held"] == 1


def test_build_fidelity_baseline_snapshot_rows_formats_expected_columns() -> None:
    rows = backtesting._build_fidelity_baseline_snapshot_rows(
        {
            "metrics": {
                "sentiment_coverage_ratio_after": 1.0,
                "compare_live_fidelity_score": 0.975,
            }
        }
    )

    assert list(rows.columns) == ["Métrique", "Valeur"]
    assert rows.iloc[0]["Métrique"] == "sentiment_coverage_ratio_after"


def test_build_fidelity_baseline_check_rows_formats_expected_columns() -> None:
    rows = backtesting._build_fidelity_baseline_check_rows(
        {
            "checks": [
                {
                    "label": "Score global compare-to-live",
                    "check_type": "metric",
                    "comparison": "min",
                    "baseline_value": 0.98,
                    "current_value": 0.97,
                    "delta": -0.01,
                    "tolerance_abs": 0.02,
                    "status": "passed",
                }
            ]
        }
    )

    assert list(rows.columns) == ["Check", "Type", "Comparaison", "Baseline", "Courant", "Delta", "Tolérance", "Statut"]
    assert rows.iloc[0]["Type"] == "metric"
    assert rows.iloc[0]["Statut"] == "passed"


def test_build_fidelity_baseline_catalog_rows_formats_expected_columns(tmp_path) -> None:
    catalog_path = tmp_path / "fidelity_baseline_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "version": 1,
                "baselines": [
                    {
                        "baseline_id": "pipeline_live_like_2024_full_year",
                        "label": "Pipeline live-like 2024",
                        "requested_window": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
                        "phase_modes": {
                            "phase2_mode": "risk_execution",
                            "phase3_mode": "execution_replay",
                        },
                        "snapshot_path": "../artifacts/fidelity_baselines/pipeline_live_like_2024_full_year/fidelity_baseline_snapshot.json",
                        "promotion_manifest_path": "../artifacts/fidelity_baselines/pipeline_live_like_2024_full_year/promotion_manifest.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rows = backtesting._build_fidelity_baseline_catalog_rows(catalog_path)

    assert list(rows.columns) == ["Baseline", "Libellé", "Fenêtre", "Phases", "Snapshot", "Manifest"]
    assert rows.iloc[0]["Baseline"] == "pipeline_live_like_2024_full_year"
    assert rows.iloc[0]["Fenêtre"] == "2024-01-01 → 2024-12-31"
    assert "phase2_mode=risk_execution" in rows.iloc[0]["Phases"]


def test_build_screener_artifact_objective_rows_formats_expected_columns() -> None:
    rows = backtesting._build_screener_artifact_objective_rows(
        {
            "objective_recommendations": [
                {
                    "objective_label": "robuste",
                    "objective_scope": "cross_regime",
                    "scenario_name": "steady",
                    "objective_score": 0.82,
                    "overall_score": 0.78,
                    "reason": "Stable sur tous les régimes.",
                }
            ]
        }
    )

    assert list(rows.columns) == [
        "Objectif",
        "Périmètre",
        "Scénario recommandé",
        "Score objectif",
        "Score global",
        "Pourquoi",
    ]
    assert rows.iloc[0]["Scénario recommandé"] == "steady"


def test_build_screener_artifact_metric_rows_includes_inventory_counts() -> None:
    metrics = dict(
        backtesting._build_screener_artifact_metric_rows(
            {
                "scenario_count": 12,
                "trading_days": 20,
                "file_count": 7,
                "objective_count": 4,
                "baseline_name": "baseline",
                "summary_rows": 12,
                "daily_rows": 240,
                "market_regimes": ["bull", "bear"],
            }
        )
    )

    assert metrics["Scénarios"] == "12"
    assert metrics["Reco objectifs"] == "4"
    assert metrics["Régimes"] == "2"


def test_build_global_screener_history_dataframe_exposes_transverse_inventory() -> None:
    history_df = backtesting._build_global_screener_history_dataframe(
        [
            {
                "artifacts_dir": "C:/tmp/screener_a",
                "artifacts_dir_label": "artifacts/screener_a",
                "available": True,
                "coverage_label": "2026-04-01 → 2026-04-03 (3 séance(s))",
                "updated_at_label": "2026-04-25 10:02",
                "baseline_name": "baseline",
                "objective_count": 4,
                "scenario_count": 12,
                "file_count": 7,
                "market_regime_count": 2,
                "run_count": 3,
                "last_run_label": "Recommandation screener",
                "last_run_status": "completed",
                "source_tags": ["runs IHM"],
            }
        ]
    )

    assert history_df.iloc[0]["Répertoire"] == "artifacts/screener_a"
    assert history_df.iloc[0]["Disponible"] == "oui"


def test_resolve_history_selected_run_id_returns_selected_run(monkeypatch) -> None:
    history_df = pd.DataFrame(
        [
            {"run_id": "run_a", "libellé": "A"},
            {"run_id": "run_b", "libellé": "B"},
        ]
    )

    monkeypatch.setattr(backtesting, "_selected_dataframe_row_index", lambda table_key: 1)

    assert backtesting._resolve_history_selected_run_id(history_df) == "run_b"


def test_resolve_history_selected_run_id_returns_none_when_selection_is_invalid(monkeypatch) -> None:
    history_df = pd.DataFrame([{"run_id": "run_a"}])

    monkeypatch.setattr(backtesting, "_selected_dataframe_row_index", lambda table_key: 3)

    assert backtesting._resolve_history_selected_run_id(history_df) is None


