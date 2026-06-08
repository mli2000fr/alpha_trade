from datetime import date as dt_date, datetime, time as dt_time, timedelta
from typing import cast

import pytest

from ihm.pages import _data_integrity as data_integrity_page, _watcher_block as watcher_block, _workflow as workflow_page, pipeline


class _DummyContainer:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyColumn(_DummyContainer):
    pass


class _WidgetBoundSessionState(dict[str, object]):
    def __init__(self) -> None:
        super().__init__()
        self._widget_keys: set[str] = set()

    def bind_widget_value(self, key: str, value: object) -> None:
        super().__setitem__(key, value)
        self._widget_keys.add(key)

    def __setitem__(self, key: str, value: object) -> None:
        if key in self._widget_keys:
            raise AssertionError(f"post-widget mutation interdite pour {key}")
        super().__setitem__(key, value)


def test_pages_pipeline_importable():
    assert hasattr(pipeline, "__doc__")


def test_pipeline_render_renders_import_news_panel_outside_auto_refresh_fragment(monkeypatch) -> None:
    panel_calls: list[tuple[bool, dict[str, list[dict[str, object]]], list[dict[str, object]], dict[str, dict[str, object]]]] = []
    render_markers: list[str] = []

    monkeypatch.setattr(pipeline.st, "header", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "subheader", lambda value, *args, **kwargs: render_markers.append(str(value)))
    monkeypatch.setattr(pipeline, "_build_launch_options", lambda: (pipeline.PipelineLaunchOptions(), False))
    monkeypatch.setattr(pipeline, "_render_execution_mode_banner", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "get_runtime_db_config", lambda: {})
    monkeypatch.setattr(pipeline, "_render_workflow_launcher", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "_render_runtime_center", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "_render_step_panels", lambda *args, **kwargs: render_markers.append("fragment"))
    monkeypatch.setattr(
        pipeline,
        "_build_pipeline_run_context",
        lambda: ([], [{"run_id": "manual-1", "step_key": "sentiment_standard_scoring"}], {"sentiment_standard_scoring": {"run_id": "manual-1"}}, False, {"sentiment_standard_scoring": [{"run_id": "manual-1"}]}),
    )

    def _fake_render_import_news_panel(options, db_config, *, workflow_active, active_by_step, all_runs, latest_by_step):
        panel_calls.append((workflow_active, active_by_step, all_runs, latest_by_step))

    monkeypatch.setattr(pipeline, "_render_import_news_panel", _fake_render_import_news_panel)

    pipeline.render()

    assert render_markers == ["fragment"]
    assert panel_calls == [
        (
            False,
            {"sentiment_standard_scoring": [{"run_id": "manual-1"}]},
            [{"run_id": "manual-1", "step_key": "sentiment_standard_scoring"}],
            {"sentiment_standard_scoring": {"run_id": "manual-1"}},
        )
    ]


def test_render_import_news_panel_previews_use_selected_date_window(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    preview_calls: list[tuple[str, object, object]] = []
    captions: list[str] = []

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda value, *args, **kwargs: captions.append(str(value)))
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    target_start = dt_date(2022, 1, 1)
    target_end = dt_date(2022, 1, 31)

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = target_start.isoformat()
        elif "date de fin" in lowered_label:
            value = target_end.isoformat()
        else:
            value = ""
        if key:
            session_state[key] = value
        return value

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))

    def _fake_build_pipeline_command(step_key, options):
        preview_calls.append((step_key, options.news_import_start_date, options.news_import_end_date))
        return ["python", step_key, str(options.news_import_start_date), str(options.news_import_end_date)]

    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", _fake_build_pipeline_command)
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert len(preview_calls) == 5
    assert [step_key for step_key, _start, _end in preview_calls] == [
        "import_news",
        "sentiment_relevance_backfill",
        "sentiment_standard_scoring",
        "sentiment_contextual_scoring",
        "rebuild_daily_sentiment_features_only",
    ]
    assert all(start == "2022-01-01" for _key, start, _end in preview_calls)
    assert all(end == "2022-01-31" for _key, _start, end in preview_calls)
    assert any("Fenêtre appliquée : 2022-01-01 → 2022-01-31" in value for value in captions)


def test_render_import_news_panel_previews_follow_successive_end_date_changes(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    preview_calls: list[tuple[str, object, object]] = []
    end_values = iter([dt_date(2022, 1, 31), dt_date(2022, 2, 15)])

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = dt_date(2022, 1, 1).isoformat()
        elif "date de fin" in lowered_label:
            value = next(end_values).isoformat()
        else:
            value = ""
        if key:
            session_state[key] = value
        return value

    def _fake_build_pipeline_command(step_key, options):
        preview_calls.append((step_key, options.news_import_start_date, options.news_import_end_date))
        return ["python", step_key, str(options.news_import_start_date), str(options.news_import_end_date)]

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", _fake_build_pipeline_command)
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )
    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert [end for _key, _start, end in preview_calls[:5]] == ["2022-01-31"] * 5
    assert [end for _key, _start, end in preview_calls[5:]] == ["2022-02-15"] * 5


def test_render_import_news_panel_previews_follow_end_change_after_start_change(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    preview_calls: list[tuple[str, object, object]] = []
    render_index = {"value": 0}

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = (dt_date(2020, 1, 1) if render_index["value"] >= 1 else dt_date(2022, 1, 1)).isoformat()
        elif "date de fin" in lowered_label:
            value = (dt_date(2020, 1, 31) if render_index["value"] >= 2 else dt_date(2026, 5, 17)).isoformat()
        else:
            value = ""
        if key:
            session_state[key] = value
        return value

    def _fake_build_pipeline_command(step_key, options):
        preview_calls.append((step_key, options.news_import_start_date, options.news_import_end_date))
        return ["python", step_key, str(options.news_import_start_date), str(options.news_import_end_date)]

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", _fake_build_pipeline_command)
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )
    render_index["value"] = 1
    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )
    render_index["value"] = 2
    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert [end for _key, _start, end in preview_calls[:5]] == ["2026-05-17"] * 5
    assert [end for _key, _start, end in preview_calls[5:10]] == ["2026-05-17"] * 5
    assert [end for _key, _start, end in preview_calls[10:]] == ["2020-01-31"] * 5


def test_render_import_news_panel_previews_follow_year_change_on_start_then_end(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    preview_calls: list[tuple[str, object, object]] = []
    render_index = {"value": 0}

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = (dt_date(2020, 1, 1) if render_index["value"] >= 1 else dt_date(2022, 1, 1)).isoformat()
        elif "date de fin" in lowered_label:
            value = (dt_date(2020, 1, 31) if render_index["value"] >= 2 else dt_date(2026, 5, 17)).isoformat()
        else:
            value = ""
        if key and key not in session_state:
            session_state[key] = value
        return session_state.get(key, value)

    def _fake_build_pipeline_command(step_key, options):
        preview_calls.append((step_key, options.news_import_start_date, options.news_import_end_date))
        return ["python", step_key, str(options.news_import_start_date), str(options.news_import_end_date)]

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", _fake_build_pipeline_command)
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )
    session_state[data_integrity_page.IMPORT_NEWS_START_DATE_KEY] = dt_date(2020, 1, 1).isoformat()
    render_index["value"] = 1
    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )
    session_state[data_integrity_page.IMPORT_NEWS_END_DATE_KEY] = dt_date(2020, 1, 31).isoformat()
    render_index["value"] = 2
    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert [end for _key, _start, end in preview_calls[:5]] == ["2026-05-17"] * 5
    assert [end for _key, _start, end in preview_calls[5:10]] == ["2026-05-17"] * 5
    assert [end for _key, _start, end in preview_calls[10:]] == ["2020-01-31"] * 5


def test_render_import_news_panel_previews_prefer_latest_end_widget_state_over_stale_persisted_value(monkeypatch) -> None:
    session_state: dict[str, object] = {
        data_integrity_page.IMPORT_NEWS_START_DATE_KEY: dt_date(2020, 1, 1).isoformat(),
        data_integrity_page.IMPORT_NEWS_END_DATE_KEY: dt_date(2026, 5, 17).isoformat(),
    }
    preview_calls: list[tuple[str, object, object]] = []

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de fin" in lowered_label:
            session_state[key] = dt_date(2020, 1, 31).isoformat()
        elif "date de début" not in lowered_label:
            session_state[key] = ""
        return session_state[key]

    def _fake_build_pipeline_command(step_key, options):
        preview_calls.append((step_key, options.news_import_start_date, options.news_import_end_date))
        return ["python", step_key, str(options.news_import_start_date), str(options.news_import_end_date)]

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", _fake_build_pipeline_command)
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert len(preview_calls) == 5
    assert all(start == "2020-01-01" for _key, start, _end in preview_calls)
    assert all(end == "2020-01-31" for _key, _start, end in preview_calls)
    assert session_state[data_integrity_page.IMPORT_NEWS_END_DATE_KEY] == dt_date(2020, 1, 31).isoformat()


