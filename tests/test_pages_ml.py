from io import BytesIO

import pandas as pd
from zipfile import ZipFile

from ihm.pages import ml

def test_pages_ml_importable():
    assert hasattr(ml, "__doc__")


def test_summarize_prediction_governance_audit_counts_mismatches() -> None:
    audit_df = pd.DataFrame(
        [
            {
                "served_model": "lightgbm",
                "governance_champion_model": "lightgbm",
                "governance_link_status": "aligned",
            },
            {
                "served_model": "catboost",
                "governance_champion_model": "lightgbm",
                "governance_link_status": "served_model_differs_from_governance_champion",
            },
        ]
    )

    summary = ml._summarize_prediction_governance_audit(audit_df)

    assert summary["latest_served_model"] == "lightgbm"
    assert summary["latest_governance_champion"] == "lightgbm"
    assert summary["latest_link_status"] == "aligned"
    assert summary["mismatch_count"] == 1


def test_build_prediction_audit_filter_options_merges_audit_and_governance_sources() -> None:
    audit_df = pd.DataFrame(
        [
            {
                "run_id": "run-2",
                "served_model": "lightgbm",
                "governance_selection_mode": "auto_selected_champion",
                "governance_link_status": "aligned",
            },
            {
                "run_id": "run-1",
                "served_model": "catboost",
                "governance_selection_mode": "fallback_default_champion",
                "governance_link_status": "served_model_differs_from_governance_champion",
            },
        ]
    )
    governance_df = pd.DataFrame(
        [
            {"run_id": "run-3", "selection_mode": "default_champion"},
            {"run_id": "run-2", "selection_mode": "auto_selected_champion"},
        ]
    )

    options = ml._build_prediction_audit_filter_options(audit_df, governance_df)

    assert options["governance_link_statuses"] == [
        "aligned",
        "served_model_differs_from_governance_champion",
    ]
    assert options["selection_modes"] == [
        "auto_selected_champion",
        "default_champion",
        "fallback_default_champion",
    ]
    assert options["served_models"] == ["catboost", "lightgbm"]
    assert options["run_ids"] == ["run-3", "run-2", "run-1"]


def test_build_prediction_audit_navigation_options_prefers_artifact_symbols() -> None:
    audit_df = pd.DataFrame(
        [
            {
                "prediction_date": "2026-04-23",
                "symbol": "AAPL",
                "run_id": "run-1",
                "served_model": "global_model",
                "governance_link_status": "aligned",
                "governance_selection_mode": "auto_selected_champion",
                "governance_champion_artifact_symbol": "__GLOBAL__",
                "governance_served_artifact_symbol": "AAPL",
            }
        ]
    )

    options = ml._build_prediction_audit_navigation_options(audit_df)

    assert len(options) == 1
    assert options[0]["run_id"] == "run-1"
    assert options[0]["artifact_symbol"] == "__GLOBAL__"
    assert "servi=global_model" in options[0]["label"]


def test_resolve_navigation_symbol_falls_back_to_symbol() -> None:
    option = {
        "artifact_symbol": "__GLOBAL__",
        "symbol": "AAPL",
    }

    resolved = ml._resolve_navigation_symbol(option, ["AAPL", "MSFT"])

    assert resolved == "AAPL"


def test_focus_dataframe_on_navigation_row_moves_selected_row_first() -> None:
    audit_df = pd.DataFrame(
        [
            {"prediction_date": "2026-04-22", "symbol": "AAPL", "run_id": "run-1", "served_model": "catboost"},
            {"prediction_date": "2026-04-23", "symbol": "AAPL", "run_id": "run-1", "served_model": "lightgbm"},
        ]
    )
    navigation_option = {
        "label": "2026-04-23 | AAPL | run-1 | servi=lightgbm | statut=aligned",
        "symbol": "AAPL",
        "run_id": "run-1",
        "served_model": "lightgbm",
    }

    ordered, focused = ml._focus_dataframe_on_navigation_row(audit_df, navigation_option)

    assert len(focused) == 1
    assert focused.iloc[0]["served_model"] == "lightgbm"
    assert ordered.iloc[0]["served_model"] == "lightgbm"


def test_build_ml_run_export_dataframe_includes_sections() -> None:
    focused = pd.DataFrame([{"run_id": "run-1", "symbol": "AAPL"}])
    governance = pd.DataFrame([{"run_id": "run-1", "model_name": "lightgbm"}])
    audit_rows = pd.DataFrame([{"run_id": "run-1", "served_model": "lightgbm"}])
    predictions = pd.DataFrame([{"run_id": "run-1", "predicted_class": 1}])
    artifact_report = {
        "symbol": "AAPL",
        "run_id": "run-1",
        "selected_model": "lightgbm",
        "selection_mode": "auto_selected_champion",
        "selected_decision_threshold": 0.61,
        "config_path": "config.json",
        "metrics_path": "metrics.json",
        "routes_df": pd.DataFrame([{"model_name": "lightgbm"}]),
        "ranking_df": pd.DataFrame([{"model_name": "lightgbm", "rank": 1}]),
    }

    export_df = ml._build_ml_run_export_dataframe(
        run_id="run-1",
        focused_audit_row=focused,
        run_governance=governance,
        run_audit_rows=audit_rows,
        run_predictions=predictions,
        artifact_report=artifact_report,
    )

    assert set(export_df["section"].dropna().unique()) == {
        "selected_audit_row",
        "run_governance",
        "run_prediction_audit",
        "run_predictions",
        "artifact_summary",
        "artifact_routes_snapshot",
        "artifact_ranking_snapshot",
    }


