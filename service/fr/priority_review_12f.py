"""Priority register and narrowly scoped evidence: never grant an economic GO."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

REVIEWED_HASHES = {
    "ttf_scope": "7396390f25a1cd074f819668551ed29fcfd576daec8ac4c5dcf49f18dfe9862c",
    "xfab_2023": "f3e7fc5a8220ea80266dc86f7a87cf84b71270c9766ebe52ac7406b25a4a556b",
    "xfab_2024": "fd238d9ca0d0a9497a64d28c73459d071a8f95407f9e4d2d77489967aafbbdcc",
    "xfab_2025": "151395f22cdac25ba5655c50d57f9c3aeae274f0bb7ae8cea050c601006ebbfe",
}


def priority_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Rank missing fiscal evidence by frozen intentions, not realized returns."""
    keys = ["fold", "entry_session", "research_uid", "policy"]
    if frame.duplicated(keys).any():
        raise ValueError("Duplicate intentions")
    if frame.future_label_used.any():
        raise ValueError("Future labels in intentions")
    subset = frame[frame.policy.eq("oracle_top20_long") & ~frame.tax_qualified].copy()
    subset["first_8"] = subset.candidate_rank.le(8)
    return subset.groupby(["symbol", "isin"], as_index=False).agg(
        oracle_intentions=("entry_session", "size"),
        first_8_intentions=("first_8", "sum"),
        years=("tax_year", lambda x: sorted({int(v) for v in x.dropna()})),
    ).sort_values(["oracle_intentions", "symbol"], ascending=[False, True])


def verified_sources(source_root: Path) -> dict:
    report = json.loads((source_root / "report.json").read_text(encoding="utf-8"))
    for row in report["sources"].values():
        if row.get("status") != "ARCHIVED_NOT_PROMOTED":
            continue
        path = Path(row["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Source hash mismatch")
    return report["sources"]


def run(output: Path, source_root: Path, intentions: Path) -> dict:
    sources = verified_sources(source_root)
    required = ["ttf_scope", "xfab_2023", "xfab_2024", "xfab_2025"]
    if any(sources.get(key, {}).get("status") != "ARCHIVED_NOT_PROMOTED" for key in required):
        raise ValueError("Missing required sources")
    if any(sources[key]["sha256"] != REVIEWED_HASHES[key] for key in required):
        raise ValueError("Documents differ from manually reviewed sources")
    priorities = priority_table(pd.read_parquet(intentions))
    output.mkdir(parents=True, exist_ok=False)
    priorities.to_json(output / "tax_priorities.json", orient="records", indent=2)
    # Manual reading of these exact reports. End-of-year snapshots do not
    # establish continuous fiscal eligibility for every settlement in a year.
    review = {
        "symbol": "XFAB.PA", "isin": "BE0974310428",
        "tax": {"state": "FOREIGN_ORDINARY_SCOPE_EVIDENCE_REVIEWED_ANNUAL_CONTINUITY_PENDING",
                "annual_2024_2025_eligibility_promoted": False,
                "reason": "Belgian registered office and direct ordinary share documented; continuous seat history not established",
                "pages": {"xfab_2023": [61, 127, 129], "xfab_2024": [57, 132, 134],
                          "xfab_2025": [58, 156]},
                "legal_scope": "ttf_scope paragraphs 80-90; foreign issuer exceptions must be checked"},
        "corporate_actions": {
            "dividends_2024_2025": "NO_DIVIDENDS_RESOLVED_OR_PAID_ISSUER_ANNUAL_REVIEWED",
            "dividend_pages": {"xfab_2024": [58], "xfab_2025": [59]},
            "issued_shares_at_year_ends": 130781669,
            "complete_independent_event_coverage": False,
            "unqualified_families": ["splits", "rights", "capital_repayments", "mergers",
                                     "spin_offs", "delistings", "share_class_changes"],
            "available_at_for_strategy": None,
            "reason": "Retrospective reports collected in 2026; not a historical PIT feed"},
    }
    result = {"status": "PARTIAL_PRIORITY_REVIEW_NO_ECONOMIC_GO", "priority_symbols": len(priorities),
              "reviewed": [review], "sources": sources,
              "intentions": {"path": str(intentions), "sha256": hashlib.sha256(intentions.read_bytes()).hexdigest()},
              "canonical_writes": False, "tax_rows_promoted": 0, "economic_paths_qualified": 0}
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--intentions", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.sources, args.intentions)))
