import pandas as pd
import json

from ihm.pages import backtesting


def test_pages_backtesting_importable() -> None:
    assert hasattr(backtesting, "__doc__")


def test_build_daily_portfolio_snapshot_df_reconstructs_positions_from_trades_and_equity_curve() -> None:
    equity_curve_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]),
            "portfolio_value": [10_000.0, 10_150.0, 10_080.0, 10_220.0],
        }
    )
    trades_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "execution_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "exit_date": pd.to_datetime(["2025-01-07", None]),
            "quantity": [10.0, 5.0],
            "entry_price": [150.0, 400.0],
        }
    )

    snapshot_df = backtesting._build_daily_portfolio_snapshot_df(equity_curve_df, trades_df)

    assert snapshot_df["trade_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2025-01-02",
        "2025-01-03",
        "2025-01-06",
        "2025-01-07",
    ]
    assert snapshot_df["portfolio_value"].tolist() == [10_000.0, 10_150.0, 10_080.0, 10_220.0]
    assert snapshot_df["open_positions"].tolist() == [1, 2, 2, 1]
    assert snapshot_df["held_symbols"].tolist() == [
        "AAPL",
        "AAPL, MSFT",
        "AAPL, MSFT",
        "MSFT",
    ]
    assert snapshot_df["positions_detail"].tolist() == [
        "AAPL (10 | $1,500.00)",
        "AAPL (10 | $1,500.00), MSFT (5 | $2,000.00)",
        "AAPL (10 | $1,500.00), MSFT (5 | $2,000.00)",
        "MSFT (5 | $2,000.00)",
    ]


def test_build_daily_portfolio_snapshot_df_excludes_same_day_round_trip_from_end_of_day_holdings() -> None:
    equity_curve_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "portfolio_value": [10_000.0, 10_010.0],
        }
    )
    trades_df = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "entry_date": pd.to_datetime(["2025-01-02"]),
            "exit_date": pd.to_datetime(["2025-01-02"]),
            "quantity": [10.0],
        }
    )

    snapshot_df = backtesting._build_daily_portfolio_snapshot_df(equity_curve_df, trades_df)

    assert snapshot_df["open_positions"].tolist() == [0, 0]
    assert snapshot_df["held_symbols"].tolist() == ["—", "—"]
    assert snapshot_df["positions_detail"].tolist() == ["—", "—"]


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
    assert any(row["Paramètre"] == "scores_pit_mode" for row in run_rows)
    assert any(row["Paramètre"] == "macro_pit_mode" for row in run_rows)
    assert any(row["Paramètre"] == "ml_pit_strategy" for row in run_rows)
    assert any(row["Paramètre"] == "phase2_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase3_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase4_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase5_mode" for row in run_rows)
    assert any(row["Paramètre"] == "phase7_mode" for row in run_rows)
    assert any(row["Paramètre"] == "allow_fractional_shares" for row in run_rows)
    assert any(row["Paramètre"] == "allow_neutral_fallback_on_missing_macro_data" for row in run_rows)
    assert any(row["Paramètre"] == "fidelity_baseline_id" for row in run_rows)
    assert any(row["Paramètre"] == "fidelity_baseline_catalog" for row in run_rows)


def test_build_daily_portfolio_snapshot_df_falls_back_to_quantity_only_when_entry_notional_is_missing() -> None:
    equity_curve_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-02"]),
            "portfolio_value": [10_000.0],
        }
    )
    trades_df = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "quantity": [10.0],
        }
    )

    snapshot_df = backtesting._build_daily_portfolio_snapshot_df(equity_curve_df, trades_df)

    assert snapshot_df["positions_detail"].tolist() == ["AAPL (10)"]


def test_build_daily_portfolio_snapshot_df_merges_market_regime_by_trade_date() -> None:
    equity_curve_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "portfolio_value": [10_000.0, 10_150.0],
        }
    )
    trades_df = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "quantity": [10.0],
        }
    )
    market_regimes_df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "market_regime": ["normal", "capital_preservation"],
        }
    )

    snapshot_df = backtesting._build_daily_portfolio_snapshot_df(
        equity_curve_df,
        trades_df,
        market_regimes_df,
    )

    assert snapshot_df["market_regime"].tolist() == ["normal", "capital_preservation"]


