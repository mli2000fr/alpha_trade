from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from ihm.services import batch_management as batches


def _spec(name: str = "daily_bars_sync", **overrides: object) -> batches.BatchSpec:
    values = {
        "name": name, "priority": "P0", "description": "Collecte test",
        "activation_requirement": "", "unlock_steps": (), "tables": ("table_a",),
        "enabled": True, "status": "ACTIVE", "provider": "provider", "timezone": "Europe/Paris",
        "run_hours": ("1", "13"), "run_minutes": ("5",), "run_days": ("1", "4"),
        "symbols_file": "config/univers.txt", "universe_scope": "", "log_file": "log/test.txt",
        "task_name": batches.task_name_for_batch(name), "raw_config": {},
    }
    values.update(overrides)
    return batches.BatchSpec(**values)


def test_load_catalogue_sorts_priorities_and_reads_metadata(tmp_path: Path) -> None:
    config = {
        "late": {
            "priority": "P4", "description": "Late", "tables": "x,y", "enabled": False,
            "activation_requirement": "Choose provider",
            "unlock_steps": ["Choose", "Implement", "Validate"],
        },
        "urgent": {"priority": "P0", "description": "Urgent", "tables": "z", "run_hours": "2"},
    }
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    specs = batches.load_batch_specs(str(path))
    assert [item.name for item in specs] == ["urgent", "late"]
    assert specs[0].tables == ("z",)
    assert specs[1].tables == ("x", "y")
    assert specs[1].activation_requirement == "Choose provider"
    assert specs[1].unlock_steps == ("Choose", "Implement", "Validate")
    assert not specs[1].runnable


def test_catalogue_exposes_research_notice(tmp_path: Path) -> None:
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump({
        "analyst": {"enabled": True, "research_notice": "Yahoo pour la recherche."}
    }), encoding="utf-8")
    spec = batches.load_batch_specs(str(path))[0]
    assert spec.research_notice == "Yahoo pour la recherche."


def test_retired_us_quality_batch_is_absent_from_ui_catalog():
    assert "pit_data_quality_daily" not in {
        spec.name for spec in batches.load_market_batch_specs("US_EQ")
    }


def test_retired_cn_staging_quality_is_absent_and_current_quality_is_preserved():
    names = {spec.name for spec in batches.load_market_batch_specs("CN_A")}
    assert "cn_staging_quality_daily" not in names
    assert "cn_baostock_smoke" not in names
    assert "cn_master_calendar_sync" not in names
    assert "cn_daily_quality_17c" in names


def test_retired_fr_quality_batch_is_absent_from_ui_catalog():
    assert "fr_pit_quality_daily" not in {
        spec.name for spec in batches.load_market_batch_specs("FR_EQ")
    }


def test_catalogue_exposes_quality_supervision_dependencies(tmp_path: Path) -> None:
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump({
        "quality": {
            "enabled": True,
            "supervision_dependencies": "sec,finra,fred",
            "execution_notice": "Lancer après les collecteurs.",
        }
    }), encoding="utf-8")
    spec = batches.load_batch_specs(str(path))[0]
    assert spec.supervision_dependencies == ("sec", "finra", "fred")
    assert spec.execution_notice == "Lancer après les collecteurs."


def test_schedule_and_task_names_cover_legacy_and_generic() -> None:
    assert batches.task_name_for_batch("earnings_calendar_sync") == "AlphaTrade-EarningsCalendarSync"
    assert batches.task_name_for_batch("daily_bars_sync") == "AlphaTrade-DailyBarsSync"
    assert batches.format_schedule(_spec()) == "lun, jeu · 01:05, 13:05 · Europe/Paris"


def test_schedule_displays_conditional_recovery_separately() -> None:
    spec = _spec(
        run_hours=("16",), run_minutes=("20",),
        raw_config={"recovery_run_hours": "22", "recovery_run_minutes": "20"},
    )
    assert batches.format_schedule(spec) == (
        "lun, jeu · 16:20 · Europe/Paris · secours conditionnel 22:20"
    )