def test_render_import_news_panel_previews_use_latest_widget_state_even_if_date_input_returns_stale_value(monkeypatch) -> None:
    session_state: dict[str, object] = {
        data_integrity_page.IMPORT_NEWS_END_DATE_KEY: dt_date(2026, 5, 17).isoformat(),
    }
    preview_calls: list[tuple[str, object, object]] = []

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = dt_date(2022, 1, 1).isoformat()
            if key:
                session_state[key] = value
            return value
        if "date de fin" not in lowered_label:
            return ""
        if key:
            session_state[key] = dt_date(2020, 1, 31).isoformat()
        return dt_date(2026, 5, 17).isoformat()

    def _fake_build_pipeline_command(step_key, options):
        preview_calls.append((step_key, options.news_import_start_date, options.news_import_end_date))
        return ["python", step_key, str(options.news_import_start_date), str(options.news_import_end_date)]

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", _fake_build_pipeline_command)
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert len(preview_calls) == 5
    assert all(end == "2020-01-31" for _key, _start, end in preview_calls)


def test_render_import_news_panel_invalid_end_date_does_not_reuse_previous_valid_end(monkeypatch) -> None:
    session_state: dict[str, object] = {
        data_integrity_page.IMPORT_NEWS_START_DATE_KEY: dt_date(2026, 5, 10).isoformat(),
        data_integrity_page.IMPORT_NEWS_END_DATE_KEY: dt_date(2026, 5, 17).isoformat(),
    }
    captions: list[str] = []
    errors: list[str] = []
    preview_calls: list[tuple[str, object, object]] = []

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda value, *args, **kwargs: captions.append(str(value)))
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda value, *args, **kwargs: errors.append(str(value)))
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            session_state[key] = "2020-04-01"
        elif "date de fin" in lowered_label:
            session_state[key] = "2020-04-31"
        else:
            session_state[key] = str(kwargs.get("value", "") or "")
        return session_state[key]

    def _fake_build_pipeline_command(step_key, options):
        preview_calls.append((step_key, options.news_import_start_date, options.news_import_end_date))
        return ["python", step_key, str(options.news_import_start_date), str(options.news_import_end_date)]

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", _fake_build_pipeline_command)
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert preview_calls == []
    assert any("Date de fin invalide" in message for message in errors)
    assert any("Fenêtre appliquée : 2020-04-01 → invalide (2020-04-31)" in value for value in captions)
    assert session_state[data_integrity_page.IMPORT_NEWS_START_DATE_KEY] == "2020-04-01"
    assert session_state[data_integrity_page.IMPORT_NEWS_END_DATE_KEY] == "2020-04-31"


def test_render_import_news_panel_does_not_mutate_widget_bound_date_keys_after_date_input(monkeypatch) -> None:
    session_state = _WidgetBoundSessionState()

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    target_start = dt_date(2022, 1, 1).isoformat()
    target_end = dt_date(2022, 1, 31).isoformat()

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = target_start
        elif "date de fin" in lowered_label:
            value = target_end
        else:
            value = ""
        if key:
            session_state.bind_widget_value(key, value)
        return value

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", lambda step_key, options: [step_key])
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert session_state[data_integrity_page.IMPORT_NEWS_START_DATE_KEY] == target_start
    assert session_state[data_integrity_page.IMPORT_NEWS_END_DATE_KEY] == target_end


def test_render_import_news_panel_preserves_dates_after_launch_when_widgets_are_recreated(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    preview_calls: list[tuple[str, object, object]] = []
    started_runs: list[pipeline.PipelineLaunchOptions] = []
    rerun_calls: list[bool] = []
    current_clicked = {"key": "run_sentiment_standard_scoring"}

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: rerun_calls.append(True))
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if not started_runs and "date de début" in lowered_label:
            session_state[key] = dt_date(2020, 1, 1).isoformat()
        elif not started_runs and "date de fin" in lowered_label:
            session_state[key] = dt_date(2020, 1, 31).isoformat()
        elif key not in session_state:
            session_state[key] = str(kwargs.get("value", "") or "")
        return session_state[key]

    def _fake_button(_label, *args, **kwargs):
        return str(kwargs.get("key") or "") == current_clicked["key"]

    def _fake_start_pipeline_run(_step_key, _step_label, options, *, db_config=None, **kwargs):
        started_runs.append(options)
        return type("_Record", (), {"run_id": "run-standard"})()

    def _fake_build_pipeline_command(step_key, options):
        preview_calls.append((step_key, options.news_import_start_date, options.news_import_end_date))
        return ["python", step_key, str(options.news_import_start_date), str(options.news_import_end_date)]

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page.st, "button", _fake_button)
    monkeypatch.setattr(data_integrity_page, "start_pipeline_run", _fake_start_pipeline_run)
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", _fake_build_pipeline_command)
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert len(started_runs) == 1
    assert started_runs[0].news_import_start_date == "2020-01-01"
    assert started_runs[0].news_import_end_date == "2020-01-31"

    for key in (
        data_integrity_page.IMPORT_NEWS_START_DATE_WIDGET_KEY,
        data_integrity_page.IMPORT_NEWS_END_DATE_WIDGET_KEY,
        data_integrity_page._date_last_synced_key(data_integrity_page.IMPORT_NEWS_START_DATE_WIDGET_KEY),
        data_integrity_page._date_last_synced_key(data_integrity_page.IMPORT_NEWS_END_DATE_WIDGET_KEY),
    ):
        session_state.pop(key, None)
    current_clicked["key"] = ""

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert rerun_calls == [True]
    assert [start for _key, start, _end in preview_calls[-5:]] == ["2020-01-01"] * 5
    assert [end for _key, _start, end in preview_calls[-5:]] == ["2020-01-31"] * 5


@pytest.mark.parametrize(
    ("clicked_button_key", "expected_step_key"),
    [
        ("run_import_news", "import_news"),
        ("run_sentiment_relevance_backfill", "sentiment_relevance_backfill"),
        ("run_sentiment_standard_scoring", "sentiment_standard_scoring"),
        ("run_rebuild_daily_sentiment_features_only", "rebuild_daily_sentiment_features_only"),
        ("run_sentiment_contextual_scoring", "sentiment_contextual_scoring"),
    ],
)
def test_render_import_news_panel_launches_each_manual_7bis_button(
    monkeypatch,
    clicked_button_key: str,
    expected_step_key: str,
) -> None:
    session_state = _WidgetBoundSessionState()
    started_runs: list[tuple[str, str, pipeline.PipelineLaunchOptions, dict[str, str | None]]] = []
    success_messages: list[str] = []
    rerun_calls: list[bool] = []

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda message, *args, **kwargs: success_messages.append(str(message)))
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: rerun_calls.append(True))
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    target_start = dt_date(2022, 1, 1)
    target_end = dt_date(2022, 1, 31)

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = target_start.isoformat()
        elif "date de fin" in lowered_label:
            value = target_end.isoformat()
        else:
            value = ""
        if key:
            session_state.bind_widget_value(key, value)
        return value

    def _fake_button(_label, *args, **kwargs):
        return str(kwargs.get("key") or "") == clicked_button_key

    def _fake_start_pipeline_run(step_key, step_label, options, *, db_config=None, **kwargs):
        started_runs.append((step_key, step_label, options, dict(db_config or {})))
        return type("_Record", (), {"run_id": f"run-{step_key}"})()

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page.st, "button", _fake_button)
    monkeypatch.setattr(data_integrity_page, "start_pipeline_run", _fake_start_pipeline_run)
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", lambda step_key, options: [step_key, str(options.news_import_start_date), str(options.news_import_end_date)])
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {"host": "localhost", "name": "alpha_trade", "user": "u", "password": "p"},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert len(started_runs) == 1
    step_key, step_label, options, db_config = started_runs[0]
    assert step_key == expected_step_key
    assert step_label.startswith("News-Sentiement Traitement par étape")
    assert options.news_import_start_date == "2022-01-01"
    assert options.news_import_end_date == "2022-01-31"
    assert options.news_import_symbol_source == "stock_scores_all"
    assert options.news_import_resume_from_checkpoint is True
    assert db_config == {"host": "localhost", "name": "alpha_trade", "user": "u", "password": "p"}
    assert session_state[data_integrity_page.PENDING_SELECTED_RUN_KEY] == f"run-{expected_step_key}"
    assert session_state[data_integrity_page.PENDING_COMPARE_RUNS_KEY] == [f"run-{expected_step_key}"]
    assert any(f"run-{expected_step_key}" in message for message in success_messages)
    assert rerun_calls == [True]


