from __future__ import annotations

from ihm.pages import screening


def test_pages_screening_importable():
    assert hasattr(screening, "__doc__")


def test_build_quality_summary_rows_exposes_recent_pipeline_context() -> None:
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
            "run_summary": {"requested_selection_size": 50, "selected_candidates": 2},
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

    rows = screening._build_quality_summary_rows(runs)

    scope_list = list(rows["scope"])
    # Vérifier la présence des étapes clés (les noms de labels peuvent évoluer).
    assert any("Import Alpaca" in s for s in scope_list)
    assert any("Stock Screener" in s or "screener" in s.lower() for s in scope_list)
    assert any("Alpha Scanner" in s for s in scope_list)
    assert any("Sentiment" in s for s in scope_list)
    assert any("Signal" in s or "Aggregator" in s for s in scope_list)
    assert any("Workflow" in s or "complet" in s for s in scope_list)


def test_build_objective_recommendation_rows_formats_phase7_snapshot() -> None:
    rows = screening._build_objective_recommendation_rows(
        {
            "objective_rows_df": screening.pd.DataFrame(
                [
                    {
                        "objective_label": "robuste",
                        "scenario_name": "steady",
                        "objective_scope": "cross_regime",
                        "objective_score": 0.77,
                        "overall_score": 0.75,
                        "reason": "Stable sur tous les régimes.",
                    }
                ]
            )
        }
    )

    assert list(rows.columns) == [
        "Objectif",
        "Scénario recommandé",
        "Périmètre",
        "Score objectif",
        "Score global",
        "Pourquoi",
    ]
    assert rows.iloc[0]["Scénario recommandé"] == "steady"


def test_build_artifact_history_dataframe_exposes_global_screener_inventory() -> None:
    history_df = screening._build_artifact_history_dataframe(
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

    assert list(history_df.columns) == [
        "Répertoire",
        "Disponible",
        "Couverture",
        "MAJ",
        "Baseline",
        "Reco objectifs",
        "Scénarios",
        "Fichiers",
        "Régimes",
        "Runs IHM",
        "Dernier run",
        "Statut",
        "Origines",
        "Chemin",
    ]
    assert history_df.iloc[0]["Répertoire"] == "artifacts/screener_a"


def test_build_csv_preview_inventory_dataframe_exposes_csv_inventory() -> None:
    inventory_df = screening._build_csv_preview_inventory_dataframe(
        [
            {
                "label": "summary_metrics.csv",
                "row_count": 12,
                "size_label": "1.2 Ko",
                "path": "C:/tmp/screener/summary_metrics.csv",
            }
        ]
    )

    assert list(inventory_df.columns) == ["Fichier", "Lignes", "Taille", "Chemin"]
    assert inventory_df.iloc[0]["Fichier"] == "summary_metrics.csv"


def test_build_screening_display_dataframe_keeps_operator_columns() -> None:
    df = screening.pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "sector": "Technology",
                "is_candidate": 1,
                "candidate_rank": 1,
                "selector_signal_mode": "sector_neutralized",
                "final_score": 0.88,
                "total_score": 91.0,
                "selection_explanation": "mode=sector_neutralized",
                "candidate_explainability_payload": {"identity": {"symbol": "AAPL"}},
            }
        ]
    )

    out = screening._build_screening_display_dataframe(df)

    assert "symbol" in out.columns
    assert "candidate_rank" in out.columns
    assert "selection_explanation" in out.columns
    assert "candidate_explainability_payload" not in out.columns


def test_format_csv_preview_option_includes_label_lines_and_size() -> None:
    label = screening._format_csv_preview_option(
        {
            "label": "daily_metrics.csv",
            "row_count": 240,
            "size_label": "12.3 Ko",
        }
    )

    assert "daily_metrics.csv" in label
    assert "240" in label
    assert "12.3 Ko" in label


# ---------------------------------------------------------------------------
# Sprint S3 / A-015 — alerte TTL market_cap dans l'IHM screening
# ---------------------------------------------------------------------------

