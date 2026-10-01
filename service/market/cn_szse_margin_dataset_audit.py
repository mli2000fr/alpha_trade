"""Read-only verification of the completed 15-B4 dataset, streaming partitions."""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from service.market.cn_margin_lending_contract_audit import proxy_available_at
from service.market.cn_szse_margin_dataset import CONFIG, OUTPUT, checkpoint, sha

LOG = logging.getLogger(__name__)


def validate_row(row: dict, day: str, proxy: str | None, reference: dict) -> None:
    if (row["source_session"] != day or row["market_code"] != "CN_A"
            or row["exchange_mic"] != "XSHE" or row["strict_ml_allowed"] is not False
            or row["historical_vintage_proven"] is not False):
        raise ValueError("Wrong date, scope or PIT status")
    instrument = reference[row["instrument_id"]]
    if (instrument["local_symbol"] != row["local_symbol"] or instrument["listing_date"] > day
            or instrument["delisting_date"] and instrument["delisting_date"] < day):
        raise ValueError("Wrong historical instrument")
    actual = row["research_available_at_proxy"]
    if (actual is None) != (proxy is None):
        raise ValueError("Wrong proxy presence")
    if actual is not None and datetime.fromisoformat(actual) != datetime.fromisoformat(proxy):
        raise ValueError("Wrong proxy timestamp")
    measures = row["measures"]
    if measures is None:
        if row["observation_status"] != "ELIGIBLE_WITHOUT_OBSERVATION":
            raise ValueError("Missing observation imputed")
    elif (any(not isinstance(v, int) or v < 0 for v in measures.values())
          or measures["融资余额"] + measures["融券余额"] != measures["融资融券余额"]):
        raise ValueError("Wrong numeric values or balance")
    ratio = row["financing_buy_to_amount"]
    if row["quality_reasons"] and ratio is not None:
        raise ValueError("Invalid ratio exposed")
    if ratio is not None and (measures is None or not row["amount_cny"]
                              or not math.isclose(ratio, measures["融资买入额"] / row["amount_cny"],
                                                  rel_tol=1e-12, abs_tol=1e-12)):
        raise ValueError("Wrong monetary normalization")


def run(root: Path, report_path: Path) -> dict:
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    report = {"status": "RUNNING", "errors": [], "years": {}, "missing_observations": [],
              "proxy_missing_days": [], "quality_reasons": {}, "ratio_above_one": 0,
              "ratio_above_one_samples": [],
              "strict_ml_allowed": False, "training_ready": False}
    if state["contract"]["config_sha256"] != sha(CONFIG):
        report["errors"].append("Configuration fingerprint differs")
    if state["contract"]["implementation_sha256"] != sha(
            Path(__file__).with_name("cn_szse_margin_dataset.py")):
        report["errors"].append("Collector fingerprint differs")
    snapshot_path = root / "reference_snapshot.json"
    if sha(snapshot_path) != state["reference_sha256"]:
        raise ValueError("Reference hash differs")
    frozen = json.loads(snapshot_path.read_text(encoding="utf-8"))
    sessions = [(date.fromisoformat(d), datetime.fromisoformat(t) if t else None)
                for d, t in frozen["sessions"]]
    reference = {r["instrument_id"]: r for r in frozen["instruments"]}
    dates = state["contract"]["session_dates"]
    if sorted(state["sessions"]) != dates:
        report["errors"].append("Missing or unexpected session keys")
    reasons = Counter()
    for index, day in enumerate(dates):
        item = state["sessions"].get(day, {})
        year = day[:4]
        totals = report["years"].setdefault(year, {
            "days": 0, "rows": 0, "observed": 0, "valid_feature_rows": 0,
            "duplicate_rows": 0, "detail_outside_eligible": 0})
        try:
            if item.get("status") != "COMPLETED":
                raise ValueError("Session not completed")
            partition = root / f"{day}.jsonl.gz"
            if sha(partition) != item["partition_sha256"]:
                raise ValueError("Partition fingerprint differs")
            for name, receipt in item["sources"].items():
                if sha(root / name) != receipt["sha256"]:
                    raise ValueError(f"Raw source fingerprint differs: {name}")
                stored = json.loads((root / (name + ".receipt.json")).read_text(encoding="utf-8"))
                if stored != receipt or stored["historical_vintage_proven"] is not False:
                    raise ValueError("Receipt differs")
            try:
                proxy = proxy_available_at(date.fromisoformat(day), sessions).isoformat()
            except ValueError:
                proxy = None
                report["proxy_missing_days"].append(day)
            ids = set()
            daily = Counter()
            with gzip.open(partition, "rt", encoding="utf-8") as stream:
                for line in stream:
                    row = json.loads(line)
                    validate_row(row, day, proxy, reference)
                    if row["instrument_id"] in ids:
                        raise ValueError("Duplicate instrument/date")
                    ids.add(row["instrument_id"])
                    daily["rows"] += 1
                    daily["observed"] += row["measures"] is not None
                    daily["valid_feature_rows"] += not row["quality_reasons"]
                    reasons.update(row["quality_reasons"])
                    if row["measures"] is None:
                        report["missing_observations"].append(
                            {"day": day, "instrument_id": row["instrument_id"], "symbol": row["local_symbol"]})
                    if row["financing_buy_to_amount"] is not None and row["financing_buy_to_amount"] > 1:
                        report["ratio_above_one"] += 1
                        report["ratio_above_one_samples"].append({
                            "day": day, "instrument_id": row["instrument_id"],
                            "symbol": row["local_symbol"], "amount_cny": row["amount_cny"],
                            "financing_buy_cny": row["measures"]["融资买入额"],
                            "ratio": row["financing_buy_to_amount"]})
            expected = {"rows": item["eligible_equities"], "observed": item["observed_equities"],
                        "valid_feature_rows": item["valid_feature_rows"]}
            if any(daily[key] != value for key, value in expected.items()):
                raise ValueError("Session counters differ")
            totals["days"] += 1
            for key in expected:
                totals[key] += daily[key]
            totals["detail_outside_eligible"] += len(item["detail_outside_eligible"])
        except Exception as exc:
            report["errors"].append({"day": day, "error": str(exc)})
        if index % 100 == 0:
            LOG.info("audited=%s/%s errors=%s", index + 1, len(dates), len(report["errors"]))
            checkpoint(report_path, report)
    report["quality_reasons"] = dict(reasons)
    report["status"] = "PASS_COLLECTION_AUDIT_PROXY_ONLY" if not report["errors"] else "FAIL"
    report["summary"] = {key: sum(y[key] for y in report["years"].values())
                         for key in ("days", "rows", "observed", "valid_feature_rows")}
    report["coverage_pct"] = 100 * report["summary"]["observed"] / report["summary"]["rows"]
    checkpoint(report_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run(args.dataset_root, args.dataset_root / "audit_report.json")
    print(json.dumps(result, ensure_ascii=True))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