def test_load_run_artifacts_supports_cli_style_root_output_dir(tmp_path) -> None:
    run_dir = tmp_path / "manual_cli_run"
    run_dir.mkdir()
    (run_dir / "stdout.log").write_text("", encoding="utf-8")
    (run_dir / "report.json").write_text(json.dumps({"summary": {"final_value": 101234.5}}), encoding="utf-8")
    (run_dir / "equity_curve.csv").write_text(
        "trade_date,portfolio_value\n2025-01-02,100000\n2025-01-03,101000\n",
        encoding="utf-8",
    )
    (run_dir / "trades.csv").write_text(
        "symbol,execution_date,quantity\nAAPL,2025-01-02,10\n",
        encoding="utf-8",
    )
    (run_dir / "market_regimes.csv").write_text(
        "trade_date,market_regime\n2025-01-02,normal\n2025-01-03,capital_preservation\n",
        encoding="utf-8",
    )
    run_record = {"stdout_path": str(run_dir / "stdout.log")}

    report_payload = backtesting._load_run_report(run_record)
    equity_curve_df = backtesting._load_equity_curve_df(run_record)
    trades_df = backtesting._load_run_trades_df(run_record)
    market_regimes_df = backtesting._load_market_regimes_df(run_record)

    assert report_payload is not None
    assert report_payload["summary"]["final_value"] == 101234.5
    assert equity_curve_df["portfolio_value"].tolist() == [100000, 101000]
    assert trades_df["symbol"].tolist() == ["AAPL"]
    assert market_regimes_df["market_regime"].tolist() == ["normal", "capital_preservation"]


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


def test_run_configuration_preset_auto_applied_once_on_first_page_load() -> None:
    """L'auto-application du preset de configuration à l'arrivée sur la page
    pose les valeurs AVANT l'instanciation des widgets (une seule fois par
    session), puis préserve les ajustements manuels de l'utilisateur."""
    from streamlit.testing.v1 import AppTest

    code = """\
import streamlit as st
from ihm.pages.backtesting import (
    _ensure_run_configuration_preset_session_key,
    _apply_run_configuration_preset,
    BT_RUN_CONFIGURATION_PRESET_APPLIED_KEY,
    BT_RUN_CONFIGURATION_PRESET_KEY,
)
_ensure_run_configuration_preset_session_key()
if not st.session_state.get(BT_RUN_CONFIGURATION_PRESET_APPLIED_KEY):
    _apply_run_configuration_preset(
        str(st.session_state.get(BT_RUN_CONFIGURATION_PRESET_KEY, "pipeline_live_like"))
    )
    st.session_state[BT_RUN_CONFIGURATION_PRESET_APPLIED_KEY] = True
engine_mode = st.selectbox("engine", options=["research", "pipeline"], key="bt_run_engine_mode")
phase2 = st.selectbox("phase2", options=["off", "risk_execution"], key="bt_run_phase2_mode")
dip = st.checkbox("DIP", value=True, key="bt_run_dip_enabled")
st.write("ok")
"""
    at = AppTest.from_string(code, default_timeout=10)
    at.run()

    # RUN 1 : arrivée sur la page -> le preset par défaut est appliqué.
    assert at.selectbox(key="bt_run_engine_mode").value == "pipeline"
    assert at.selectbox(key="bt_run_phase2_mode").value == "risk_execution"
    assert at.session_state["bt_run_configuration_preset_applied"] is True

    # RUN 2 : l'utilisateur modifie un paramètre -> pas de ré-application.
    at.selectbox(key="bt_run_phase2_mode").set_value("off")
    at.run()
    assert at.selectbox(key="bt_run_phase2_mode").value == "off"

    # RUN 3 : rerun quelconque (ex. toggle DIP) -> la modif manuelle est préservée.
    at.checkbox(key="bt_run_dip_enabled").uncheck()
    at.run()
    assert at.selectbox(key="bt_run_phase2_mode").value == "off"
    assert at.selectbox(key="bt_run_engine_mode").value == "pipeline"


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


def test_build_ml_coverage_status_message_warns_when_coverage_is_partial() -> None:
    level, message = backtesting._build_ml_coverage_status_message(
        {
            "status": "partial",
            "start": "2024-01-01",
            "end": "2024-01-31",
            "capital_preset_key": "capital_50001_100000",
            "capital_preset_filtered": True,
            "effective_strategy": "use-persisted",
            "expected_universe_symbol_dates": 10,
            "covered_prediction_symbol_dates": 7,
            "missing_prediction_symbol_dates": 3,
            "coverage_pct": 70.0,
        }
    )

    assert level == "warning"
    assert "7/10" in message
    assert "70.0%" in message
    assert "rebuild-missing" in message
    assert "capital_50001_100000" in message


