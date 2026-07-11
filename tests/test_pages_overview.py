from ihm.pages import overview

def test_pages_overview_importable():
    assert hasattr(overview, "__doc__")


# ---------------------------------------------------------------------------
# Sprint S4 / A-021 — compute_daily_pnl
# ---------------------------------------------------------------------------


def test_compute_daily_pnl_with_positions() -> None:
    """compute_daily_pnl retourne le PnL et le % depuis les données broker."""
    pnl_data = {
        "unrealized_pnl": 500.0,
        "total_market_value": 10_500.0,
        "open_positions": 3,
        "available": True,
        "snapshot_at": "2026-05-16 18:00:00",
    }
    pnl, pct = overview.compute_daily_pnl(pnl_data)
    assert pnl == 500.0
    # cost_basis = 10_500 - 500 = 10_000 → pnl_pct = 500/10_000 = 0.05
    assert abs(pct - 0.05) < 1e-6


def test_compute_daily_pnl_zero_positions() -> None:
    """compute_daily_pnl retourne (0.0, 0.0) quand aucune position (paper trading)."""
    pnl_data = {
        "unrealized_pnl": 0.0,
        "total_market_value": 0.0,
        "open_positions": 0,
        "available": False,
        "snapshot_at": None,
    }
    pnl, pct = overview.compute_daily_pnl(pnl_data)
    assert pnl == 0.0
    assert pct == 0.0


def test_compute_daily_pnl_negative_pnl() -> None:
    """compute_daily_pnl gère le PnL négatif correctement."""
    pnl_data = {
        "unrealized_pnl": -200.0,
        "total_market_value": 9_800.0,
        "open_positions": 2,
        "available": True,
        "snapshot_at": None,
    }
    pnl, pct = overview.compute_daily_pnl(pnl_data)
    assert pnl == -200.0
    # cost_basis = 9_800 - (-200) = 10_000 → pnl_pct = -200/10_000 = -0.02
    assert abs(pct - (-0.02)) < 1e-6


def test_build_pipeline_summary_rows_exposes_latest_workflow_and_upstream_runs() -> None:
    runs = [
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "step_key": "pipeline_workflow",
            "status": "completed",
            "run_summary": {"workflow_steps_with_summary": 2, "targeted_symbols": 6, "successful_symbols": 5},
        },
        {
            "run_id": "imp-1",
            "run_kind": "step",
            "step_key": "import_alpaca_bar",
            "status": "completed",
            "run_summary": {"targeted_symbols": 3, "successful_symbols": 2},
        },
        {
            "run_id": "san-1",
            "run_kind": "step",
            "step_key": "data_sanitizer_daily",
            "status": "completed",
            "run_summary": {"targeted_symbols": 3, "successful_symbols": 3},
        },
        {
            "run_id": "scr-1",
            "run_kind": "step",
            "step_key": "stock_screener",
            "status": "completed",
            "run_summary": {"targeted_symbols": 3, "symbols_final": 2},
        },
        {
            "run_id": "sel-1",
            "run_kind": "step",
            "step_key": "alpha_scanner",
            "status": "completed",
            "run_summary": {"requested_selection_size": 50, "selected_selections": 2},
        },
        {
            "run_id": "sent-1",
            "run_kind": "step",
            "step_key": "sentiment_pipeline",
            "status": "completed",
            "run_summary": {"resolved_symbols": 2, "fetched_articles": 12},
        },
        {
            "run_id": "rel-1",
            "run_kind": "step",
            "step_key": "relevance_backfill",
            "status": "completed",
            "run_summary": {"targeted_articles": 12, "rescored_pairs": 4},
        },
        {
            "run_id": "agg-1",
            "run_kind": "step",
            "step_key": "signal_aggregator",
            "status": "completed",
            "run_summary": {"loaded_symbols": 2, "updated_symbols": 2},
        },
    ]

    rows = overview._build_pipeline_summary_rows(runs)

    scope_list = list(rows["scope"])
    # Vérification flexible (les noms de labels de certains steps peuvent évoluer).
    assert any("Workflow" in s for s in scope_list)
    assert any("Import Alpaca" in s for s in scope_list)
    assert any("Sanitizer" in s or "sanitizer" in s.lower() for s in scope_list)
    assert any("Screener" in s or "screener" in s.lower() for s in scope_list)
    assert any("Alpha Scanner" in s for s in scope_list)
    assert any("Sentiment" in s for s in scope_list)
    assert any("Signal" in s or "Aggregator" in s for s in scope_list)


def test_build_pipeline_summary_rows_exposes_quote_bias_in_sync_latest_quotes_caption() -> None:
    runs = [
        {
            "run_id": "quotes-1",
            "run_kind": "step",
            "step_key": "sync_latest_quotes",
            "status": "completed",
            "run_summary": {
                "symbols": 120,
                "rows_upserted": 118,
                "quote_iex_vs_consolidated_bps": 42.5,
                "quote_iex_vs_consolidated_observations": 90,
                "batch_size": 50,
            },
        },
    ]

    rows = overview._build_pipeline_summary_rows(runs)

    assert not rows.empty
    sync_quotes_row = rows.loc[rows["scope"].astype(str).str.contains("Sync Latest Quotes", regex=False)].iloc[0]
    assert "biais iex=42.5" in str(sync_quotes_row["résumé métier"])
    assert "obs. biais=90" in str(sync_quotes_row["résumé métier"])


def test_build_screener_objective_rows_exposes_operational_leaders() -> None:
    rows = overview._build_screener_objective_rows(
        {
            "objective_rows_df": overview.pd.DataFrame(
                [
                    {
                        "objective": "robust",
                        "objective_label": "robuste",
                        "scenario_name": "steady",
                        "objective_scope": "cross_regime",
                        "objective_score": 0.77,
                        "overall_score": 0.75,
                    }
                ]
            )
        }
    )

    assert list(rows.columns) == ["objectif", "label", "scénario", "périmètre", "score objectif", "score global"]
    assert rows.iloc[0]["scénario"] == "steady"


def test_build_screener_history_dataframe_exposes_shared_artifact_rows() -> None:
    history_df = overview._build_screener_history_dataframe(
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
                "source_tags": ["défaut", "runs IHM"],
            }
        ]
    )

    assert history_df.iloc[0]["Origines"] == "défaut, runs IHM"
    assert history_df.iloc[0]["Runs IHM"] == 3


def test_build_eodhd_quota_feature_rows_sorts_by_calls_desc() -> None:
    rows = overview._build_eodhd_quota_feature_rows(
        {
            "feature_calls": {
                "event_sentiment": 7,
                "corporate_actions": 2,
                "selector": 11,
            }
        }
    )

    assert list(rows["feature"]) == ["selector", "event_sentiment", "corporate_actions"]
    assert list(rows["calls_used"]) == [11, 7, 2]


def test_build_eodhd_quota_feature_rows_returns_empty_dataframe_without_feature_calls() -> None:
    rows = overview._build_eodhd_quota_feature_rows({})
    assert rows.empty