def test_schedule_displays_first_weekday_of_month() -> None:
    spec = _spec(
        name="db_news_raw_backup",
        run_hours=("18",), run_minutes=("0",), run_days=("0",),
        raw_config={"first_weekday_of_month": True},
    )
    assert batches.format_schedule(spec) == (
        "premier dim du mois · 18:00 · Europe/Paris"
    )


def test_data_coverage_prefers_recovery_then_rolling_window() -> None:
    recovery = _spec(
        run_hours=("16",), run_minutes=("20",),
        raw_config={"recovery_run_hours": "22", "recovery_run_minutes": "20"},
    )
    assert batches.format_data_coverage(recovery) == (
        "Snapshot J non reconstructible · second passage conditionnel disponible à "
        "22:20 (Europe/Paris)"
    )
    rolling = _spec(raw_config={"lookback_days": 7})
    assert batches.format_data_coverage(rolling) == "Fenêtre rejouée : J−7 à J"
    forward = _spec(raw_config={"lookback_days": 7, "forward_days": 30})
    assert batches.format_data_coverage(forward) == "Fenêtre rejouée : J−7 à J+30"


def test_data_coverage_handles_local_backlog_and_disabled_contracts() -> None:
    raw = _spec(universe_scope="raw_sec_filings")
    assert "backlog RAW complet" in batches.format_data_coverage(raw)
    disabled = _spec(enabled=False)
    assert batches.format_data_coverage(disabled).startswith("Aucune collecte planifiée")


def test_data_coverage_uses_explicit_backup_scope() -> None:
    spec = _spec(raw_config={"coverage_description": "Snapshot complet des modèles"})
    assert batches.format_data_coverage(spec) == "Snapshot complet des modèles"


def test_commands_use_force_for_immediate_runs() -> None:
    generic = _spec()
    assert "install_forward_pit_task.ps1" in " ".join(batches.build_install_command(generic))
    assert "-BatchName daily_bars_sync" in batches.format_command(batches.build_install_command(generic))
    assert batches.build_run_command(generic)[-1] == "-Force"
    earnings = _spec("earnings_calendar_sync")
    assert batches.build_run_command(earnings)[-1] == "-Force"
    analyst = _spec("analyst_snapshot_collection")
    assert batches.build_run_command(analyst)[-1] == "-Force"
    market = _spec("market_cap_sync")
    assert batches.build_run_command(market)[-1] == "-Force"
    assert "forward_pit_launcher.ps1" in " ".join(batches.build_run_command(market))
    assert "install_forward_pit_task.ps1" in " ".join(batches.build_install_command(market))
    uninstall = batches.build_uninstall_command(generic)
    assert "uninstall_scheduled_batch_task.ps1" in " ".join(uninstall)
    assert uninstall[-2:] == ["-TaskName", "AlphaTrade-DailyBarsSync"]


def test_cn_dragon_research_uses_dedicated_launcher_and_file_ledger(tmp_path: Path) -> None:
    spec = _spec(
        "cn_dragon_tiger_before_open",
        raw_config={"output_root": str(tmp_path)},
        timezone="China Standard Time",
    )
    assert "cn_dragon_tiger_launcher_15d6.ps1" in " ".join(batches.build_install_command(spec))
    assert "cn_dragon_tiger_launcher_15d6.ps1" in " ".join(batches.build_run_command(spec))
    folder = tmp_path / "runs"
    folder.mkdir()
    (folder / "run-20260930T003000Z-unit.json").write_text(json.dumps({
        "batch": spec.name, "status": "COMPLETED_RESEARCH_ONLY",
        "started_at_utc": "2026-09-30T00:30:00+00:00",
        "finished_at_utc": "2026-09-30T00:31:00+00:00",
        "requested_count": 2, "received_count": 76,
        "persisted_count": 76, "failed_count": 0, "warning_count": 0,
    }), encoding="utf-8")
    row = batches.latest_cn_dragon_research_run(spec)
    assert row is not None and row["status"] == "COMPLETED"
    assert row["persisted_count"] == 76


