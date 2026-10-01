"""Future CN catalog route must be explicit, unique and research-only."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from service.market.cn_catalog_contract_17d import validate
from service.market.cn_dragon_tiger_daily_15d10 import execute as d10_execute
from service.market.cn_dragon_tiger_schedule_15d6 import execute as d6_execute
from service.market.cn_oracle_daily_15d9 import execute as d9_execute

CALENDAR = Path("config/research_cn/sprint15d6_cn_calendar_2026.yaml").resolve()


def _config(tmp_path: Path, name: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "batch_cn.yaml"
    (tmp_path / "batch.yaml").write_text("{}", encoding="utf-8")
    cfg = {
        "enabled": True, "status": "RESEARCH_ONLY", "market_code": "CN_A",
        "database_alias": "cn_primary", "calendar": str(CALENDAR),
        "output_root": str(tmp_path / "output"),
    }
    if name.startswith("cn_dragon_tiger_"):
        cfg.update(run_hours="17", run_minutes="30")
    if name == "cn_dragon_tiger_daily_match":
        cfg["oracle_output_root"] = str(tmp_path / "oracle")
    if name == "cn_oracle_prospective_daily":
        cfg["oracle_output_root"] = str(tmp_path / "oracle")
    path.write_text(yaml.safe_dump({
        "defaults": {"database_alias": "cn_primary", "timezone": "Asia/Shanghai"},
        name: cfg,
    }), encoding="utf-8")
    return path


def test_cn_route_identity_and_duplicate_guard(tmp_path):
    path = _config(tmp_path, "cn_oracle_prospective_daily")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    identity = validate(path, config, "cn_oracle_prospective_daily")
    assert identity == {"market_code": "CN_A", "database_alias": "cn_primary",
                        "catalog_path": str(path.resolve())}
    legacy = tmp_path / "batch.yaml"
    legacy.write_text("cn_oracle_prospective_daily: {}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Duplicate CN batch"):
        validate(path, config, "cn_oracle_prospective_daily")


@pytest.mark.parametrize("field,value", [
    ("market_code", "US"), ("database_alias", "us_primary"),
])
def test_cn_route_refuses_unsafe_market_or_database(tmp_path, field, value):
    path = _config(tmp_path, "cn_oracle_prospective_daily")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["cn_oracle_prospective_daily"][field] = value
    with pytest.raises(RuntimeError, match="Unsafe CN catalog route"):
        validate(path, config, "cn_oracle_prospective_daily")


def test_legacy_catalog_keeps_existing_behavior(tmp_path):
    path = tmp_path / "batch.yaml"
    path.write_text("cn_oracle_prospective_daily: {}", encoding="utf-8")
    assert validate(path, yaml.safe_load(path.read_text(encoding="utf-8")),
                    "cn_oracle_prospective_daily") == {}


def test_all_three_cn_runners_accept_explicit_cn_catalog_without_collecting(tmp_path):
    d6 = _config(tmp_path / "d6", "cn_dragon_tiger_after_close")
    d6_result = d6_execute("cn_dragon_tiger_after_close", d6, CALENDAR,
                           now=datetime(2026, 10, 8, 9, 30, tzinfo=UTC), probe=True)
    assert d6_result["status"] == "DUE"
    d9 = _config(tmp_path / "d9", "cn_oracle_prospective_daily")
    d9_result = d9_execute(batch_config=d9,
                           now=datetime(2026, 10, 8, 10, 15, tzinfo=UTC), dry_run=True)
    assert d9_result["status"] == "DUE"
    d10 = _config(tmp_path / "d10", "cn_dragon_tiger_daily_match")
    d10_result = d10_execute(batch_config=d10,
                             now=datetime(2026, 10, 8, 1, 30, tzinfo=UTC), dry_run=True)
    assert d10_result["status"] == "DUE"
    assert not any((tmp_path / name / "output").exists() for name in ("d6", "d9", "d10"))
