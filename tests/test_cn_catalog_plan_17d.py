"""The 17-D preparation must not mutate either catalog or bypass the gate."""

from pathlib import Path

import yaml

from service.market.cn_catalog_plan_17d import prepare
from service.market.cn_catalog_preflight_17d import RESEARCH_BATCHES


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    us, cn = tmp_path / "batch.yaml", tmp_path / "batch_cn.yaml"
    us.write_text(yaml.safe_dump({name: {
        "enabled": True, "status": "RESEARCH_ONLY", "run_hours": "17",
        "provider": "official", "output_root": "artifacts/cn",
    } for name in RESEARCH_BATCHES}), encoding="utf-8")
    cn.write_text(yaml.safe_dump({
        "defaults": {"database_alias": "cn_primary"},
        "cn_daily_market_data_sync": {"enabled": False},
        "cn_daily_quality_17c": {"enabled": True, "status": "ACTIVE"},
    }), encoding="utf-8")
    return us, cn, tmp_path / "quality"


def test_plan_preserves_all_business_fields_and_does_not_write(tmp_path):
    us, cn, quality = _paths(tmp_path)
    before = us.read_bytes(), cn.read_bytes()
    report = prepare(us_batch_path=us, cn_batch_path=cn, quality_root=quality)
    assert report["status"] == "HOLD"
    assert report["blockers"] == ["first_real_d6_d9_d10_quality_cycle_missing"]
    assert set(report["sections"]) == set(RESEARCH_BATCHES)
    assert all(section["business_fields_unchanged"] for section in report["sections"].values())
    assert all(section["added_identity"] == {"market_code": "CN_A", "database_alias": "cn_primary"}
               for section in report["sections"].values())
    assert (us.read_bytes(), cn.read_bytes()) == before
    assert not quality.exists()


def test_duplicate_section_blocks_preparation(tmp_path):
    us, cn, quality = _paths(tmp_path)
    payload = yaml.safe_load(cn.read_text(encoding="utf-8"))
    payload[RESEARCH_BATCHES[0]] = {"enabled": True, "status": "RESEARCH_ONLY"}
    cn.write_text(yaml.safe_dump(payload), encoding="utf-8")
    report = prepare(us_batch_path=us, cn_batch_path=cn, quality_root=quality)
    assert report["status"] == "HOLD"
    assert f"cannot_prepare_unique_move:{RESEARCH_BATCHES[0]}" in report["blockers"]
