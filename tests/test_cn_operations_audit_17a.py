"""Sprint 17-A config audit must not activate or change CN/US batch state."""

from pathlib import Path

import yaml

from service.market.cn_operations_audit_17a import inspect


def _write(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_audit_detects_disabled_cn_operations_without_mutating_files(tmp_path):
    us = _write(tmp_path / "batch.yaml", {
        name: {"enabled": True, "status": "RESEARCH_ONLY", "timezone": "China Standard Time"}
        for name in (
            "cn_dragon_tiger_after_close", "cn_dragon_tiger_before_open",
            "cn_oracle_prospective_daily", "cn_dragon_tiger_daily_match",
        )
    })
    cn = _write(tmp_path / "batch_cn.yaml", {
        "defaults": {"database_alias": "cn_primary", "timezone": "Asia/Shanghai"},
        "cn_daily_market_data_sync": {"enabled": False},
        "cn_staging_quality_daily": {"enabled": False},
    })
    before = (us.read_bytes(), cn.read_bytes())
    report = inspect(us_batch_path=us, cn_batch_path=cn)
    assert (us.read_bytes(), cn.read_bytes()) == before
    assert report["database_modified"] is False
    assert {item["code"] for item in report["findings"]} >= {
        "CN_RESEARCH_IN_LEGACY_BATCH_CATALOG", "CN_STAGING_QUALITY_DISABLED",
        "CN_BACKUP_NOT_SCHEDULED",
    }
    assert "CN_CANONICAL_DAILY_SYNC_DISABLED" not in {
        item["code"] for item in report["findings"]
    }


def test_audit_catches_unsafe_route_and_duplicate_batch_name(tmp_path):
    us = _write(tmp_path / "batch.yaml", {"cn_oracle_prospective_daily": {"enabled": True}})
    cn = _write(tmp_path / "batch_cn.yaml", {
        "defaults": {"database_alias": "us_primary", "timezone": "Europe/Paris"},
        "cn_oracle_prospective_daily": {"enabled": True},
    })
    report = inspect(us_batch_path=us, cn_batch_path=cn)
    codes = {item["code"] for item in report["findings"]}
    assert "DUPLICATE_CN_BATCH_NAME" in codes
    assert "CN_DATABASE_ROUTE_UNSAFE" in codes
    assert "CN_TIMEZONE_UNSAFE" in codes


def test_audit_accepts_d9_owner_and_17c_quality_but_rejects_second_owner(tmp_path):
    us = _write(tmp_path / "batch.yaml", {
        name: {"enabled": True, "status": "RESEARCH_ONLY", "timezone": "China Standard Time"}
        for name in (
            "cn_dragon_tiger_after_close", "cn_dragon_tiger_before_open",
            "cn_oracle_prospective_daily", "cn_dragon_tiger_daily_match",
        )
    })
    cn_payload = {
        "defaults": {"database_alias": "cn_primary", "timezone": "Asia/Shanghai"},
        "cn_daily_market_data_sync": {"enabled": False},
        "cn_staging_quality_daily": {"enabled": False},
        "cn_daily_quality_17c": {"enabled": True},
        "cn_db_backup": {"enabled": True},
    }
    cn = _write(tmp_path / "batch_cn.yaml", cn_payload)
    codes = {item["code"] for item in inspect(us_batch_path=us, cn_batch_path=cn)["findings"]}
    assert "CN_CANONICAL_DAILY_SYNC_DISABLED" not in codes
    assert "CN_STAGING_QUALITY_DISABLED" not in codes
    assert "CN_BACKUP_NOT_SCHEDULED" not in codes
    cn_payload["cn_daily_market_data_sync"]["enabled"] = True
    _write(cn, cn_payload)
    codes = {item["code"] for item in inspect(us_batch_path=us, cn_batch_path=cn)["findings"]}
    assert "CN_DUPLICATE_CANONICAL_DAILY_OWNER" in codes


def test_audit_accepts_research_batches_moved_to_cn_catalog(tmp_path):
    us = _write(tmp_path / "batch.yaml", {})
    cn = _write(tmp_path / "batch_cn.yaml", {
        "defaults": {"database_alias": "cn_primary", "timezone": "Asia/Shanghai"},
        **{name: {"enabled": True, "status": "RESEARCH_ONLY", "timezone": "China Standard Time",
                  "market_code": "CN_A", "database_alias": "cn_primary"}
           for name in (
               "cn_dragon_tiger_before_open", "cn_dragon_tiger_after_close",
               "cn_oracle_prospective_daily", "cn_dragon_tiger_daily_match",
           )},
        "cn_daily_market_data_sync": {"enabled": False},
        "cn_daily_quality_17c": {"enabled": True},
        "cn_db_backup": {"enabled": True},
    })
    codes = {item["code"] for item in inspect(us_batch_path=us, cn_batch_path=cn)["findings"]}
    assert "CN_RESEARCH_BATCH_MISSING" not in codes
    assert "CN_RESEARCH_IN_LEGACY_BATCH_CATALOG" not in codes
    assert "CN_CANONICAL_DAILY_SYNC_DISABLED" not in codes
    assert "CN_RESEARCH_ROUTE_UNSAFE" not in codes
