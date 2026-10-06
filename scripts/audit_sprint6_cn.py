from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.router import get_market_engine  # noqa: E402
from service.tushare.bootstrap_database import (  # noqa: E402
    EXPECTED_REVISION,
    EXPECTED_TABLES,
    audit_database,
)

DEFAULT_OUTPUT = ROOT / "artifacts" / "audits" / "market_integration" / "sprint_06"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _configuration_audit() -> dict[str, Any]:
    batches = yaml.safe_load((ROOT / "batch_cn.yaml").read_text(encoding="utf-8")) or {}
    defaults = batches.get("defaults") or {}
    jobs = {key: value for key, value in batches.items() if key not in {"schema_version", "defaults"}}
    return {
        "database_alias": defaults.get("database_alias"),
        "provider": defaults.get("provider"),
        "baostock_dependency_installed": importlib.util.find_spec("baostock") is not None,
        "canonical_writes_enabled": defaults.get("canonical_writes_enabled"),
        "jobs": {
            name: {
                "enabled": bool(job.get("enabled", False)),
                "market_code": job.get("market_code"),
                "endpoints": list(job.get("endpoints") or []),
            }
            for name, job in jobs.items()
        },
    }


def _staging_counts() -> dict[str, int]:
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        tables = set(inspect(engine).get_table_names())
        counts: dict[str, int] = {}
        with engine.connect() as connection:
            for table in sorted(EXPECTED_TABLES & tables):
                counts[table] = int(connection.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0)
        return counts
    finally:
        engine.dispose()


def run(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    database = audit_database()
    configuration = _configuration_audit()
    counts = _staging_counts()
    real_smoke_path = output_dir / "real_provider_smoke.json"
    real_smoke: dict[str, Any] | None = None
    if real_smoke_path.exists():
        real_smoke = json.loads(real_smoke_path.read_text(encoding="utf-8"))
    structural_pass = (
        database.get("status") == "PASS"
        and database.get("alembic_version") == EXPECTED_REVISION
        and configuration.get("database_alias") == "cn_primary"
        and configuration.get("canonical_writes_enabled") is False
        and all(not item["enabled"] for item in configuration["jobs"].values())
    )
    real_smoke_pass = bool(real_smoke and real_smoke.get("status") == "PASS")
    if structural_pass and real_smoke_pass:
        status = "GO"
        blocker = None
    elif structural_pass and not configuration["baostock_dependency_installed"]:
        status = "READY_BLOCKED_BAOSTOCK_DEPENDENCY"
        blocker = "Installer requirements.txt puis exécuter le smoke BaoStock réel."
    elif structural_pass:
        status = "READY_BLOCKED_REAL_PROVIDER_SMOKE"
        blocker = "Exécuter et valider manuellement le smoke fournisseur réel."
    else:
        status = "NO_GO_STRUCTURE"
        blocker = "Corriger les contrôles structurels en échec avant toute collecte réelle."
    generated_at = datetime.now(UTC).isoformat()
    database_payload = {**database, "table_counts": counts, "generated_at": generated_at}
    gate = {
        "sprint": 6,
        "status": status,
        "structural_pass": structural_pass,
        "real_provider_smoke_pass": real_smoke_pass,
        "provider": configuration.get("provider"),
        "baostock_dependency_installed": configuration["baostock_dependency_installed"],
        "blocker": blocker,
        "canonical_writes": 0,
        "generated_at": generated_at,
    }
    _write_json(output_dir / "database_audit.json", database_payload)
    _write_json(output_dir / "effective_config.json", configuration)
    _write_json(output_dir / "gate_result.json", gate)
    return gate


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit reproductible du gate Sprint 6 CN")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