def test_cn_research_commands_pass_cn_catalog_only_after_cutover(tmp_path: Path) -> None:
    cn_path = str(tmp_path / "batch_cn.yaml")
    for name in (
        "cn_dragon_tiger_before_open", "cn_dragon_tiger_after_close",
        "cn_oracle_prospective_daily", "cn_dragon_tiger_daily_match",
    ):
        legacy = _spec(name)
        future = _spec(name, catalog_path=cn_path)
        assert "-BatchConfigPath" not in batches.build_install_command(legacy)
        assert "-BatchConfigPath" not in batches.build_run_command(legacy)
        for command in (batches.build_install_command(future), batches.build_run_command(future)):
            position = command.index("-BatchConfigPath")
            assert command[position + 1] == cn_path


def test_cn_catalog_merge_rejects_duplicate_research_name(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(batches, "PROJECT_ROOT", tmp_path)
    def load(path):
        if path is None:
            return {"cn_oracle_prospective_daily": {"enabled": True, "status": "RESEARCH_ONLY"}}
        return {"cn_oracle_prospective_daily": {"enabled": True, "status": "RESEARCH_ONLY"}}
    monkeypatch.setattr(batches, "load_batch_config", load)
    with pytest.raises(ValueError, match="Duplicate cn_oracle_prospective_daily"):
        batches.load_batch_specs()


def test_cn_catalog_merge_loads_migrated_research_section(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(batches, "PROJECT_ROOT", tmp_path)
    def load(path):
        if path is None:
            return {"us_job": {"enabled": True}}
        return {"cn_oracle_prospective_daily": {"enabled": True, "status": "RESEARCH_ONLY"}}
    monkeypatch.setattr(batches, "load_batch_config", load)
    specs = {item.name: item for item in batches.load_batch_specs()}
    assert specs["us_job"].catalog_path.endswith("batch.yaml")
    assert specs["cn_oracle_prospective_daily"].catalog_path.endswith("batch_cn.yaml")
    assert "-BatchConfigPath" in batches.build_run_command(specs["cn_oracle_prospective_daily"])


def test_cn_oracle_daily_uses_dedicated_launcher_and_file_ledger(tmp_path: Path) -> None:
    spec = _spec("cn_oracle_prospective_daily", raw_config={"output_root": str(tmp_path)})
    assert "cn_oracle_daily_launcher_15d9.ps1" in " ".join(batches.build_install_command(spec))
    assert "cn_oracle_daily_launcher_15d9.ps1" in " ".join(batches.build_run_command(spec))
    folder = tmp_path / "runs"
    folder.mkdir()
    (folder / "run-20260930T183000Z-unit.json").write_text(json.dumps({
        "batch": spec.name, "status": "COMPLETED_RESEARCH_ONLY",
        "started_at_utc": "2026-09-30T17:00:00+00:00",
        "finished_at_utc": "2026-09-30T18:30:00+00:00",
        "requested_count": 5224, "received_count": 5228,
        "persisted_count": 1034, "failed_count": 0, "warning_count": 0,
    }), encoding="utf-8")
    row = batches.latest_cn_dragon_research_run(spec)
    assert row is not None and row["status"] == "COMPLETED"
    assert row["persisted_count"] == 1034


def test_cn_dragon_daily_match_uses_research_launcher_and_file_ledger(tmp_path: Path) -> None:
    spec = _spec("cn_dragon_tiger_daily_match", raw_config={"output_root": str(tmp_path)})
    assert "cn_dragon_tiger_daily_launcher_15d10.ps1" in " ".join(batches.build_install_command(spec))
    assert "cn_dragon_tiger_daily_launcher_15d10.ps1" in " ".join(batches.build_run_command(spec))
    folder = tmp_path / "runs"
    folder.mkdir()
    (folder / "run-20261008T013000Z-unit.json").write_text(json.dumps({
        "batch": spec.name, "status": "COMPLETED_RESEARCH_ONLY",
        "started_at_utc": "2026-10-08T01:30:00+00:00",
        "finished_at_utc": "2026-10-08T01:31:00+00:00",
        "requested_count": 1034, "received_count": 1034,
        "persisted_count": 3, "failed_count": 0, "warning_count": 0,
    }), encoding="utf-8")
    row = batches.latest_cn_dragon_research_run(spec)
    assert row is not None and row["status"] == "COMPLETED"
    assert row["persisted_count"] == 3


def test_cn_backup_is_catalogued_from_separate_cn_yaml_and_uses_own_launcher() -> None:
    specs = {item.name: item for item in batches.load_batch_specs()}
    spec = specs["cn_db_backup"]
    assert spec.enabled is True
    assert spec.status == "ACTIVE"
    assert spec.runnable is True
    assert spec.raw_config["db"] == "alpha_trade_cn"
    assert "batch_cn.yaml" in " ".join(batches.build_install_command(spec))
    assert "cn_db_backup_launcher_17b.ps1" in " ".join(batches.build_run_command(spec))
    assert not _spec("cn_db_backup", enabled=True, status="PENDING_RESTORE_PROOF").runnable


def test_cn_daily_quality_is_catalogued_without_enabling_duplicate_collector() -> None:
    specs = {item.name: item for item in batches.load_batch_specs()}
    quality = specs["cn_daily_quality_17c"]
    assert quality.enabled and quality.runnable and quality.status == "ACTIVE"
    assert quality.timezone == "Europe/Paris"
    assert "batch_cn.yaml" in " ".join(batches.build_install_command(quality))
    assert "cn_daily_quality_launcher_17c.ps1" in " ".join(batches.build_run_command(quality))
    assert "cn_daily_market_data_sync" not in specs


def test_cn_daily_quality_history_deduplicates_sessions_and_exposes_failed_gates(tmp_path: Path) -> None:
    spec = _spec("cn_daily_quality_17c", raw_config={"output_root": str(tmp_path)})
    folder = tmp_path / "runs"
    folder.mkdir()
    reports = [
        ("run-20261008T153000Z-old.json", "2026-10-08", "FAILED", "old_gate"),
        ("run-20261008T154000Z-new.json", "2026-10-08", "FAILED", "d9_owner_completed"),
        ("run-20261009T154000Z.json", "2026-10-09", "COMPLETED", ""),
    ]
    for name, session, status, alert in reports:
        (folder / name).write_text(json.dumps({
            "batch": spec.name, "session": session, "status": status,
            "failed_count": int(status == "FAILED"), "warning_count": 0,
            "checks": ([{"name": alert, "status": "CRITICAL"}] if alert else
                       [{"name": "chunks_complete", "status": "PASS"}]),
        }), encoding="utf-8")
    (folder / "run-20261010T154000Z-broken.json").write_text("{broken", encoding="utf-8")
    rows = batches.read_cn_daily_quality_history(spec)
    assert [row["session"] for row in rows] == ["2026-10-09", "2026-10-08"]
    assert rows[0]["passed"] == 1
    assert rows[1]["critical"] == 1 and rows[1]["alerts"] == "d9_owner_completed"
    assert batches.read_cn_daily_quality_history(_spec("daily_bars_sync")) == ()


def test_pending_batch_cannot_run() -> None:
    assert not _spec(enabled=False).runnable
    assert not _spec(status="PENDING_PROVIDER").runnable


def test_start_batch_is_async_and_suppresses_duplicate_notification(monkeypatch) -> None:
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(run_id="run-1")

    monkeypatch.setattr(batches, "start_managed_run", fake_start)
    record = batches.start_batch(_spec(), db_config={"host": "localhost"})
    assert record.run_id == "run-1"
    assert captured["step_key"] == "batch:daily_bars_sync"
    assert captured["notify_on_finish"] is False
    assert captured["timeout_seconds"] is None


def test_task_scheduler_json_is_normalized(monkeypatch) -> None:
    payload = [{
        "task_name": "AlphaTrade-DailyBarsSync",
        "state": "Ready",
        "enabled": True,
        "last_run_time": "1999-11-30T00:00:00.0000000+01:00",
        "next_run_time": "2026-09-14T11:00:00+02:00",
    }]
    monkeypatch.setattr(batches.sys, "platform", "win32")
    monkeypatch.setattr(
        batches.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    states, error = batches.query_windows_task_states()
    assert error is None
    assert states["AlphaTrade-DailyBarsSync"]["state"] == "Ready"
    assert states["AlphaTrade-DailyBarsSync"]["last_run_time"] is None
    assert states["AlphaTrade-DailyBarsSync"]["next_run_time"] == "2026-09-14T11:00:00+02:00"


def test_earnings_latest_audit_is_included_in_batch_page(monkeypatch) -> None:
    from ihm.pages import batches as page

    def fake_query(sql: str) -> pd.DataFrame:
        assert "cleaning_audit_earnings_runs" in sql
        return pd.DataFrame([{
            "batch_name": "earnings_calendar_sync", "provider": "finnhub",
            "status": "SUCCESS", "started_at": datetime(2026, 9, 17, 19, 27),
            "finished_at": datetime(2026, 9, 17, 20, 6),
            "requested_count": 1798, "persisted_count": 136,
        }])

    monkeypatch.setattr(page, "safe_query", fake_query)
    monkeypatch.setattr(page, "get_last_query_error", lambda: None)
    page._latest_collection_runs.clear()
    runs, error = page._latest_collection_runs()
    assert error is None
    assert runs["earnings_calendar_sync"]["status"] == "SUCCESS"


def test_batch_title_prefers_newer_business_success_to_stale_windows_failure() -> None:
    from ihm.pages import batches as page

    task = {
        "state": "Ready", "last_run_time": "2026-09-16T23:00:00+02:00",
        "last_result": 1073807364,
    }
    latest_success = {
        "status": "SUCCESS", "started_at": datetime(2026, 9, 17, 19, 27),
        "finished_at": datetime(2026, 9, 17, 20, 6),
    }
    assert not page._batch_title(["P1"], "earnings_calendar_sync", latest_success, task).startswith(":red[")
    old_success = {**latest_success, "finished_at": datetime(2026, 9, 16, 19, 0)}
    assert page._batch_title(["P1"], "earnings_calendar_sync", old_success, task).startswith(":red[")
    latest_failure = {**latest_success, "status": "FAILED"}
    assert page._batch_title(["P1"], "earnings_calendar_sync", latest_failure, task).startswith(":red[")
    assert page._database_time_label(datetime(2026, 9, 17, 20, 6)) == (
        "2026-09-17 22:06:00 Europe/Paris"
    )


@pytest.mark.parametrize("status", sorted(batches.RIGHTS_BLOCK_STATUSES))
@pytest.mark.parametrize("last_status", [None, "SUCCESS", "FAILED"])
def test_rights_block_title_remains_visible_regardless_of_last_run(status, last_status):
    from ihm.pages import batches as page
    row = {"status": last_status} if last_status else None
    title = page._batch_title(["P1", "Désactivé"], "sample", row, catalog_status=status)
    assert title.startswith("**⛔ ⚖️ DROITS / PRUDENCE")
    assert ":red[" not in title
    assert "sample" in title and "Désactivé" in title


@pytest.mark.parametrize("status", ["ACTIVE", "PENDING_PROVIDER", "BLOCKED_FREE_NO_NBBO_SOURCE",
                                  "BLOCKED_NO_FREE_OFFICIAL_FEED", "PENDING_QUALIFICATION"])
def test_technical_or_provider_block_does_not_show_rights_badge(status):
    from ihm.pages import batches as page
    title = page._batch_title(["P1"], "sample", {"status": "SUCCESS"}, catalog_status=status)
    assert "⚖️" not in title and "DROITS / PRUDENCE" not in title
    assert not title.startswith(":red[")


@pytest.mark.parametrize("market,expected", [
    ("US_EQ", {"analyst_snapshot_collection", "fred_alfred_vintage_sync", "finra_short_volume_sync"}),
    ("CN_A", {"cn_oracle_prospective_daily", "cn_dragon_tiger_after_close", "cn_dragon_tiger_before_open"}),
    ("FR_EQ", {"fr_fundamentals_sync", "fr_consensus_snapshot"}),
])
def test_rights_badge_covers_all_eight_blocked_collectors_across_markets(market, expected):
    actual = {s.name for s in batches.load_market_batch_specs(market)
              if s.status in batches.RIGHTS_BLOCK_STATUSES}
    assert actual == expected


def test_uninstall_batch_executes_exact_non_shell_command(monkeypatch) -> None:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="removed", stderr="")

    monkeypatch.setattr(batches.subprocess, "run", fake_run)
    result = batches.uninstall_batch(_spec())
    assert result.ok
    assert captured["command"][-2:] == ["-TaskName", "AlphaTrade-DailyBarsSync"]
    assert "shell" not in captured


def test_bulk_install_and_uninstall_continue_after_one_failure(monkeypatch) -> None:
    specs = [_spec("one"), _spec("two")]

    def fake_install(spec, *, run_as):
        if spec.name == "one":
            raise RuntimeError("boom")
        return batches.CommandResult(True, 0, "ok", "")

    monkeypatch.setattr(batches, "install_batch", fake_install)
    installed = batches.install_all_batches(specs, run_as="System")
    assert not installed["one"].ok
    assert installed["two"].ok

    monkeypatch.setattr(
        batches, "uninstall_batch",
        lambda spec: batches.CommandResult(True, 0, spec.name, ""),
    )
    removed = batches.uninstall_all_batches(specs)
    assert list(removed) == ["one", "two"]
    assert all(result.ok for result in removed.values())


def test_bulk_install_ignores_disabled_batches(monkeypatch) -> None:
    installed_names: list[str] = []

    def fake_install(spec, *, run_as):
        installed_names.append(spec.name)
        return batches.CommandResult(True, 0, "ok", "")

    monkeypatch.setattr(batches, "install_batch", fake_install)
    results = batches.install_all_batches(
        [_spec("active"), _spec("disabled", enabled=False)],
        run_as="Interactive",
    )

    assert installed_names == ["active"]
    assert list(results) == ["active"]


@pytest.mark.e2e
def test_batch_page_renders_without_external_dependencies(monkeypatch) -> None:
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from ihm.pages import batches as page

    monkeypatch.setattr(
        page,
        "load_market_batch_specs",
        lambda market: (
            _spec(),
            _spec(
                "pending_provider", enabled=False, status="PENDING_PROVIDER",
                activation_requirement="Choisir un fournisseur PIT.",
            ),
            _spec(
                "rights_block", enabled=False, status="BLOCKED_YAHOO_AUTOMATED_ACCESS",
                research_notice="Autorisation automatisation à confirmer.",
            ),
        ),
    )
    monkeypatch.setattr(page, "_task_states", lambda: ({}, None))
    monkeypatch.setattr(page, "_latest_collection_runs", lambda: ({}, None))
    monkeypatch.setattr(page, "list_active_batch_runs", lambda *args: [])
    monkeypatch.setattr(page, "load_pipeline_history", lambda: [])
    monkeypatch.setattr(page, "read_batch_log_tail", lambda spec: "")

    def runner() -> None:
        from ihm.pages import batches as batch_page
        batch_page.render()

    at = AppTest.from_function(runner).run(timeout=15)
    assert not at.exception
    assert any("Batchs planifiés" in title.value for title in at.title)
    metric_labels = {metric.label for metric in at.metric}
    assert "Exécutables (catalogues)" in metric_labels
    assert "Installés mais dormants" in metric_labels
    assert any("Choisir un fournisseur PIT." in error.value for error in at.error)
    assert any("⛔ ⚖️ DROITS / PRUDENCE" in expander.label and "rights_block" in expander.label
               for expander in at.expander)
    assert any("Ne pas relancer ni réactiver" in error.value for error in at.error)
    button_labels = {button.label for button in at.button}
    assert "♻️ Installer / réinstaller tous" in button_labels
    assert "🗑️ Désinstaller tous les batchs" in button_labels