def test_render_import_news_panel_shows_only_one_latest_run_summary(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    captions: list[str] = []
    rendered_results: list[dict[str, object] | None] = []

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "expander", lambda *args, **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda value, *args, **kwargs: captions.append(str(value)))
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda result: rendered_results.append(result))
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        data_integrity_page,
        "_resolve_import_news_scope_preview",
        lambda *args, **kwargs: {"effective_source": "stock_scores_all", "symbol_count": 3, "sample_symbols": ["AAPL"]},
    )

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = dt_date(2022, 1, 1).isoformat()
        elif "date de fin" in lowered_label:
            value = dt_date(2022, 1, 31).isoformat()
        else:
            value = ""
        if key:
            session_state[key] = value
        return value

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", lambda step_key, options: [step_key])
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={
            "import_news": {
                "run_id": "run-import",
                "status": "completed",
                "executed_at": "2026-05-17T09:00:00",
                "finished_at": "2026-05-17T09:10:00",
            },
            "sentiment_standard_scoring": {
                "run_id": "run-standard",
                "status": "completed",
                "executed_at": "2026-05-17T10:00:00",
                "finished_at": "2026-05-17T10:15:00",
            },
        },
    )

    assert [caption for caption in captions if caption.startswith("Dernier run")] == [
        "Dernier run — Sous-étape 3 — Scoring FinBERT standard (sans features)"
    ]
    assert rendered_results == [
        {
            "run_id": "run-standard",
            "status": "completed",
            "executed_at": "2026-05-17T10:00:00",
            "finished_at": "2026-05-17T10:15:00",
        }
    ]


