from ihm.pages import pipeline


def test_pages_pipeline_importable():
    assert hasattr(pipeline, "__doc__")


def test_pipeline_page_no_longer_exposes_legacy_strict_preset_preferences() -> None:
    assert not hasattr(pipeline, "_sync_alpha_scanner_strict_preset_preference")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_WIDGET_KEY")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_LAST_ACCOUNT_KEY")
    assert not hasattr(pipeline, "ALPHA_SCANNER_PRESET_PREFS_KEY")


def test_format_selector_dependency_indicator_reports_quotes_health() -> None:
    health = {
        "active_symbols": 100,
        "quotes": {"latest_date": "2026-04-22", "symbols_covered": 80, "coverage_ratio": 0.8, "coverage_pct": 80.0},
        "earnings": {"latest_date": "2026-05-15", "max_date": "2026-05-15", "symbols_covered": 40, "coverage_ratio": 0.4, "coverage_pct": 40.0},
    }

    label = pipeline._format_selector_dependency_indicator("sync_latest_quotes", health)

    assert label is not None
    assert "stock_quote_snapshots" in label
    assert "🟢" in label
    assert "latest_date=2026-04-22" in label
    assert "couverture=80.0%" in label
    assert "N symboles=80/100" in label


def test_build_alpha_scanner_dependency_warning_when_dependencies_are_incomplete() -> None:
    health = {
        "active_symbols": 100,
        "quotes": {"latest_date": None, "symbols_covered": 0, "coverage_ratio": 0.0, "coverage_pct": 0.0},
        "earnings": {"latest_date": None, "max_date": None, "symbols_covered": 0, "coverage_ratio": 0.0, "coverage_pct": 0.0},
    }

    warning = pipeline._build_alpha_scanner_dependency_warning(health)

    assert warning is not None
    severity, message = warning
    assert severity == "error"
    assert "Alpha Scanner" in message
    assert "spread_bps" in message
    assert "earnings_blackout" in message
    assert "critiques" in message


def test_build_selector_dependency_diagnostic_exposes_reason_and_fix_command() -> None:
    diagnostic = pipeline._build_selector_dependency_diagnostic(
        "quotes",
        {"latest_date": None, "symbols_covered": 0, "coverage_ratio": 0.0, "coverage_pct": 0.0},
        100,
    )

    assert diagnostic is not None
    assert diagnostic["status"] == "error"
    assert "stock_quote_snapshots" in str(diagnostic["reason"])
    assert str(diagnostic["command"]) == "python -m dataIntegrityEngine.sync_latest_quotes"
    assert str(diagnostic["step_key"]) == "sync_latest_quotes"
    assert "Lancer Sync Latest Quotes" in str(diagnostic["action_label"])


def test_build_alpha_scanner_dependency_diagnostics_lists_fix_commands() -> None:
    health = {
        "active_symbols": 100,
        "quotes": {"latest_date": None, "symbols_covered": 0, "coverage_ratio": 0.0, "coverage_pct": 0.0},
        "earnings": {"latest_date": None, "max_date": None, "symbols_covered": 0, "coverage_ratio": 0.0, "coverage_pct": 0.0},
    }

    diagnostics = pipeline._build_alpha_scanner_dependency_diagnostics(health)

    assert len(diagnostics) == 2
    commands = {str(item["command"]) for item in diagnostics}
    assert "python -m dataIntegrityEngine.sync_latest_quotes" in commands
    assert "python -m dataIntegrityEngine.sync_earnings_calendar" in commands


