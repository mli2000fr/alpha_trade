"""US planning: Paris absence, runtime margin, NY dates and DST transitions."""
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
PARIS = ZoneInfo("Europe/Paris")

# Conservative planning budgets, not runtime timeouts. Read-only 30-day audit
# of successful runs on 2026-10-10; roughly 2 * worst duration + 30 min,
# with a 45 min floor and rounding upwards (see operational document).
BUDGET_MINUTES = {
    "market_cap_sync": 190,
    "sec_edgar_incremental": 90,
    "db_news_raw_backup": 65,
    "borrow_status_snapshot": 45,
    "oracle_opening_window_sync": 45,
    "oracle_options_indicative_snapshot": 90,
    "sec_corporate_events_normalize": 45,
    "sec_institutional_ownership_normalize": 45,
    "options_delayed_bars_sync": 65,
    "corporate_actions_sync": 45,
    "security_master_snapshot": 45,
    "option_contract_adjustment_sync": 45,
    "daily_bars_sync": 45,
    "ml_artifacts_backup": 45,
    "db_core_backup": 70,
}


def _passages(cfg):
    for prefix in ("", "recovery_"):
        hours = str(cfg.get(prefix + "run_hours") or "").split(",")
        minutes = str(cfg.get(prefix + "run_minutes") or "0").split(",")
        for i, hour in enumerate(hours):
            if hour:
                minute = minutes[i] if len(minutes) == len(hours) else minutes[0]
                yield prefix, int(hour), int(minute)


def test_every_active_us_batch_is_checked_except_unchanged_pipeline():
    active = {name for name, cfg in CONFIG.items()
              if cfg.get("enabled") and not name.startswith(("cn_", "fr_"))}
    assert active == set(BUDGET_MINUTES) | {"us_pipeline"}
    pipeline = CONFIG["us_pipeline"]
    assert pipeline["timezone"] == "Europe/Paris"
    assert pipeline["run_hours"] == "22" and pipeline["run_minutes"] == "45"
    assert pipeline["run_days"] == "1,2,3,4,5"
    assert "recovery_run_hours" not in pipeline


@pytest.mark.parametrize("name", BUDGET_MINUTES)
def test_principal_and_recovery_fit_paris_night_with_runtime_margin(name):
    cfg = CONFIG[name]
    timezone = ZoneInfo(cfg["timezone"])
    weekdays = {int(day) for day in cfg["run_days"].split(",")}
    day = date(2025, 1, 1)
    while day < date(2028, 1, 1):
        # The launcher uses .NET DayOfWeek: Sunday=0, Monday=1.
        if (day.weekday() + 1) % 7 in weekdays:
            for passage, hour, minute in _passages(cfg):
                start = datetime.combine(day, time(hour, minute), timezone).astimezone(PARIS)
                cutoff_day = start.date() + timedelta(days=start.hour >= 20)
                # Finish budget by 07:00, leaving 30 min before departure.
                cutoff = datetime.combine(cutoff_day, time(7), PARIS)
                finish = (start.astimezone(ZoneInfo("UTC"))
                          + timedelta(minutes=BUDGET_MINUTES[name])).astimezone(PARIS)
                assert start.hour >= 20 or start.hour < 7, (name, passage, start)
                assert finish <= cutoff, (name, passage, start, finish, cutoff)
        day += timedelta(days=1)


def test_snapshot_recoveries_stay_same_configured_day_and_after_principal():
    for name in BUDGET_MINUTES:
        cfg = CONFIG[name]
        passages = list(_passages(cfg))
        if len(passages) == 2:
            _, hour, minute = passages[0]
            _, recovery_hour, recovery_minute = passages[1]
            delta_hours = ((recovery_hour * 60 + recovery_minute) - (hour * 60 + minute)) / 60
            # No new midnight weekday rollover logic needed in the launcher.
            assert delta_hours > 0
            assert delta_hours < cfg["recovery_success_lookback_hours"] < 24


@pytest.mark.parametrize("name", ["borrow_status_snapshot", "oracle_options_indicative_snapshot",
                                  "options_delayed_bars_sync"])
@pytest.mark.parametrize("friday", [date(2026, 3, 13), date(2026, 7, 10), date(2026, 10, 30)])
def test_friday_ny_recovery_is_saturday_paris_without_losing_us_session(name, friday):
    cfg = CONFIG[name]
    assert cfg["timezone"] == "America/New_York"
    assert "5" in cfg["run_days"].split(",")
    prefix, hour, minute = list(_passages(cfg))[1]
    assert prefix == "recovery_"
    ny = datetime.combine(friday, time(hour, minute), ZoneInfo(cfg["timezone"]))
    assert ny.astimezone(PARIS).date() == friday + timedelta(days=1)
    assert ny.date() == friday


def test_windows_trigger_minutes_unchanged_no_reinstall_needed():
    # Installed hourly triggers were inspected read-only on 2026-10-10.
    installed = {
        "market_cap_sync": {0}, "security_master_snapshot": {0},
        "sec_edgar_incremental": {0}, "db_news_raw_backup": {0},
        "borrow_status_snapshot": {25, 45}, "option_contract_adjustment_sync": {15},
        "oracle_opening_window_sync": {50}, "sec_corporate_events_normalize": {0},
        "sec_institutional_ownership_normalize": {0},
    }
    for name, minutes in installed.items():
        assert {minute for _, _, minute in _passages(CONFIG[name])} == minutes