def test_build_ml_run_export_filename_sanitizes_inputs() -> None:
    filename = ml._build_ml_run_export_filename("run/1:test", "AAPL")

    assert filename == "ml_run_audit_AAPL_run_1_test.csv"


def test_build_ml_run_export_zip_filename_sanitizes_inputs() -> None:
    filename = ml._build_ml_run_export_zip_filename("run/1:test", "AAPL")

    assert filename == "ml_run_audit_AAPL_run_1_test.zip"


def test_build_ml_run_export_zip_bytes_contains_csv_and_artifact_manifests(tmp_path) -> None:
    export_df = pd.DataFrame([{"section": "run_predictions", "run_id": "run-1", "symbol": "AAPL"}])
    config_path = tmp_path / "config.json"
    metrics_path = tmp_path / "metrics.json"
    config_path.write_text('{"run_id": "run-1", "selection_mode": "auto_selected_champion"}', encoding="utf-8")
    metrics_path.write_text('{"champion": {"model_name": "lightgbm"}}', encoding="utf-8")
    artifact_report = {
        "symbol": "AAPL",
        "run_id": "run-1",
        "config_path": config_path,
        "metrics_path": metrics_path,
        "config": {"run_id": "run-1"},
        "metrics": {"champion": {"model_name": "lightgbm"}},
        "errors": [],
    }

    zip_bytes = ml._build_ml_run_export_zip_bytes(
        export_df=export_df,
        artifact_report=artifact_report,
        focused_audit_row=pd.DataFrame(
            [{"governance_link_status": "aligned", "served_model": "lightgbm", "governance_selection_mode": "auto_selected_champion"}]
        ),
        selected_navigation={"governance_link_status": "aligned", "served_model": "lightgbm", "selection_mode": "auto_selected_champion"},
        exported_at="2026-04-23T22:55:00+00:00",
        run_id="run-1",
        symbol="AAPL",
    )

    with ZipFile(BytesIO(zip_bytes)) as archive:
        assert "ml_run_audit_AAPL_run-1.csv" in archive.namelist()
        assert '"selection_mode": "auto_selected_champion"' in archive.read("config.json").decode("utf-8")
        assert '"model_name": "lightgbm"' in archive.read("metrics.json").decode("utf-8")
        readme = archive.read("README.txt").decode("utf-8")
        assert "Alpha Trade — Export ML du run sélectionné" in readme
        assert "Horodatage d'export (UTC) : 2026-04-23T22:55:00+00:00" in readme
        assert "Statut d'alignement de la ligne sélectionnée : aligned" in readme
        assert "config.json" in readme
        assert "metrics.json" in readme
        assert "run_predictions" in readme


def test_build_ml_run_export_zip_bytes_falls_back_to_loaded_json_when_files_missing() -> None:
    export_df = pd.DataFrame([{"section": "run_predictions", "run_id": "run-1"}])
    artifact_report = {
        "symbol": "AAPL",
        "run_id": "run-1",
        "config_path": "missing_config.json",
        "metrics_path": "missing_metrics.json",
        "config": {"run_id": "run-1", "selection_mode": "default_champion"},
        "metrics": {"champion": {"model_name": "lstm_attention"}},
        "errors": ["Fichier absent : `config.json`"],
    }

    zip_bytes = ml._build_ml_run_export_zip_bytes(
        export_df=export_df,
        artifact_report=artifact_report,
        focused_audit_row=pd.DataFrame(
            [{"governance_link_status": "aligned", "served_model": "lstm_attention", "governance_selection_mode": "default_champion"}]
        ),
        selected_navigation={
            "governance_link_status": "aligned",
            "served_model": "lstm_attention",
            "selection_mode": "default_champion",
        },
        exported_at="2026-04-23T22:55:00+00:00",
        run_id="run-1",
        symbol="AAPL",
    )

    with ZipFile(BytesIO(zip_bytes)) as archive:
        config_payload = archive.read("config.json").decode("utf-8")
        metrics_payload = archive.read("metrics.json").decode("utf-8")
        readme = archive.read("README.txt").decode("utf-8")
        assert '"selection_mode": "default_champion"' in config_payload
        assert '"model_name": "lstm_attention"' in metrics_payload
        assert "warning" in config_payload
        assert "Horodatage d'export (UTC) : 2026-04-23T22:55:00+00:00" in readme
        assert "Statut d'alignement de la ligne sélectionnée : aligned" in readme
        assert "reconstruits à partir des données déjà chargées en mémoire" in readme