def test_build_ml_coverage_status_message_reports_disabled_mode() -> None:
    level, message = backtesting._build_ml_coverage_status_message(
        {
            "status": "disabled",
            "reason": "Mode ML désactivé (`ml_mode=off`).",
        }
    )

    assert level == "info"
    assert "ml_mode=off" in message


def test_render_ml_coverage_preflight_skips_queries_outside_pipeline(monkeypatch) -> None:
    info_messages: list[str] = []

    monkeypatch.setattr(
        backtesting,
        "get_backtesting_ml_coverage_diagnostic",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected diagnostic call")),
    )
    monkeypatch.setattr(backtesting.st, "info", lambda message: info_messages.append(str(message)))

    backtesting._render_ml_coverage_preflight(
        engine_mode="research",
        ml_mode="auto",
        ml_pit_strategy="auto",
        start="2024-01-01",
        end="2024-01-31",
        selected_run_preset_key=backtesting.CAPITAL_PRESET_CUSTOM,
        auto_run_preset_key="capital_50001_100000",
    )

    assert info_messages == ["Préflight couverture ML PIT disponible pour `engine-mode pipeline` uniquement."]


def test_render_ml_coverage_preflight_renders_metrics_and_samples(monkeypatch) -> None:
    warning_messages: list[str] = []
    metric_calls: list[tuple[str, object]] = []
    caption_messages: list[str] = []
    dataframe_rows: list[int] = []

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        backtesting,
        "get_backtesting_ml_coverage_diagnostic",
        lambda **kwargs: {
            "status": "partial",
            "start": "2024-01-01",
            "end": "2024-01-31",
            "capital_preset_key": "capital_50001_100000",
            "capital_preset_filtered": True,
            "effective_strategy": "use-persisted",
            "expected_universe_symbol_dates": 10,
            "covered_prediction_symbol_dates": 7,
            "missing_prediction_symbol_dates": 3,
            "missing_snapshot_days": 2,
            "coverage_pct": 70.0,
            "fast_mode_estimate": {"summary": "Mode rapide : 7/10 couverts."},
            "rebuild_missing_estimate": {"summary": "rebuild-missing : 3 paires à reconstruire."},
            "missing_days_sample": [{"trade_date": "2024-01-03", "missing_count": 2}],
            "missing_rows_sample": [{"trade_date": "2024-01-03", "symbol": "AAPL"}],
        },
    )
    monkeypatch.setattr(backtesting.st, "warning", lambda message: warning_messages.append(str(message)))
    monkeypatch.setattr(backtesting.st, "success", lambda message: (_ for _ in ()).throw(AssertionError(message)))
    monkeypatch.setattr(backtesting.st, "error", lambda message: (_ for _ in ()).throw(AssertionError(message)))
    monkeypatch.setattr(backtesting.st, "info", lambda message: (_ for _ in ()).throw(AssertionError(message)))
    monkeypatch.setattr(backtesting.st, "metric", lambda label, value: metric_calls.append((str(label), value)))
    monkeypatch.setattr(backtesting.st, "caption", lambda message: caption_messages.append(str(message)))
    monkeypatch.setattr(backtesting.st, "dataframe", lambda df, **kwargs: dataframe_rows.append(len(df)))
    monkeypatch.setattr(backtesting.st, "columns", lambda n: [_Ctx() for _ in range(n)])
    monkeypatch.setattr(backtesting.st, "expander", lambda *args, **kwargs: _Ctx())

    backtesting._render_ml_coverage_preflight(
        engine_mode="pipeline",
        ml_mode="auto",
        ml_pit_strategy="auto",
        start="2024-01-01",
        end="2024-01-31",
        selected_run_preset_key=backtesting.CAPITAL_PRESET_CUSTOM,
        auto_run_preset_key="capital_50001_100000",
    )

    assert len(warning_messages) == 1
    assert "7/10" in warning_messages[0]
    assert metric_calls == [
        ("Univers attendu", 10),
        ("Déjà couverts", 7),
        ("Taux de couverture", "70.0%"),
        ("Manquants", 3),
        ("Séances manquantes", 2),
    ]
    assert any("Mode rapide estimé" in message for message in caption_messages)
    assert any("rebuild-missing" in message for message in caption_messages)
    assert dataframe_rows == [1, 1]


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


def test_resolve_phase2_risk_summary_prefers_report_params() -> None:
    payload = backtesting._resolve_phase2_risk_summary(
        {
            "phase2": {
                "risk_bridge": {
                    "regime_enabled": True,
                    "macro_missing_dates_count": 3,
                }
            }
        },
        {},
    )

    assert payload == {
        "regime_enabled": True,
        "macro_missing_dates_count": 3,
    }


