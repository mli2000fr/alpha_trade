"""Fail-closed identity contract for CN research tasks after catalog cutover."""

from __future__ import annotations

from pathlib import Path

import yaml


def validate(batch_config: Path, config: dict, batch_name: str) -> dict:
    """Keep legacy behavior; validate explicit CN route and ownership after cutover."""
    if batch_config.name != "batch_cn.yaml":
        return {}
    defaults = config.get("defaults") or {}
    cfg = config.get(batch_name) or {}
    if (defaults.get("database_alias") != "cn_primary"
            or defaults.get("timezone") != "Asia/Shanghai"
            or cfg.get("market_code") != "CN_A"
            or cfg.get("database_alias") != "cn_primary"):
        raise RuntimeError(f"Unsafe CN catalog route for {batch_name}")
    legacy_path = batch_config.resolve().parent / "batch.yaml"
    if legacy_path.is_file():
        legacy = yaml.safe_load(legacy_path.read_text(encoding="utf-8")) or {}
        if not isinstance(legacy, dict):
            raise ValueError("Legacy batch.yaml must be a mapping")
        if batch_name in legacy:
            raise RuntimeError(f"Duplicate CN batch section across catalogs: {batch_name}")
    return {"market_code": "CN_A", "database_alias": "cn_primary",
            "catalog_path": str(batch_config.resolve())}
