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

