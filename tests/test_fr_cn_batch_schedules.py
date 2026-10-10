"""Active FR/CN schedules fit Paris presence, including daylight saving."""
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PARIS = ZoneInfo("Europe/Paris")


def _active(path):
    raw = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    return {name: {**raw.get("defaults", {}), **cfg}
            for name, cfg in raw.items()
            if isinstance(cfg, dict) and name != "defaults" and cfg.get("enabled")}


FR = _active("batch_fr.yaml")
CN = {**_active("batch_cn.yaml"),
      **{name: cfg for name, cfg in _active("batch.yaml").items() if name.startswith("cn_")}}
# Planning margins, not forced timeouts. Successful local archives/run logs
# audited on 2026-10-10. ESMA gets extra headroom for its bounded catchup;
# unobserved jobs have conservative budgets, not a claim of measured duration.
BUDGETS = {
    "fr_calendar_snapshot": 45, "fr_security_master_sync": 120,
    "fr_daily_bars_sync": 45, "fr_corporate_actions_sync": 50,
    "fr_amf_short_sync": 45, "fr_dila_disclosures_sync": 45,
    "fr_options_mifir_trade_sync": 45, "fr_db_backup": 90,
    "fr_artifacts_backup": 90, "cn_db_backup": 50,
    "cn_daily_quality_17c": 45, "cn_dragon_tiger_daily_match": 45,
}


def test_all_active_fr_cn_jobs_have_a_runtime_budget():
    assert set(FR) | set(CN) == set(BUDGETS)


@pytest.mark.parametrize("name", BUDGETS)
def test_main_and_any_recovery_fit_night(name):
    cfg = (FR | CN)[name]
    zone = ZoneInfo({"China Standard Time": "Asia/Shanghai"}.get(cfg["timezone"], cfg["timezone"]))
    # D10's research launcher applies the CN calendar itself (weekdays).
    weekdays = {int(d) for d in str(cfg.get("run_days", "1,2,3,4,5")).split(",")}
    day = date(2025, 1, 1)
    while day < date(2028, 1, 1):
        if (day.weekday() + 1) % 7 in weekdays:
            for prefix in ("", "recovery_"):
                hours = str(cfg.get(prefix + "run_hours", "")).split(",")
                minutes = str(cfg.get(prefix + "run_minutes", "0")).split(",")
                for i, hour in enumerate(hours):
                    if not hour:
                        continue
                    minute = minutes[i] if len(minutes) == len(hours) else minutes[0]
                    start = datetime.combine(day, time(int(hour), int(minute)), zone).astimezone(PARIS)
                    cutoff = datetime.combine(start.date() + timedelta(days=start.hour >= 20), time(7), PARIS)
                    finish = (start.astimezone(ZoneInfo("UTC"))
                              + timedelta(minutes=BUDGETS[name])).astimezone(PARIS)
                    assert start.hour >= 20 or start.hour < 7, (name, start)
                    assert finish <= cutoff, (name, start, finish)
        day += timedelta(days=1)


def test_disabled_collectors_not_reactivated_and_minutes_unchanged():
    assert len(FR) == 9 and len(CN) == 3
    assert CN["cn_daily_quality_17c"]["audit_previous_day_before_open"] is True
    assert CN["cn_daily_quality_17c"]["run_minutes"] == "30"
    # Installed hourly triggers already cover these minutes; no reinstall.
    for name in ("fr_calendar_snapshot", "fr_security_master_sync", "fr_options_mifir_trade_sync"):
        assert FR[name]["run_minutes"] == "0"
    assert FR["fr_daily_bars_sync"]["run_hours"] == "22"
    assert FR["fr_daily_bars_sync"]["after_close_hour_paris"] == 22
