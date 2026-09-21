from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _migration_module():
    path = ROOT / "alembic_cn" / "versions" / "0001_tushare_raw_staging.py"
    spec = importlib.util.spec_from_file_location("cn_migration_0001", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cn_migration_contains_only_staging_contract() -> None:
    module = _migration_module()
    sql = module.TABLES_SQL
    assert "cn_ingestion_runs" in sql
    assert "tushare_raw_payloads" in sql
    assert "tushare_staging_rows" in sql
    assert "payload_hash" in sql
    assert "available_at" in sql
    for canonical in ("stock_bars_daily", "model_predictions", "global_oracle_labels"):
        assert f"CREATE TABLE IF NOT EXISTS {canonical}" not in sql


def test_sql_reference_matches_migration_table_contract() -> None:
    module = _migration_module()
    reference = (ROOT / "database" / "sql" / "cn" / "migration_cn_0001_tushare_raw_staging.sql").read_text(
        encoding="utf-8"
    )
    for table in module.TABLES_SQL.split("CREATE TABLE IF NOT EXISTS ")[1:]:
        assert table.split(" ", 1)[0] in reference


def test_raw_lineage_migration_is_run_scoped() -> None:
    sql = (ROOT / "database" / "sql" / "cn" / "migration_cn_0002_tushare_raw_run_lineage.sql").read_text(
        encoding="utf-8"
    )
    assert "(run_id,endpoint,request_hash,page_key)" in sql
    assert "uq_tushare_raw_page" in sql


def test_cn_batch_configuration_is_safe_by_default() -> None:
    payload = yaml.safe_load((ROOT / "batch_cn.yaml").read_text(encoding="utf-8"))
    assert payload["defaults"]["database_alias"] == "cn_primary"
    assert payload["defaults"]["canonical_writes_enabled"] is False
    jobs = {key: value for key, value in payload.items() if key not in {"schema_version", "defaults"}}
    assert jobs
    assert all(job["enabled"] is False for job in jobs.values())
    assert all(job["market_code"].startswith("CN_") for job in jobs.values())


def test_cn_application_config_keeps_canonical_writes_disabled() -> None:
    payload = yaml.safe_load((ROOT / "config_cn.yaml").read_text(encoding="utf-8"))
    assert payload["database_name"] == "alpha_trade_cn"
    assert payload["database_alias"] == "cn_primary"
    assert payload["canonical_writes_enabled"] is False


def test_windows_cn_launchers_reuse_notifications_and_hidden_scheduler() -> None:
    launcher = (ROOT / "scripts" / "windows" / "cn_ingestion_launcher.ps1").read_text(encoding="utf-8")
    installer = (ROOT / "scripts" / "windows" / "install_cn_ingestion_task.ps1").read_text(encoding="utf-8")
    common = (ROOT / "scripts" / "windows" / "forward_pit_launcher.ps1").read_text(encoding="utf-8")
    assert "batch_cn.yaml" in launcher
    assert "dataIntegrityEngine.cn_provider_ingestion" in launcher
    assert "install_forward_pit_task.ps1" in installer
    assert "send_batch_email.py" in common
    assert "Start-Process" in common and "-WindowStyle Hidden" in common


def test_cn_runner_failure_summary_preserves_partial_counters() -> None:
    source = (ROOT / "dataIntegrityEngine" / "cn_provider_ingestion.py").read_text(encoding="utf-8")
    assert "class CnBatchRunError" in source
    assert "counters = exc.counters if isinstance(exc, CnBatchRunError)" in source


def test_provider_neutral_staging_migration() -> None:
    sql = (ROOT / "database" / "sql" / "cn" / "migration_cn_0003_provider_neutral_staging.sql").read_text(
        encoding="utf-8"
    )
    assert "tushare_raw_payloads TO cn_raw_payloads" in sql
    assert "tushare_staging_rows TO cn_staging_rows" in sql
