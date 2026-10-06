"""Precautionary CN rights blocks must survive an enabled-only toggle."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from ihm.services import batch_management
from service.market import cn_dragon_tiger_schedule_15d6 as dragon
from service.market import cn_oracle_daily_15d9 as oracle


ROOT = Path(__file__).resolve().parents[1]
BLOCKS = [
    ("cn_dragon_tiger_after_close", "BLOCKED_SSE_SZSE_AUTOMATION"),
    ("cn_dragon_tiger_before_open", "BLOCKED_SSE_SZSE_AUTOMATION"),
    ("cn_oracle_prospective_daily", "BLOCKED_BAOSTOCK_RIGHTS"),
]


@pytest.mark.parametrize("name,status", BLOCKS)
def test_cn_catalog_exposes_block_and_unlock_instructions(name, status):
    specs = batch_management.load_market_batch_specs("CN_A")
    spec = next(item for item in specs if item.name == name)
    assert spec.status == status
    assert not spec.enabled and not spec.runnable
    assert spec.activation_requirement and spec.unlock_steps
    assert spec.research_notice
    assert not replace(spec, enabled=True).runnable


@pytest.mark.parametrize("name,status", BLOCKS)
def test_enabled_toggle_cannot_collect_even_with_manual_force(tmp_path, monkeypatch, name, status):
    config = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    section = dict(config[name], enabled=True)
    assert section["status"] == status
    path = tmp_path / "batch.yaml"
    path.write_text(yaml.safe_dump({name: section}), encoding="utf-8")
    existing_paths = set(tmp_path.rglob("*"))

    def forbidden(*args, **kwargs):
        pytest.fail("Blocked batch must not collect, open SQL or score")

    monkeypatch.setattr(dragon, "collect", forbidden)
    monkeypatch.setattr(oracle, "get_market_engine", forbidden)
    monkeypatch.setattr(oracle, "prepare", forbidden)
    monkeypatch.setattr(oracle, "run_all", forbidden)
    monkeypatch.setattr(oracle, "oracle_run", forbidden)
    now = datetime(2026, 9, 30, 11, 0, tzinfo=UTC)
    if name == oracle.BATCH_NAME:
        result = oracle.execute(batch_config=path, now=now)
    else:
        result = dragon.execute(name, path, ROOT / "config/research_cn/sprint15d6_cn_calendar_2026.yaml",
                                now=now, force=True)
    assert result["status"] == "SKIP_DISABLED"
    assert set(tmp_path.rglob("*")) == existing_paths