def test_resolve_phase2_risk_summary_falls_back_to_artifact(tmp_path) -> None:
    artifact_path = tmp_path / "phase2_risk_summary.json"
    artifact_path.write_text(
        json.dumps(
            {
                "regime_enabled": True,
                "macro_missing_dates_count": 2,
                "macro_missing_dates": ["2025-05-01", "2025-05-02"],
            }
        ),
        encoding="utf-8",
    )

    payload = backtesting._resolve_phase2_risk_summary(
        {},
        {"phase2_risk_summary_json": str(artifact_path)},
    )

    assert payload["regime_enabled"] is True
    assert payload["macro_missing_dates_count"] == 2
    assert payload["macro_missing_dates"] == ["2025-05-01", "2025-05-02"]


def test_build_replay_diagnostic_session_rows_formats_expected_columns() -> None:
    rows = backtesting._build_replay_diagnostic_session_rows(
        {
            "sessions": [
                {
                    "trade_date": "2025-01-02",
                    "scoring_rows": 5,
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
        "Lignes score",
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


def test_build_selection_target_parity_rows_formats_expected_columns() -> None:
    rows = backtesting._build_selection_target_parity_rows(
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
                        "divergence_reasons": ["research_only_selections", "risk_rejections"],
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
                    "selection_compare": {"status": "diverged"},
                    "risk_compare": {"status": "aligned"},
                    "portfolio_compare": {"status": "missing_live"},
                    "execution_compare": {"status": "diverged"},
                    "fills_compare": {"status": "aligned"},
                    "exits_compare": {"status": "missing_replay"},
                    "pnl_compare": {"status": "aligned"},
                    "top_divergences": [
                        {"component": "selections", "symbol": "BBB", "divergence_kind": "missing_live_selection"},
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
    assert "selections:BBB:missing_live_selection" in rows.iloc[0]["Divergences clés"]


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


def test_should_preload_runtime_details_only_for_active_runs() -> None:
    assert backtesting._should_preload_runtime_details("running") is True
    assert backtesting._should_preload_runtime_details("starting") is True
    assert backtesting._should_preload_runtime_details("completed") is False
    assert backtesting._should_preload_runtime_details("failed") is False


def test_should_auto_refresh_runtime_center_only_when_some_run_group_is_active() -> None:
    assert backtesting._should_auto_refresh_runtime_center([], [], []) is False
    assert backtesting._should_auto_refresh_runtime_center([{"run_id": "r1"}], [], []) is True


def test_is_runtime_center_auto_update_enabled_defaults_to_true() -> None:
    backtesting.st.session_state.pop(backtesting.RUNTIME_CENTER_AUTO_UPDATE_KEY, None)

    assert backtesting._is_runtime_center_auto_update_enabled() is True


def test_is_runtime_center_auto_update_enabled_reads_session_preference() -> None:
    backtesting.st.session_state[backtesting.RUNTIME_CENTER_AUTO_UPDATE_KEY] = False

    assert backtesting._is_runtime_center_auto_update_enabled() is False




def test_clear_history_selection_resets_selection_rows(monkeypatch) -> None:
    """Après suppression, la sélection du dataframe doit être vidée."""
    state = {"selection": {"rows": [0, 2]}}
    backtesting.st.session_state[backtesting.BACKTESTING_HISTORY_TABLE_KEY] = state

    backtesting._clear_history_selection()

    assert backtesting.st.session_state[backtesting.BACKTESTING_HISTORY_TABLE_KEY]["selection"]["rows"] == []


def test_clear_history_selection_handles_attribute_selection(monkeypatch) -> None:
    """Supporte aussi le cas où selection est exposé comme attribut (objet)."""
    class _Selection:
        def __init__(self):
            self.rows = [0, 1]

    class _State:
        def __init__(self):
            self.selection = _Selection()

    backtesting.st.session_state[backtesting.BACKTESTING_HISTORY_TABLE_KEY] = _State()

    backtesting._clear_history_selection()

    assert backtesting.st.session_state[backtesting.BACKTESTING_HISTORY_TABLE_KEY].selection.rows == []


def test_clear_history_selection_noop_when_no_state() -> None:
    backtesting.st.session_state.pop(backtesting.BACKTESTING_HISTORY_TABLE_KEY, None)
    backtesting._clear_history_selection()  # ne doit pas lever
