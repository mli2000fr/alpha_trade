"""Vérification reproductible du gate Sprint 5 France (lecture seule)."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from database.router import build_database_url
from service.fr.eodhd_backfill import _atomic_json
from service.fr.load_eodhd_staging import CLASSIFIER_VERSION


def evaluate(root: Path) -> dict:
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    quality = json.loads((root / "quality_report.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "universe.json").read_text(encoding="utf-8"))
    records = [{**row, "provider_status": status} for status in ("active", "delisted")
               for row in manifest[status] if row.get("Type") == "Common Stock"
               and row.get("Currency") == "EUR" and row.get("Code")]
    by_isin = defaultdict(list)
    for record in records:
        if record.get("Isin"):
            by_isin[record["Isin"]].append(record["Code"])
    collisions = {isin: codes for isin, codes in by_isin.items() if len(codes) > 1}
    engine = create_engine(build_database_url("fr_primary", "FR_EQ"), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            actual = conn.execute(text("SELECT DATABASE()")).scalar()
            if actual != "alpha_trade_fr":
                raise RuntimeError(f"gate FR refuse {actual!r}")
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            def scalar(sql: str) -> int:
                return int(conn.execute(text(sql)).scalar() or 0)
            tables = {
                "raw_payloads": scalar("SELECT COUNT(*) FROM fr_raw_payloads WHERE provider='EODHD'"),
                "staging_symbols": scalar("SELECT COUNT(*) FROM fr_provider_universe_staging WHERE provider='EODHD'"),
                "staging_progress": scalar("SELECT COUNT(*) FROM fr_staging_progress WHERE provider='EODHD' AND status='COMPLETED'"),
                "staging_current_classifier": scalar("SELECT COUNT(*) FROM fr_staging_progress WHERE provider='EODHD' AND status='COMPLETED' AND classifier_version='fr_eod_v2'"),
                "staging_bars": scalar("SELECT COUNT(*) FROM fr_provider_bars_staging WHERE provider='EODHD'"),
                "staging_actions": scalar("SELECT COUNT(*) FROM fr_provider_actions_staging WHERE provider='EODHD'"),
                "verified_mic": scalar("SELECT COUNT(*) FROM fr_provider_universe_staging WHERE verified_mic='XPAR'"),
                "instruments": scalar("SELECT COUNT(*) FROM instruments"),
                "listings": scalar("SELECT COUNT(*) FROM instrument_listings"),
                "canonical_bars": scalar("SELECT COUNT(*) FROM stock_bars_daily"),
            }
            quality_counts = {row[0]: int(row[1]) for row in conn.execute(text("""
                SELECT quality_code,COUNT(*) FROM fr_provider_bars_staging
                WHERE provider='EODHD' GROUP BY quality_code
            """))}
    finally:
        engine.dispose()
    expected_payloads = summary["selected"] * 3
    flags = {
        "archive_complete": summary["failed"] == 0 and
                            summary["completed"] + summary["skipped"] == summary["selected"],
        "hashes_valid": quality["counts"].get("sha256_mismatch", 0) == 0,
        "raw_index_complete": tables["raw_payloads"] == expected_payloads,
        "staging_complete": (tables["staging_progress"] == expected_payloads and
                             tables["staging_current_classifier"] == expected_payloads and
                             tables["staging_symbols"] == summary["selected"] and
                             tables["staging_bars"] == quality["counts"].get("eod_rows", 0) and
                             tables["staging_actions"] == quality["counts"].get("splits_rows", 0) +
                             quality["counts"].get("div_rows", 0)),
        "identity_pit_verified": tables["verified_mic"] == summary["selected"] and
                                 not quality["counts"].get("missing_isin_symbols", 0) and not collisions,
        "canonical_complete": tables["canonical_bars"] > 0 and tables["listings"] > 0,
        "historical_publication_verified": False,
        "independent_price_reference_verified": False,
        "corporate_actions_economically_checked": False,
    }
    return {"generated_at": datetime.now(UTC).isoformat(),
            "verdict": "GO" if all(flags.values()) else "NO_GO_CANONICAL_AND_ML",
            "alembic_version": version, "classifier_version": CLASSIFIER_VERSION,
            "flags": flags, "tables": tables,
            "quality_codes": quality_counts,
            "provider_anomalies": {key: quality["counts"].get(key, 0) for key in
                                   ("placeholder_price", "bad_ohlc", "non_xpar_session",
                                    "empty_eod_symbols", "duplicate_date", "sha256_mismatch")},
            "identity": {"missing_isin": quality["counts"].get("missing_isin_symbols", 0),
                         "shared_isin_groups": len(collisions),
                         "shared_isin_rows": sum(map(len, collisions.values())),
                         "examples": dict(list(collisions.items())[:20])},
            "limitations": ["PA est un code de place fournisseur, pas le MIC individuel",
                            "Le statut actif/radié du snapshot n'est pas daté historiquement",
                            "Le backfill observé en 2026 ne prouve pas l'heure de publication passée",
                            "Le canonique doit exclure les lignes anormales et préserver les radiés",
                            "Adjusted close EODHD intègre les dividendes futurs par construction"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/eodhd/backfill_2016"))
    args = parser.parse_args()
    report = evaluate(args.root)
    _atomic_json(args.root / "sprint5_gate.json", report)
    print(json.dumps({"verdict": report["verdict"], "flags": report["flags"],
                      "tables": report["tables"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
