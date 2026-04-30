from __future__ import annotations

from ihm.components import run_summary as run_summary_component


def test_render_persistent_business_summary_returns_false_without_summary(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(run_summary_component.st, "subheader", lambda value: calls.append(("subheader", value)))
    monkeypatch.setattr(run_summary_component.st, "caption", lambda value: calls.append(("caption", value)))
    monkeypatch.setattr(run_summary_component, "metric_row", lambda metrics: calls.append(("metric_row", metrics)))

    rendered = run_summary_component.render_persistent_business_summary({"step_key": "execution"})

    assert rendered is False
    assert calls == []


def test_render_persistent_business_summary_renders_title_metrics_and_caption(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(run_summary_component.st, "subheader", lambda value: calls.append(("subheader", value)))
    monkeypatch.setattr(run_summary_component.st, "caption", lambda value: calls.append(("caption", value)))
    monkeypatch.setattr(run_summary_component, "metric_row", lambda metrics: calls.append(("metric_row", metrics)))

    rendered = run_summary_component.render_persistent_business_summary(
        {
            "step_key": "execution",
            "run_summary": {
                "targeted_symbols": 5,
                "submitted_orders": 4,
                "filled_orders": 3,
                "failed_orders": 1,
            },
        },
        title="🧭 Résumé métier persistant — Test",
        max_metrics=2,
    )

    assert rendered is True
    assert calls[0] == ("subheader", "🧭 Résumé métier persistant — Test")
    assert calls[1] == (
        "metric_row",
        [("Cibles", 5, None), ("Soumis", 4, None)],
    )
    assert calls[2] == ("caption", "cibles=5 | soumis=4 | remplis=3 | échecs=1")


def test_render_persistent_business_summary_prefers_existing_summary_caption(monkeypatch) -> None:
    captions: list[str] = []
    monkeypatch.setattr(run_summary_component.st, "subheader", lambda value: None)
    monkeypatch.setattr(run_summary_component.st, "caption", lambda value: captions.append(value))
    monkeypatch.setattr(run_summary_component, "metric_row", lambda metrics: None)

    run_summary_component.render_persistent_business_summary(
        {
            "step_key": "risk_management",
            "summary_caption": "caption déjà calculé",
            "run_summary": {"targeted_symbols": 2, "accepted_symbols": 1},
        }
    )

    assert captions == ["caption déjà calculé"]


def test_render_run_summary_block_supports_markdown_heading_without_caption(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(run_summary_component.st, "subheader", lambda value: calls.append(("subheader", value)))
    monkeypatch.setattr(run_summary_component.st, "markdown", lambda value: calls.append(("markdown", value)))
    monkeypatch.setattr(run_summary_component.st, "caption", lambda value: calls.append(("caption", value)))
    monkeypatch.setattr(run_summary_component, "metric_row", lambda metrics: calls.append(("metric_row", metrics)))

    rendered = run_summary_component.render_run_summary_block(
        {
            "step_key": "pipeline_workflow",
            "run_summary": {
                "workflow_steps_with_summary": 2,
                "targeted_symbols": 6,
                "successful_symbols": 5,
            },
        },
        title="**Résumé métier**",
        max_metrics=2,
        heading_level="markdown",
        show_caption=False,
    )

    assert rendered is True
    assert calls == [
        ("markdown", "**Résumé métier**"),
        ("metric_row", [("Étapes résumées", 2, None), ("Cibles", 6, None)]),
    ]


def test_render_run_summary_block_renders_earnings_resume_details(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(run_summary_component.st, "subheader", lambda value: calls.append(("subheader", value)))
    monkeypatch.setattr(run_summary_component.st, "markdown", lambda value: calls.append(("markdown", value)))
    monkeypatch.setattr(run_summary_component.st, "caption", lambda value: calls.append(("caption", value)))
    monkeypatch.setattr(run_summary_component, "metric_row", lambda metrics: calls.append(("metric_row", metrics)))

    rendered = run_summary_component.render_run_summary_block(
        {
            "step_key": "sync_earnings_calendar",
            "run_summary": {
                "symbols": 120,
                "symbols_skipped_resume": 45,
                "symbols_remaining": 7,
                "rows_upserted": 300,
                "batch_size": 50,
                "failed_symbols": 2,
                "bookmark_path": r"C:\artifacts\finnhub_cache\sync_earnings_calendar_bookmark.json",
            },
        },
        title="**Résumé métier**",
        max_metrics=6,
        heading_level="markdown",
        show_caption=False,
    )

    assert rendered is True
    assert calls == [
        ("markdown", "**Résumé métier**"),
        (
            "metric_row",
            [("Symboles", 120, None), ("Repris", 45, None), ("À rejouer", 7, None), ("Rows upsert", 300, None), ("Batch", 50, None), ("KO", 2, None)],
        ),
        ("caption", "Reprise bookmark : 45 symbole(s) déjà traité(s), 7 restant(s) à rejouer."),
        ("caption", r"Bookmark local : C:\artifacts\finnhub_cache\sync_earnings_calendar_bookmark.json"),
    ]


