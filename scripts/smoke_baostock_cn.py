from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dataIntegrityEngine.cn_provider_ingestion import execute  # noqa: E402

DEFAULT_OUTPUT = ROOT / "artifacts" / "audits" / "market_integration" / "sprint_06" / "real_provider_smoke.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke réel et borné du fournisseur gratuit BaoStock")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    status, counters = execute(
        "cn_baostock_smoke",
        config_path=ROOT / "batch_cn.yaml",
        force=True,
    )
    report = {
        "provider": "baostock",
        "status": "PASS" if status.startswith("COMPLETED") and counters.received > 0 else "FAIL",
        "run_status": status,
        **counters.to_dict(),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