def test_render_screening_warning_on_stale_market_cap(monkeypatch) -> None:
    """Si stale_pct > 20%, un st.warning doit être émis."""
    import pandas as pd

    monkeypatch.setattr(screening, "db_available", lambda: True)
    monkeypatch.setattr(screening, "get_stock_scores", lambda: pd.DataFrame({
        "symbol": ["AAPL"],
        "is_candidate": [1],
        "sector": ["Technology"],
        "total_score": [0.7],
    }))
    monkeypatch.setattr(screening, "get_stale_market_cap_stats", lambda **kwargs: {
        "stale_pct": 45.0,
        "stale_symbols": 45,
        "total_symbols": 100,
    })
    # Stopper le reste du rendu Streamlit.
    monkeypatch.setattr(screening.st, "header", lambda *a, **k: None)
    monkeypatch.setattr(screening.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(screening.st, "container", lambda *a, **k: _DummyContainer())
    monkeypatch.setattr(screening.st, "columns", lambda n: [_DummyContext()] * n)
    monkeypatch.setattr(screening.st, "text_input", lambda *a, **k: "")
    monkeypatch.setattr(screening.st, "selectbox", lambda *a, **k: "Tous")
    monkeypatch.setattr(screening.st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(screening.st, "slider", lambda *a, **k: 0.0)
    monkeypatch.setattr(screening, "get_alpha_scanner_dependency_diagnostic", lambda: {})
    monkeypatch.setattr(screening, "render_alpha_scanner_dependency_panel", lambda *a, **k: None)
    monkeypatch.setattr(screening, "render_shared_screener_artifact_selector", lambda **k: ("", {}))
    monkeypatch.setattr(screening, "render_symbol_table", lambda *a, **k: None)
    monkeypatch.setattr(screening, "_merge_pipeline_runs", lambda: [])
    monkeypatch.setattr(screening, "show_dataframe", lambda *a, **k: None)
    monkeypatch.setattr(screening, "metric_row", lambda *a, **k: None)

    warnings_emitted: list[str] = []
    monkeypatch.setattr(screening.st, "warning", lambda msg: warnings_emitted.append(str(msg)))

    screening.render()

    assert any("45%" in w for w in warnings_emitted), "Warning market_cap TTL attendu (45% > 20%)"


def test_render_screening_no_warning_when_market_cap_fresh(monkeypatch) -> None:
    """Si stale_pct <= 20%, pas de warning market_cap TTL."""
    import pandas as pd

    monkeypatch.setattr(screening, "db_available", lambda: True)
    monkeypatch.setattr(screening, "get_stock_scores", lambda: pd.DataFrame({
        "symbol": ["AAPL"],
        "is_candidate": [1],
        "sector": ["Technology"],
        "total_score": [0.7],
    }))
    monkeypatch.setattr(screening, "get_stale_market_cap_stats", lambda **kwargs: {
        "stale_pct": 5.0,
        "stale_symbols": 5,
        "total_symbols": 100,
    })
    monkeypatch.setattr(screening.st, "header", lambda *a, **k: None)
    monkeypatch.setattr(screening.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(screening.st, "container", lambda *a, **k: _DummyContainer())
    monkeypatch.setattr(screening.st, "columns", lambda n: [_DummyContext()] * n)
    monkeypatch.setattr(screening.st, "text_input", lambda *a, **k: "")
    monkeypatch.setattr(screening.st, "selectbox", lambda *a, **k: "Tous")
    monkeypatch.setattr(screening.st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(screening.st, "slider", lambda *a, **k: 0.0)
    monkeypatch.setattr(screening, "get_alpha_scanner_dependency_diagnostic", lambda: {})
    monkeypatch.setattr(screening, "render_alpha_scanner_dependency_panel", lambda *a, **k: None)
    monkeypatch.setattr(screening, "render_shared_screener_artifact_selector", lambda **k: ("", {}))
    monkeypatch.setattr(screening, "render_symbol_table", lambda *a, **k: None)
    monkeypatch.setattr(screening, "_merge_pipeline_runs", lambda: [])
    monkeypatch.setattr(screening, "show_dataframe", lambda *a, **k: None)
    monkeypatch.setattr(screening, "metric_row", lambda *a, **k: None)

    warnings_emitted: list[str] = []
    monkeypatch.setattr(screening.st, "warning", lambda msg: warnings_emitted.append(str(msg)))

    screening.render()

    assert not any("market_cap" in w.lower() and "20" in w for w in warnings_emitted)


def test_render_screening_exposes_candidate_explainability_payload(monkeypatch) -> None:
    import pandas as pd

    selected_payloads: list[dict[str, object]] = []

    monkeypatch.setattr(screening, "db_available", lambda: True)
    monkeypatch.setattr(
        screening,
        "get_stock_scores",
        lambda: pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "sector": ["Technology"],
                "is_candidate": [1],
                "candidate_rank": [1],
                "total_score": [91.0],
                "final_score": [0.88],
                "trend_score": [0.82],
                "vcp_score": [0.71],
                "trend_vcp_component": [0.41],
                "total_score_component": [0.29],
                "rsi_component": [0.18],
                "selector_signal_mode": ["sector_neutralized"],
                "selection_explanation": ["mode=sector_neutralized; trend_vcp=0.4100; total=0.2900; rsi=0.1800; final=0.8800"],
                "candidate_explainability_payload": [
                    {
                        "identity": {"symbol": "AAPL", "candidate_rank": 1},
                        "score_components": {
                            "trend_vcp_component": 0.41,
                            "total_score_component": 0.29,
                            "rsi_component": 0.18,
                        },
                        "selection_context": {
                            "selector_signal_mode": "sector_neutralized",
                            "selection_explanation": "mode=sector_neutralized; trend_vcp=0.4100; total=0.2900; rsi=0.1800; final=0.8800",
                        },
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(screening, "get_stale_market_cap_stats", lambda **kwargs: {"stale_pct": 5.0, "stale_symbols": 5, "total_symbols": 100})
    monkeypatch.setattr(screening.st, "header", lambda *a, **k: None)
    monkeypatch.setattr(screening.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(screening.st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(screening.st, "container", lambda *a, **k: _DummyContainer())
    monkeypatch.setattr(screening.st, "columns", lambda n: [_DummyContext()] * n)
    monkeypatch.setattr(screening.st, "text_input", lambda *a, **k: "")
    monkeypatch.setattr(screening.st, "selectbox", lambda *a, **k: "Tous")
    monkeypatch.setattr(screening.st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(screening.st, "slider", lambda *a, **k: 0.0)
    monkeypatch.setattr(screening.st, "info", lambda *a, **k: None)
    monkeypatch.setattr(screening.st, "json", lambda payload, *a, **k: selected_payloads.append(payload))
    monkeypatch.setattr(screening, "get_alpha_scanner_dependency_diagnostic", lambda: {})
    monkeypatch.setattr(screening, "render_alpha_scanner_dependency_panel", lambda *a, **k: None)
    monkeypatch.setattr(screening, "render_shared_screener_artifact_selector", lambda **k: ("", {}))
    monkeypatch.setattr(screening, "render_symbol_table", lambda *a, **k: "AAPL")
    monkeypatch.setattr(screening, "_merge_pipeline_runs", lambda: [])
    monkeypatch.setattr(screening, "show_dataframe", lambda *a, **k: None)
    monkeypatch.setattr(screening, "metric_row", lambda *a, **k: None)

    screening.render()

    assert selected_payloads
    payload = selected_payloads[0]
    assert payload["identity"]["symbol"] == "AAPL"
    assert payload["selection_context"]["selector_signal_mode"] == "sector_neutralized"


class _DummyContainer:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def subheader(self, *a, **k):
        pass

    def caption(self, *a, **k):
        pass


class _DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def text_input(self, *a, **k):
        return ""

    def selectbox(self, *a, **k):
        return "Tous"