def test_render_import_news_panel_uses_pipeline_style_expander(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    expander_labels: list[str] = []

    monkeypatch.setattr(data_integrity_page.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(
        data_integrity_page.st,
        "expander",
        lambda label, *args, **kwargs: expander_labels.append(str(label)) or _DummyContainer(),
    )
    monkeypatch.setattr(data_integrity_page.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(data_integrity_page.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(data_integrity_page.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "success", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page.st, "rerun", lambda: None)
    monkeypatch.setattr(data_integrity_page.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(data_integrity_page, "_render_step_result", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_render_backfill_completeness_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(data_integrity_page, "_resolve_import_news_scope_preview", lambda *args, **kwargs: None)

    def _fake_text_input(label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        lowered_label = str(label).lower()
        if "date de début" in lowered_label:
            value = dt_date(2022, 1, 1).isoformat()
        elif "date de fin" in lowered_label:
            value = dt_date(2022, 1, 31).isoformat()
        else:
            value = ""
        if key:
            session_state[key] = value
        return value

    monkeypatch.setattr(data_integrity_page.st, "text_input", _fake_text_input)
    monkeypatch.setattr(data_integrity_page.st, "selectbox", lambda *args, **kwargs: "stock_scores_all")
    monkeypatch.setattr(data_integrity_page.st, "number_input", lambda *args, **kwargs: 0)
    monkeypatch.setattr(data_integrity_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(data_integrity_page, "build_pipeline_command", lambda step_key, options: [step_key])
    monkeypatch.setattr(data_integrity_page, "format_command_for_display", lambda command: " ".join(command))

    data_integrity_page._render_import_news_panel(
        pipeline.PipelineLaunchOptions(),
        {},
        workflow_active=False,
        active_by_step={},
        all_runs=[],
        latest_by_step={},
    )

    assert expander_labels[0] == "**News-Sentiement Traitement par étape**"


def test_render_ml_train_scope_block_launches_selected_symbol_source(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    launch_calls: list[tuple[str, str, pipeline.PipelineLaunchOptions]] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])

    def _fake_selectbox(_label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        session_state[key] = "stock_scores_all"
        return "stock_scores_all"

    monkeypatch.setattr(pipeline.st, "selectbox", _fake_selectbox)
    monkeypatch.setattr(
        pipeline,
        "_resolve_ml_train_scope_preview",
        lambda *args, **kwargs: {
            "raw_symbol_count": 12,
            "symbol_count": 7,
            "sample_symbols": ["AAPL", "MSFT"],
            "selector_summary": {"enabled": True, "applied": True, "input_symbol_count": 12, "output_symbol_count": 7},
        },
    )
    monkeypatch.setattr(
        pipeline.st,
        "button",
        lambda _label, *args, **kwargs: str(kwargs.get("key") or "") == "run_pipeline_step_ml_train_scoped",
    )
    monkeypatch.setattr(
        pipeline,
        "_launch_pipeline_step",
        lambda step_key, step_label, options, db_config, all_runs: launch_calls.append((step_key, step_label, options)),
    )

    pipeline._render_ml_train_scope_block(
        pipeline.PipelineLaunchOptions(
            ml_selector_universe_signal_modes=("strict",),
            ml_selector_universe_max_candidate_rank=25,
            ml_selector_universe_exclude_earnings_blackout=True,
        ),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert len(launch_calls) == 1
    step_key, step_label, options = launch_calls[0]
    assert step_key == "ml_train"
    assert "Union stock_scores + stock_scores_history" in step_label
    assert options.ml_train_symbol_source == "stock_scores_all"


def test_render_ml_train_scope_block_displays_historical_window_caption(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    captions: list[str] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "caption", lambda value, *args, **kwargs: captions.append(str(value)))
    monkeypatch.setattr(pipeline.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(pipeline.st, "selectbox", lambda _label, *args, **kwargs: "candidates")
    monkeypatch.setattr(
        pipeline,
        "_resolve_ml_train_scope_preview",
        lambda *args, **kwargs: {
            "raw_symbol_count": 2,
            "symbol_count": 2,
            "sample_symbols": ["AAPL", "MSFT"],
            "selector_summary": {"enabled": False, "applied": False, "input_symbol_count": 2, "output_symbol_count": 2},
        },
    )
    monkeypatch.setattr(pipeline.st, "button", lambda *args, **kwargs: False)

    pipeline._render_ml_train_scope_block(
        pipeline.PipelineLaunchOptions(
            ml_training_start_date="2022-01-01",
            ml_training_end_date="2022-01-31",
        ),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert any("Fenêtre historique appliquée : `2022-01-01` → `2022-01-31`." in value for value in captions)


def test_render_ml_train_scope_block_uses_latest_widget_session_state_for_preview_and_launch(monkeypatch) -> None:
    session_state: dict[str, object] = {
        "pipeline_ml_train_symbol_source": "stock_scores_all",
    }
    launch_calls: list[tuple[str, str, pipeline.PipelineLaunchOptions]] = []
    codes: list[str] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(pipeline.st, "code", lambda value, *args, **kwargs: codes.append(str(value)))
    monkeypatch.setattr(
        pipeline.st,
        "selectbox",
        lambda _label, *args, **kwargs: "candidates",
    )
    monkeypatch.setattr(
        pipeline,
        "_resolve_ml_train_scope_preview",
        lambda *args, **kwargs: {
            "raw_symbol_count": 12,
            "symbol_count": 7,
            "sample_symbols": ["AAPL", "MSFT"],
            "selector_summary": {"enabled": False, "applied": False, "input_symbol_count": 12, "output_symbol_count": 7},
        },
    )
    monkeypatch.setattr(
        pipeline,
        "build_pipeline_command",
        lambda step_key, options: [step_key, str(options.ml_train_symbol_source)],
    )
    monkeypatch.setattr(pipeline, "format_command_for_display", lambda command: " ".join(command))
    monkeypatch.setattr(
        pipeline.st,
        "button",
        lambda _label, *args, **kwargs: str(kwargs.get("key") or "") == "run_pipeline_step_ml_train_scoped",
    )
    monkeypatch.setattr(
        pipeline,
        "_launch_pipeline_step",
        lambda step_key, step_label, options, db_config, all_runs: launch_calls.append((step_key, step_label, options)),
    )

    pipeline._render_ml_train_scope_block(
        pipeline.PipelineLaunchOptions(),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert any("ml_train stock_scores_all" in value for value in codes)
    assert len(launch_calls) == 1
    step_key, step_label, options = launch_calls[0]
    assert step_key == "ml_train"
    assert "Union stock_scores + stock_scores_history" in step_label
    assert options.ml_train_symbol_source == "stock_scores_all"


def test_render_ml_predict_scope_block_launches_selected_symbol_source_with_historical_range(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    launch_calls: list[tuple[str, str, pipeline.PipelineLaunchOptions]] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])

    def _fake_selectbox(_label, *args, **kwargs):
        key = str(kwargs.get("key") or "")
        session_state[key] = "stock_scores_history"
        return "stock_scores_history"

    monkeypatch.setattr(pipeline.st, "selectbox", _fake_selectbox)
    monkeypatch.setattr(
        pipeline,
        "_resolve_ml_train_scope_preview",
        lambda *args, **kwargs: {
            "raw_symbol_count": 8,
            "symbol_count": 5,
            "sample_symbols": ["AAPL", "MSFT"],
            "selector_summary": {"enabled": False, "applied": False, "input_symbol_count": 8, "output_symbol_count": 5},
        },
    )
    monkeypatch.setattr(
        pipeline.st,
        "button",
        lambda _label, *args, **kwargs: str(kwargs.get("key") or "") == "run_pipeline_step_ml_predict_scoped",
    )
    monkeypatch.setattr(
        pipeline,
        "_launch_pipeline_step",
        lambda step_key, step_label, options, db_config, all_runs: launch_calls.append((step_key, step_label, options)),
    )

    pipeline._render_ml_predict_scope_block(
        pipeline.PipelineLaunchOptions(
            ml_training_start_date="2022-01-01",
            ml_training_end_date="2022-01-31",
        ),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert len(launch_calls) == 1
    step_key, step_label, options = launch_calls[0]
    assert step_key == "ml_predict"
    assert "Historique PIT stock_scores_history" in step_label
    assert options.ml_predict_symbol_source == "stock_scores_history"
    assert options.ml_predict_use_historical_range is True


def test_render_ml_predict_scope_block_uses_latest_widget_session_state_for_preview_and_launch(monkeypatch) -> None:
    session_state: dict[str, object] = {
        "pipeline_ml_predict_symbol_source": "stock_scores_history",
    }
    launch_calls: list[tuple[str, str, pipeline.PipelineLaunchOptions]] = []
    codes: list[str] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(pipeline.st, "code", lambda value, *args, **kwargs: codes.append(str(value)))
    monkeypatch.setattr(
        pipeline.st,
        "selectbox",
        lambda _label, *args, **kwargs: "candidates",
    )
    monkeypatch.setattr(
        pipeline,
        "_resolve_ml_train_scope_preview",
        lambda *args, **kwargs: {
            "raw_symbol_count": 8,
            "symbol_count": 5,
            "sample_symbols": ["AAPL", "MSFT"],
            "selector_summary": {"enabled": False, "applied": False, "input_symbol_count": 8, "output_symbol_count": 5},
        },
    )
    monkeypatch.setattr(
        pipeline,
        "build_pipeline_command",
        lambda step_key, options: [step_key, str(options.ml_predict_symbol_source), str(options.ml_predict_use_historical_range)],
    )
    monkeypatch.setattr(pipeline, "format_command_for_display", lambda command: " ".join(command))
    monkeypatch.setattr(
        pipeline.st,
        "button",
        lambda _label, *args, **kwargs: str(kwargs.get("key") or "") == "run_pipeline_step_ml_predict_scoped",
    )
    monkeypatch.setattr(
        pipeline,
        "_launch_pipeline_step",
        lambda step_key, step_label, options, db_config, all_runs: launch_calls.append((step_key, step_label, options)),
    )

    pipeline._render_ml_predict_scope_block(
        pipeline.PipelineLaunchOptions(
            ml_training_start_date="2022-01-01",
            ml_training_end_date="2022-01-31",
        ),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert any("ml_predict stock_scores_history True" in value for value in codes)
    assert len(launch_calls) == 1
    step_key, step_label, options = launch_calls[0]
    assert step_key == "ml_predict"
    assert "Historique PIT stock_scores_history" in step_label
    assert options.ml_predict_symbol_source == "stock_scores_history"
    assert options.ml_predict_use_historical_range is True


def test_render_ml_predict_scope_block_displays_manual_command_preview(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    codes: list[str] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(pipeline.st, "code", lambda value, *args, **kwargs: codes.append(str(value)))
    monkeypatch.setattr(pipeline.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        pipeline.st,
        "selectbox",
        lambda _label, *args, **kwargs: "stock_scores_history",
    )
    monkeypatch.setattr(
        pipeline,
        "_resolve_ml_train_scope_preview",
        lambda *args, **kwargs: {
            "raw_symbol_count": 8,
            "symbol_count": 5,
            "sample_symbols": ["AAPL", "MSFT"],
            "selector_summary": {"enabled": False, "applied": False, "input_symbol_count": 8, "output_symbol_count": 5},
        },
    )
    monkeypatch.setattr(
        pipeline,
        "build_pipeline_command",
        lambda step_key, options: [
            step_key,
            str(options.ml_predict_symbol_source),
            str(options.ml_predict_use_historical_range),
            str(options.ml_training_start_date),
            str(options.ml_training_end_date),
        ],
    )
    monkeypatch.setattr(pipeline, "format_command_for_display", lambda command: " ".join(command))

    pipeline._render_ml_predict_scope_block(
        pipeline.PipelineLaunchOptions(
            ml_training_start_date="2022-01-01",
            ml_training_end_date="2022-01-31",
        ),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert any("ml_predict stock_scores_history True 2022-01-01 2022-01-31" in value for value in codes)


def test_render_period_sync_block_launches_quotes_history_with_selected_window(monkeypatch) -> None:
    session_state: dict[str, object] = {
        pipeline.QUOTE_HISTORY_START_DATE_KEY: dt_date(2026, 4, 1),
        pipeline.QUOTE_HISTORY_END_DATE_KEY: dt_date(2026, 4, 30),
        pipeline.QUOTE_HISTORY_SYMBOL_SOURCE_KEY: "candidates",
        pipeline.QUOTE_HISTORY_START_SYMBOL_KEY: "AAG",
    }
    launch_calls: list[tuple[str, str, pipeline.PipelineLaunchOptions]] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(pipeline.st, "selectbox", lambda _label, *args, **kwargs: session_state[str(kwargs.get("key"))])
    monkeypatch.setattr(pipeline.st, "text_input", lambda _label, *args, **kwargs: session_state[str(kwargs.get("key"))])
    monkeypatch.setattr(pipeline.st, "date_input", lambda _label, *args, **kwargs: session_state[str(kwargs.get("key"))])
    monkeypatch.setattr(
        pipeline.st,
        "button",
        lambda _label, *args, **kwargs: str(kwargs.get("key") or "") == "sync_latest_quotes_historical_period_launch",
    )
    monkeypatch.setattr(
        pipeline,
        "_resolve_data_integrity_scope_preview",
        lambda *args, **kwargs: {"symbol_count": 2, "sample_symbols": ["AAPL", "MSFT"]},
    )
    monkeypatch.setattr(
        pipeline,
        "build_pipeline_command",
        lambda step_key, options: [
            step_key,
            str(options.data_integrity_quotes_symbol_source),
            str(options.data_integrity_quotes_from_date),
            str(options.data_integrity_quotes_to_date),
            str(options.data_integrity_quotes_start_symbol),
        ],
    )
    monkeypatch.setattr(pipeline, "format_command_for_display", lambda command: " ".join(command))
    monkeypatch.setattr(
        pipeline,
        "_launch_pipeline_step",
        lambda step_key, step_label, options, db_config, all_runs: launch_calls.append((step_key, step_label, options)),
    )

    pipeline._render_period_sync_block(
        "sync_latest_quotes",
        pipeline.PipelineLaunchOptions(),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert len(launch_calls) == 1
    step_key, step_label, options = launch_calls[0]
    assert step_key == "sync_latest_quotes"
    assert "2026-04-01 → 2026-04-30" in step_label
    assert "Candidats du jour" in step_label
    assert "depuis AAG" in step_label
    assert options.data_integrity_quotes_symbol_source == "candidates"
    assert options.data_integrity_quotes_from_date == "2026-04-01"
    assert options.data_integrity_quotes_to_date == "2026-04-30"
    assert options.data_integrity_quotes_start_symbol == "AAG"


def test_render_period_sync_block_requires_confirmation_for_large_quotes_history_run(monkeypatch) -> None:
    session_state: dict[str, object] = {
        pipeline.QUOTE_HISTORY_START_DATE_KEY: dt_date(2026, 1, 1),
        pipeline.QUOTE_HISTORY_END_DATE_KEY: dt_date(2026, 3, 31),
        pipeline.QUOTE_HISTORY_SYMBOL_SOURCE_KEY: "stock_bars_daily",
        pipeline.QUOTE_HISTORY_START_SYMBOL_KEY: "A",
        pipeline.QUOTE_HISTORY_CONFIRM_LARGE_RUN_KEY: False,
    }
    warnings: list[str] = []
    button_disabled_values: list[bool] = []
    launch_calls: list[tuple[str, str, pipeline.PipelineLaunchOptions]] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "error", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "warning", lambda value, *args, **kwargs: warnings.append(str(value)))
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(pipeline.st, "selectbox", lambda _label, *args, **kwargs: session_state[str(kwargs.get("key"))])
    monkeypatch.setattr(pipeline.st, "text_input", lambda _label, *args, **kwargs: session_state[str(kwargs.get("key"))])
    monkeypatch.setattr(pipeline.st, "date_input", lambda _label, *args, **kwargs: session_state[str(kwargs.get("key"))])
    monkeypatch.setattr(pipeline.st, "checkbox", lambda *args, **kwargs: False)

    def _button(_label, *args, **kwargs):
        button_disabled_values.append(bool(kwargs.get("disabled")))
        return False

    monkeypatch.setattr(pipeline.st, "button", _button)
    monkeypatch.setattr(
        pipeline,
        "_resolve_data_integrity_scope_preview",
        lambda *args, **kwargs: {"symbol_count": 250, "sample_symbols": ["AAPL", "MSFT", "NVDA"]},
    )
    monkeypatch.setattr(
        pipeline,
        "build_pipeline_command",
        lambda step_key, options: [step_key, str(options.data_integrity_quotes_from_date), str(options.data_integrity_quotes_to_date)],
    )
    monkeypatch.setattr(pipeline, "format_command_for_display", lambda command: " ".join(command))
    monkeypatch.setattr(
        pipeline,
        "_launch_pipeline_step",
        lambda step_key, step_label, options, db_config, all_runs: launch_calls.append((step_key, step_label, options)),
    )

    pipeline._render_period_sync_block(
        "sync_latest_quotes",
        pipeline.PipelineLaunchOptions(data_integrity_quotes_batch_size=50),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert launch_calls == []
    assert button_disabled_values and button_disabled_values[-1] is True
    assert any("Run quotes historique volumineux détecté" in message for message in warnings)


def test_render_period_sync_block_blocks_invalid_earnings_window(monkeypatch) -> None:
    session_state: dict[str, object] = {
        pipeline.EARNINGS_HISTORY_START_DATE_KEY: dt_date(2026, 5, 10),
        pipeline.EARNINGS_HISTORY_END_DATE_KEY: dt_date(2026, 5, 1),
        pipeline.EARNINGS_HISTORY_SYMBOL_SOURCE_KEY: "stock_scores_history",
    }
    errors: list[str] = []
    launch_calls: list[tuple[str, str, pipeline.PipelineLaunchOptions]] = []

    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline.st, "divider", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "error", lambda value, *args, **kwargs: errors.append(str(value)))
    monkeypatch.setattr(pipeline.st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline.st, "columns", lambda n, **kwargs: [_DummyColumn() for _ in range(n)])
    monkeypatch.setattr(pipeline.st, "selectbox", lambda _label, *args, **kwargs: session_state[str(kwargs.get("key"))])
    monkeypatch.setattr(pipeline.st, "date_input", lambda _label, *args, **kwargs: session_state[str(kwargs.get("key"))])
    monkeypatch.setattr(pipeline.st, "button", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        pipeline,
        "_resolve_data_integrity_scope_preview",
        lambda *args, **kwargs: {"symbol_count": 3, "sample_symbols": ["AAPL", "MSFT", "NVDA"]},
    )
    monkeypatch.setattr(pipeline, "build_pipeline_command", lambda step_key, options: [step_key])
    monkeypatch.setattr(pipeline, "format_command_for_display", lambda command: " ".join(command))
    monkeypatch.setattr(
        pipeline,
        "_launch_pipeline_step",
        lambda step_key, step_label, options, db_config, all_runs: launch_calls.append((step_key, step_label, options)),
    )

    pipeline._render_period_sync_block(
        "sync_earnings_calendar",
        pipeline.PipelineLaunchOptions(),
        workflow_active=False,
        active_for_step=[],
        db_config={},
        all_runs=[],
    )

    assert launch_calls == []
    assert any("Fenêtre invalide" in message for message in errors)


def test_render_watcher_handoff_panel_uses_pipeline_style_expander(monkeypatch) -> None:
    expander_labels: list[str] = []

    class _ButtonColumn(_DummyColumn):
        def button(self, *args, **kwargs):
            return False

    monkeypatch.setattr(
        watcher_block.st,
        "expander",
        lambda label, *args, **kwargs: expander_labels.append(str(label)) or _DummyContainer(),
    )
    monkeypatch.setattr(watcher_block.st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(watcher_block.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(watcher_block.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(watcher_block.st, "dataframe", lambda *args, **kwargs: None)
    monkeypatch.setattr(watcher_block.st, "columns", lambda n, **kwargs: [_ButtonColumn() for _ in range(n)])
    monkeypatch.setattr(watcher_block.st, "checkbox", lambda *args, **kwargs: False)
    monkeypatch.setattr(watcher_block, "render_watcher_documentation_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(watcher_block, "_build_watcher_handoff_rows", lambda *args, **kwargs: [])
    monkeypatch.setattr(watcher_block, "get_runtime_db_config", lambda: {})
    monkeypatch.setattr(watcher_block, "serialize_local_watcher_control_state", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher_block, "list_alpaca_account_ids", lambda: [])

    pipeline._render_watcher_handoff_panel(pipeline.PipelineLaunchOptions())

    assert expander_labels == ["**12.bis — Watcher post-exécution (hors workflow 1 → 14)**"]


def test_pipeline_page_no_longer_exposes_legacy_strict_preset_preferences() -> None:
    assert not hasattr(pipeline, "_sync_alpha_scanner_strict_preset_preference")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_WIDGET_KEY")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_LAST_ACCOUNT_KEY")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_PREFS_KEY")


def test_build_history_rows_uses_public_run_summary_caption_helper() -> None:
    history_df = pipeline._build_history_rows(
        [
            {
                "run_id": "wf-1",
                "run_kind": "workflow",
                "step_key": "pipeline_workflow",
                "step_label": "Workflow complet",
                "status": "completed",
                "workflow_completed_steps": 2,
                "workflow_total_steps": 3,
                "duration_seconds": 12,
                "stdout_lines": 4,
                "stderr_lines": 0,
                "run_summary": {
                    "workflow_steps_with_summary": 2,
                    "targeted_symbols": 6,
                    "successful_symbols": 5,
                },
            }
        ]
    )

    row = history_df.iloc[0].to_dict()
    assert row["type"] == "workflow"
    assert row["progression"] == "2/3"
    assert "étapes résumées=2" in str(row["résumé métier"])


def test_resolve_history_selected_run_id_returns_run_id_from_dataframe_selection(monkeypatch) -> None:
    history_df = pipeline._build_history_rows(
        [
            {
                "run_id": "wf-1",
                "run_kind": "workflow",
                "step_key": "pipeline_workflow",
                "step_label": "Workflow complet",
                "status": "completed",
            },
            {
                "run_id": "step-2",
                "run_kind": "step",
                "step_key": "risk_management",
                "step_label": "11. Risk",
                "status": "failed",
            },
        ]
    )
    monkeypatch.setattr(
        workflow_page.st,
        "session_state",
        {
            workflow_page.WORKFLOW_HISTORY_TABLE_KEY: {
                "selection": {"rows": [1]},
            }
        },
        raising=False,
    )

    assert workflow_page._resolve_history_selected_run_id(history_df) == "step-2"


def test_resolve_history_selected_run_id_returns_none_without_valid_selection(monkeypatch) -> None:
    history_df = pipeline._build_history_rows(
        [
            {
                "run_id": "wf-1",
                "run_kind": "workflow",
                "step_key": "pipeline_workflow",
                "step_label": "Workflow complet",
                "status": "completed",
            }
        ]
    )
    monkeypatch.setattr(
        workflow_page.st,
        "session_state",
        {workflow_page.WORKFLOW_HISTORY_TABLE_KEY: {"selection": {"rows": [5]}}},
        raising=False,
    )

    assert workflow_page._resolve_history_selected_run_id(history_df) is None


def test_alpha_scanner_dependency_block_reason_requires_both_dependencies_red() -> None:
    diagnostic = {
        "all_red": True,
        "dependencies": {
            "sync_latest_quotes": {"status": "red"},
            "sync_earnings_calendar": {"status": "red"},
        },
    }

    reason = pipeline._alpha_scanner_dependency_block_reason(diagnostic)

    assert reason is not None
    assert "Alpha Scanner" in reason


def test_alpha_scanner_dependency_block_reason_is_none_when_not_all_red() -> None:
    diagnostic = {
        "all_red": False,
        "dependencies": {
            "sync_latest_quotes": {"status": "green"},
            "sync_earnings_calendar": {"status": "red"},
        },
    }

    assert pipeline._alpha_scanner_dependency_block_reason(diagnostic) is None


def test_pipeline_page_exposes_clear_screener_vs_alpha_scanner_labels() -> None:
    assert "diagnostic dépendances alpha scanner" in pipeline.ALPHA_SCANNER_DIAGNOSTIC_THRESHOLDS_TITLE.lower()
    assert "sélection finale stricte" in pipeline.ALPHA_SCANNER_PARAMS_TITLE.lower()
    assert "préfiltrage large" in pipeline.SCREENER_PARAMS_CAPTION.lower()


def test_build_execution_mode_banner_payload_marks_simulation_as_no_broker_orders() -> None:
    severity, message = pipeline._build_execution_mode_banner_payload(pipeline.PipelineLaunchOptions(execution_mode="simulate"))

    assert severity == "warning"
    assert "simulation" in message.lower()
    assert "aucun ordre" in message.lower()


def test_build_execution_mode_banner_payload_escalates_mode_mismatch() -> None:
    severity, message = pipeline._build_execution_mode_banner_payload(
        pipeline.PipelineLaunchOptions(account_id="acct-live", execution_mode="paper"),
        detected_broker_mode="live",
    )

    assert severity == "error"
    assert "incohérence" in message.lower()
    assert "acct-live" in message


def test_build_execution_account_banner_payload_marks_cash_as_green_swing_cash() -> None:
    severity, message = pipeline._build_execution_account_banner_payload(
        pipeline.PipelineLaunchOptions(execution_account_type="cash")
    )

    assert severity == "success"
    assert "type de compte=cash" in message.lower()
    assert "swing cash" in message.lower()


def test_build_execution_account_banner_payload_marks_margin_as_yellow() -> None:
    severity, message = pipeline._build_execution_account_banner_payload(
        pipeline.PipelineLaunchOptions(execution_account_type="margin")
    )

    assert severity == "warning"
    assert "margin" in message.lower()
    assert "type de compte=margin" in message.lower()


def test_build_execution_account_banner_payload_marks_detected_account_mismatch_as_red() -> None:
    severity, message = pipeline._build_execution_account_banner_payload(
        pipeline.PipelineLaunchOptions(execution_account_type="cash"),
        detected_account_type="margin",
    )

    assert severity == "error"
    assert "type broker détecté : `margin`" in message.lower()
    assert "incohérence critique" in message.lower()


def test_build_capital_preset_banner_payload_marks_detected_bucket_as_applied() -> None:
    payload = pipeline._build_capital_preset_banner_payload(
        "capital_0_5000",
        detected_preset_key="capital_0_5000",
        detected_equity=2_000.0,
    )

    assert payload is not None
    severity, message = payload
    assert severity == "success"
    assert "panier capital appliqué" in message.lower()
    assert "2 001 → 5 000 $" in message


def test_build_capital_preset_banner_payload_marks_custom_with_recommended_bucket() -> None:
    payload = pipeline._build_capital_preset_banner_payload(
        "custom",
        detected_preset_key="capital_50001_100000",
        detected_equity=52_000.0,
    )

    assert payload is not None
    severity, message = payload
    assert severity == "info"
    assert "personnalisé" in message.lower()
    assert "50 001 → 100 000 $" in message


def test_build_execution_protection_banner_payload_exposes_tp_and_auto_initial_stop() -> None:
    severity, message = pipeline._build_execution_protection_banner_payload(
        pipeline.PipelineLaunchOptions(
            execution_take_profit_pct=0.065,
            execution_trailing_stop_pct=0.04,
            execution_submission_window="pre_open",
            execution_trailing_trigger="multiple_r",
            execution_trailing_r_multiple=1.5,
        )
    )

    assert severity == "info"
    assert "+6.5 %" in message
    assert "1.50r" in message.lower()
    assert "-4.0 %" in message
    assert "pre_open" in message
    assert "stop initial" in message.lower()
    assert "calculé automatiquement" in message.lower()


def test_build_live_risk_guard_banner_payload_exposes_enabled_live_guards() -> None:
    severity, message = pipeline._build_live_risk_guard_banner_payload(
        pipeline.PipelineLaunchOptions(
            risk_max_portfolio_drawdown_pct=0.12,
            risk_max_daily_loss_pct=0.025,
            risk_target_annual_vol=0.13,
            risk_vol_target_lookback_days=45,
            risk_min_ml_coverage_ratio=0.80,
        )
    )

    assert severity == "success"
    assert "12.0 %" in message
    assert "2.5 %" in message
    assert "13.0 %" in message
    assert "45j" in message
    assert "80 %" in message
    assert "paramètres risk management" in message.lower()
    assert "kelly sizing & options avancées" in message.lower()


def test_build_live_risk_guard_banner_payload_marks_disabled_optional_guards() -> None:
    severity, message = pipeline._build_live_risk_guard_banner_payload(
        pipeline.PipelineLaunchOptions(
            risk_target_annual_vol=0.0,
            risk_min_ml_coverage_ratio=0.0,
        )
    )

    assert severity == "warning"
    assert "désactivé" in message.lower()


def test_build_pipeline_scope_alert_lines_distinguishes_global_and_account_specific_steps() -> None:
    global_line, account_line = pipeline._build_pipeline_scope_alert_lines()

    assert "3→10" in global_line
    assert "globales" in global_line.lower()
    assert "partagées entre comptes" in global_line.lower()
    assert "11→12" in account_line
    assert "spécifiques au compte sélectionné" in account_line.lower()


def test_build_watcher_doc_reference_exposes_explicit_workspace_link() -> None:
    assert hasattr(pipeline, "render_watcher_documentation_panel")


def test_build_watcher_handoff_rows_exposes_post_execution_launch_guidance() -> None:
    rows = pipeline._build_watcher_handoff_rows("acct-1")

    assert len(rows) >= 4
    assert rows[0]["Mode"] == "Run once (CLI local)"
    assert "juste après l'étape 12" in rows[0]["Quand l'utiliser"].lower()
    assert "run_execution_protection_watch.py" in rows[0]["Comment lancer"]
    assert any(row["Mode"] == "Task Scheduler" for row in rows)


def test_render_ml_inspection_link_uses_pending_symbol_for_cross_page_navigation(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    monkeypatch.setattr(pipeline.st, "session_state", session_state, raising=False)
    monkeypatch.setattr(pipeline, "list_ml_artifact_symbols", lambda: ["AAPL", "MSFT"])
    monkeypatch.setattr(pipeline.st, "selectbox", lambda *args, **kwargs: "MSFT")
    monkeypatch.setattr(pipeline.st, "button", lambda *args, **kwargs: True)
    monkeypatch.setattr(pipeline.st, "rerun", lambda: None)

    pipeline._render_ml_inspection_link("ml_train")

    assert session_state[pipeline.ML_PENDING_SELECTED_SYMBOL_KEY] == "MSFT"
    assert session_state[pipeline.NAVIGATION_TARGET_PAGE_KEY] == "ml"
    assert "ihm_ml_selected_symbol" not in session_state


def test_build_workflow_scope_help_lines_explains_1_to_12_3_to_12_and_13_14() -> None:
    lines = workflow_page._build_workflow_scope_help_lines()

    assert len(lines) == 3
    assert "1 → 12" in lines[0]
    assert "3 → 12" in lines[1]
    assert "changement de compte alpaca" in lines[1].lower()
    assert "13" in lines[2]
    assert "14" in lines[2]
    assert "non incluses par défaut" in lines[2].lower()


def test_build_run_provider_badge_prefers_run_summary_provider() -> None:
    badge = workflow_page._build_run_provider_badge(
        {
            "run_summary": {"provider": "eodhd"},
            "command": ["python", "-m", "dataIntegrityEngine.import_alpaca_bar"],
        }
    )

    assert badge == "provider=eodhd"


def test_build_run_symbol_progress_caption_formats_current_symbol_and_total() -> None:
    caption = workflow_page._build_run_symbol_progress_caption(
        {
            "run_summary": {
                "current_symbol_index": 125,
                "current_symbol_total": 500,
                "current_symbol": "NVDA",
            }
        }
    )

    assert caption is not None
    assert "125/500" in caption
    assert "NVDA" in caption


def test_build_run_symbol_progress_payload_returns_fraction_and_caption() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "run_summary": {
                "current_symbol_index": 25,
                "current_symbol_total": 100,
                "current_symbol": "AAPL",
            }
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert fraction == 0.25
    assert "25/100" in caption
    assert "AAPL" in caption


def test_build_run_symbol_progress_payload_uses_generic_summary_counters_for_data_sanitizer() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "step_key": "data_sanitizer_daily",
            "run_summary": {
                "targeted_symbols": 100,
                "successful_symbols": 70,
                "skipped_symbols": 5,
                "failed_symbols": 10,
            },
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert fraction == 0.85
    assert "85/100" in caption
    assert "sanitizeur" in caption.lower()


def test_build_run_symbol_progress_payload_falls_back_to_live_logs_when_summary_has_no_progress() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "step_key": "sync_earnings_calendar",
            "run_summary": {},
            "stdout_tail": (
                "2026-05-03 08:00:00 INFO Finnhub earnings calendar progress | "
                "processed=40/120 records=300 completed=38 failed=2 latest_symbol=NVDA\n"
            ),
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert round(fraction, 4) == round(40 / 120, 4)
    assert "40/120" in caption
    assert "NVDA" in caption


def test_build_run_symbol_progress_payload_parses_traitement_log_pattern() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "step_key": "data_sanitizer_daily",
            "stdout_tail": "2026-05-03 08:00:00 INFO Traitement 37/200: AAPL\n",
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert fraction == 0.185
    assert "37/200" in caption
    assert "AAPL" in caption


def test_build_run_symbol_progress_payload_prefers_explicit_live_progress_fields() -> None:
    payload = workflow_page._build_run_symbol_progress_payload(
        {
            "step_key": "stock_screener",
            "run_summary": {
                "progress_current": 3,
                "progress_total": 8,
                "progress_label": "🔎 Progression stock screener",
                "progress_item": "chunk #3",
            },
        }
    )

    assert payload is not None
    fraction, caption = payload
    assert fraction == 0.375
    assert "3/8" in caption
    assert "chunk #3" in caption


def test_should_render_active_run_live_progress_returns_false_for_workflow_child_when_parent_workflow_is_active() -> None:
    should_render = workflow_page._should_render_active_run_live_progress(
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "parent_run_id": "wf-1",
        },
        active_workflow_run_ids={"wf-1"},
    )

    assert should_render is False


def test_should_render_active_run_live_progress_returns_true_for_standalone_step() -> None:
    should_render = workflow_page._should_render_active_run_live_progress(
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "parent_run_id": None,
        },
        active_workflow_run_ids={"wf-1"},
    )

    assert should_render is True


def test_workflow_launcher_starts_with_1_to_12_and_optional_steps_disabled_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: kwargs["options"][0])
    monkeypatch.setattr(workflow_page.st, "checkbox", lambda *args, **kwargs: kwargs.get("value", False))
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: True)

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-1"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    assert captured["start_step"] == "1"
    assert captured["include_ml_train"] is True
    assert captured["include_corporate_actions_sync"] is False
    assert captured["include_corporate_actions_apply"] is False


def test_workflow_launcher_can_start_at_step_3_and_include_corporate_actions(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: "3")
    monkeypatch.setattr(workflow_page.st, "checkbox", lambda *args, **kwargs: True)
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: True)

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-2"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    assert captured["start_step"] == "3"
    assert captured["include_ml_train"] is True
    assert captured["include_corporate_actions_sync"] is True
    assert captured["include_corporate_actions_apply"] is True


def test_workflow_launcher_can_schedule_delayed_start(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: kwargs["options"][0])

    def _fake_checkbox(*args, **kwargs):
        key = kwargs.get("key")
        if key == workflow_page.WORKFLOW_DELAYED_START_ENABLED_KEY:
            return True
        return kwargs.get("value", False)

    monkeypatch.setattr(workflow_page.st, "checkbox", _fake_checkbox)
    monkeypatch.setattr(workflow_page.st, "time_input", lambda *args, **kwargs: dt_time(hour=2, minute=0))
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: kwargs.get("key") == "run_pipeline_workflow_all_steps")

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-delayed"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    scheduled_for = cast(datetime, captured["scheduled_for"])
    assert scheduled_for is not None
    assert scheduled_for.hour == 2
    assert scheduled_for.minute == 0


def test_build_scheduled_countdown_caption_displays_remaining_time() -> None:
    now = datetime(2026, 5, 7, 23, 0, 0)
    scheduled_for = now + timedelta(hours=3, minutes=15, seconds=4)

    caption = workflow_page._build_scheduled_countdown_caption(
        {
            "status": "scheduled",
            "scheduled_for": scheduled_for.isoformat(timespec="seconds"),
        },
        now=now,
    )

    assert caption is not None
    assert "2026-05-08 02:15:04" in caption
    assert "03:15:04" in caption
    assert "départ dans" in caption.lower()


def test_build_scheduled_countdown_caption_returns_none_for_non_scheduled_run() -> None:
    caption = workflow_page._build_scheduled_countdown_caption(
        {
            "status": "running",
            "scheduled_for": "2026-05-08T02:15:04",
        }
    )

    assert caption is None


def test_build_actual_start_caption_displays_actual_and_planned_times() -> None:
    caption = workflow_page._build_actual_start_caption(
        {
            "status": "running",
            "scheduled_for": "2026-05-08T02:00:00",
            "actual_started_at": "2026-05-08T02:00:07",
        }
    )

    assert caption is not None
    assert "démarrage réel" in caption.lower()
    assert "2026-05-08 02:00:07" in caption
    assert "2026-05-08 02:00:00" in caption
    assert "planifié pour" in caption.lower()


def test_build_actual_start_caption_returns_none_while_workflow_is_still_scheduled() -> None:
    caption = workflow_page._build_actual_start_caption(
        {
            "status": "scheduled",
            "scheduled_for": "2026-05-08T02:00:00",
            "actual_started_at": "2026-05-08T02:00:07",
        }
    )

    assert caption is None


def test_workflow_launcher_can_launch_explicit_selected_pipelines_in_order(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "markdown", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "divider", lambda: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "columns", lambda n: [_DummyContainer() for _ in range(n)])
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: kwargs["options"][0])

    def _fake_checkbox(*args, **kwargs):
        key = kwargs.get("key")
        if key == workflow_page.WORKFLOW_INCLUDE_ML_TRAIN_KEY:
            return kwargs.get("value", False)
        if key == workflow_page.WORKFLOW_INCLUDE_CA_SYNC_KEY:
            return False
        if key == workflow_page.WORKFLOW_INCLUDE_CA_APPLY_KEY:
            return False
        return key in {
            f"{workflow_page.WORKFLOW_CUSTOM_STEP_KEY_PREFIX}import_alpaca_bar",
            f"{workflow_page.WORKFLOW_CUSTOM_STEP_KEY_PREFIX}stock_screener",
            f"{workflow_page.WORKFLOW_CUSTOM_STEP_KEY_PREFIX}execution",
        }

    monkeypatch.setattr(workflow_page.st, "checkbox", _fake_checkbox)
    monkeypatch.setattr(
        workflow_page.st,
        "button",
        lambda *args, **kwargs: kwargs.get("key") == "run_pipeline_workflow_selected_steps",
    )

    def _fake_start_pipeline_workflow(options, **kwargs):
        captured.update(kwargs)
        return type("_Record", (), {"run_id": "wf-custom"})()

    monkeypatch.setattr(workflow_page, "start_pipeline_workflow", _fake_start_pipeline_workflow)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    assert captured["selected_step_keys"] == (
        "import_alpaca_bar",
        "stock_screener",
        "execution",
    )


def test_workflow_launcher_custom_selection_no_longer_displays_7bis_between_7_and_8(monkeypatch) -> None:
    checkbox_labels: list[str] = []

    monkeypatch.setattr(workflow_page, "_merge_runs", lambda: ([], []))
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)
    monkeypatch.setattr(workflow_page.st, "container", lambda **kwargs: _DummyContainer())
    monkeypatch.setattr(workflow_page.st, "subheader", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "caption", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "info", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "warning", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "progress", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "success", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "markdown", lambda value: None)
    monkeypatch.setattr(workflow_page.st, "divider", lambda: None)
    monkeypatch.setattr(workflow_page.st, "rerun", lambda: None)
    monkeypatch.setattr(workflow_page.st, "columns", lambda n: [_DummyContainer() for _ in range(n)])
    monkeypatch.setattr(workflow_page.st, "selectbox", lambda *args, **kwargs: kwargs["options"][0])

    def _fake_checkbox(label, *args, **kwargs):
        checkbox_labels.append(str(label))
        return kwargs.get("value", False)

    monkeypatch.setattr(workflow_page.st, "checkbox", _fake_checkbox)
    monkeypatch.setattr(workflow_page.st, "button", lambda *args, **kwargs: False)

    workflow_page._render_workflow_launcher(pipeline.PipelineLaunchOptions(), False, {})

    custom_labels = [label for label in checkbox_labels if label[:1].isdigit()]
    assert "7. Sentiment Pipeline" in custom_labels
    assert "8. Signal Aggregator" in custom_labels
    idx_7 = custom_labels.index("7. Sentiment Pipeline")
    idx_8 = custom_labels.index("8. Signal Aggregator")
    assert idx_7 < idx_8
    assert not any(label.startswith("7bis.") for label in custom_labels), custom_labels


def test_build_workflow_child_run_payload_returns_latest_runs_first_with_labels(monkeypatch) -> None:
    child_runs = {
        "run-step-1": {
            "step_label": "1. Import Bars",
            "status": "completed",
            "executed_at": "2026-05-02T20:12:59",
        },
        "run-step-2": {
            "step_label": "2. Sanitize",
            "status": "running",
            "executed_at": "2026-05-02T20:13:59",
        },
    }
    monkeypatch.setattr(workflow_page, "get_pipeline_run_record", lambda run_id: child_runs.get(run_id))

    child_ids, child_labels = workflow_page._build_workflow_child_run_payload(
        {
            "workflow_child_run_ids": ["run-step-1", "run-step-2", "run-step-2", "  ", None],
        }
    )

    assert child_ids == ["run-step-2", "run-step-1"]
    assert "2. Sanitize" in child_labels["run-step-2"]
    assert "🟨 En cours" in child_labels["run-step-2"]
    assert "1. Import Bars" in child_labels["run-step-1"]
    assert "🟢 Terminé" in child_labels["run-step-1"]


def test_prepare_workflow_child_run_state_auto_selects_current_run(monkeypatch) -> None:
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)

    child_select_key, follow_enabled, current_child_run_id, selected_child_run_id, last_auto_key = (
        workflow_page._prepare_workflow_child_run_state(
            {
                "run_id": "wf-1",
                "status": "running",
                "workflow_current_child_run_id": "run-step-2",
            },
            ["run-step-2", "run-step-1"],
            {
                "run-step-2": "2. Sanitize | run-step-2",
                "run-step-1": "1. Import Bars | run-step-1",
            },
        )
    )

    assert child_select_key == "workflow_child_run_select_wf-1"
    assert follow_enabled is True
    assert current_child_run_id == "run-step-2"
    assert selected_child_run_id == "run-step-2"
    assert last_auto_key == "workflow_child_run_last_auto_wf-1"
    assert workflow_page.st.session_state[child_select_key] == "run-step-2"


def test_prepare_workflow_child_run_state_preserves_manual_selection_when_follow_disabled(monkeypatch) -> None:
    session_state = {
        "workflow_child_run_autofollow_wf-2": False,
        "workflow_child_run_select_wf-2": "run-step-1",
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    child_select_key, follow_enabled, current_child_run_id, selected_child_run_id, _ = workflow_page._prepare_workflow_child_run_state(
        {
            "run_id": "wf-2",
            "status": "running",
            "workflow_current_child_run_id": "run-step-2",
        },
        ["run-step-2", "run-step-1"],
        {
            "run-step-2": "2. Sanitize | run-step-2",
            "run-step-1": "1. Import Bars | run-step-1",
        },
    )

    assert child_select_key == "workflow_child_run_select_wf-2"
    assert follow_enabled is False
    assert current_child_run_id == "run-step-2"
    assert selected_child_run_id == "run-step-1"
    assert workflow_page.st.session_state[child_select_key] == "run-step-1"


def test_prepare_workflow_child_run_state_disables_follow_when_manual_selection_differs_current(monkeypatch) -> None:
    session_state = {
        "workflow_child_run_autofollow_wf-3": True,
        "workflow_child_run_select_wf-3": "run-step-1",
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    child_select_key, follow_enabled, current_child_run_id, selected_child_run_id, _ = workflow_page._prepare_workflow_child_run_state(
        {
            "run_id": "wf-3",
            "status": "running",
            "workflow_current_child_run_id": "run-step-2",
        },
        ["run-step-2", "run-step-1"],
        {
            "run-step-2": "2. Sanitize | run-step-2",
            "run-step-1": "1. Import Bars | run-step-1",
        },
    )

    assert child_select_key == "workflow_child_run_select_wf-3"
    assert follow_enabled is False
    assert current_child_run_id == "run-step-2"
    assert selected_child_run_id == "run-step-1"
    assert workflow_page.st.session_state["workflow_child_run_autofollow_wf-3"] is False


def test_prepare_workflow_child_run_state_consumes_pending_reselect_to_current(monkeypatch) -> None:
    session_state = {
        "workflow_child_run_autofollow_wf-4": False,
        "workflow_child_run_select_wf-4": "run-step-1",
        "workflow_child_run_pending_select_wf-4": "run-step-2",
        "workflow_child_run_pending_autofollow_wf-4": True,
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    child_select_key, follow_enabled, current_child_run_id, selected_child_run_id, _ = workflow_page._prepare_workflow_child_run_state(
        {
            "run_id": "wf-4",
            "status": "running",
            "workflow_current_child_run_id": "run-step-2",
        },
        ["run-step-2", "run-step-1"],
        {
            "run-step-2": "2. Sanitize | run-step-2",
            "run-step-1": "1. Import Bars | run-step-1",
        },
    )

    assert child_select_key == "workflow_child_run_select_wf-4"
    assert follow_enabled is True
    assert current_child_run_id == "run-step-2"
    assert selected_child_run_id == "run-step-2"
    assert workflow_page.WORKFLOW_CHILD_PENDING_SELECT_KEY_PREFIX + "wf-4" not in workflow_page.st.session_state
    assert workflow_page.WORKFLOW_CHILD_PENDING_AUTOFOLLOW_KEY_PREFIX + "wf-4" not in workflow_page.st.session_state


def test_prime_runtime_center_state_prefers_active_workflow_parent_over_latest_child_run(monkeypatch) -> None:
    monkeypatch.setattr(workflow_page.st, "session_state", {}, raising=False)

    all_runs = [
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "status": "running",
            "parent_run_id": "wf-1",
        },
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "status": "running",
        },
    ]
    labels = {
        "run-step-1": "1. Import | run-step-1 | 🟨 En cours",
        "wf-1": "Workflow complet | wf-1 | 🟨 En cours",
    }

    compare_defaults = workflow_page._prime_runtime_center_state(all_runs, ["run-step-1", "wf-1"], labels)

    assert compare_defaults == []
    assert workflow_page.st.session_state[workflow_page.SELECTED_RUN_KEY] == "wf-1"
    assert workflow_page.st.session_state[workflow_page.WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY] == "wf-1"


def test_prime_runtime_center_state_promotes_auto_selected_child_run_back_to_active_workflow(monkeypatch) -> None:
    session_state = {
        workflow_page.SELECTED_RUN_KEY: "run-step-1",
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    all_runs = [
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "status": "completed",
            "parent_run_id": "wf-1",
        },
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "status": "running",
        },
    ]
    labels = {
        "run-step-1": "1. Import | run-step-1 | 🟢 Terminé",
        "wf-1": "Workflow complet | wf-1 | 🟨 En cours",
    }

    workflow_page._prime_runtime_center_state(all_runs, ["run-step-1", "wf-1"], labels)

    assert workflow_page.st.session_state[workflow_page.SELECTED_RUN_KEY] == "wf-1"
    assert workflow_page.st.session_state[workflow_page.WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY] == "wf-1"


def test_prime_runtime_center_state_preserves_manual_child_selection_during_active_workflow(monkeypatch) -> None:
    session_state = {
        workflow_page.SELECTED_RUN_KEY: "run-step-1",
        workflow_page.WORKFLOW_RUNTIME_AUTO_SELECTED_RUN_KEY: "wf-1",
    }
    monkeypatch.setattr(workflow_page.st, "session_state", session_state, raising=False)

    all_runs = [
        {
            "run_id": "run-step-1",
            "run_kind": "step",
            "status": "completed",
            "parent_run_id": "wf-1",
        },
        {
            "run_id": "wf-1",
            "run_kind": "workflow",
            "status": "running",
        },
    ]
    labels = {
        "run-step-1": "1. Import | run-step-1 | 🟢 Terminé",
        "wf-1": "Workflow complet | wf-1 | 🟨 En cours",
    }

    workflow_page._prime_runtime_center_state(all_runs, ["run-step-1", "wf-1"], labels)

    assert workflow_page.st.session_state[workflow_page.SELECTED_RUN_KEY] == "run-step-1"


