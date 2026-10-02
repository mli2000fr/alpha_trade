"""Préqualification FR en lecture seule ; aucune promotion canonique implicite.

Un ISIN du snapshot et un suffixe PA ne prouvent ni l'identité historique ni le
MIC individuel. Le rapport sépare donc les candidats techniques du GO vérifié.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from database.router import build_database_url
from service.fr.eodhd_backfill import _atomic_json

RULE_VERSION = "fr_s5_subset_v1"
MIN_VALID_BARS = 504


def valid_isin(value: str | None) -> bool:
    """Contrôle de forme et chiffre ISO 6166 ; pas une preuve d'identité."""
    if not value:
        return False
    value = value.strip().upper()
    if len(value) != 12 or not value[:2].isalpha() or not value[-1].isdigit():
        return False
    if not all(char.isdigit() or ("A" <= char <= "Z") for char in value):
        return False
    digits = "".join(str(ord(char) - 55) if char.isalpha() else char for char in value)
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char) * (2 if index % 2 else 1)
        total += number // 10 + number % 10
    return total % 10 == 0


def qualify(rows: list[dict], bars: dict[str, dict], actions: dict[str, dict]) -> dict:
    """Sélectionne un pool à vérifier, sans prétendre valider le PIT historique."""
    by_isin = defaultdict(set)
    for row in rows:
        isin = (row.get("reported_isin") or "").strip().upper()
        if isin:
            by_isin[isin].add(row["provider_symbol"])
    results = []
    for row in sorted(rows, key=lambda item: item["provider_symbol"]):
        symbol = row["provider_symbol"]
        isin = (row.get("reported_isin") or "").strip().upper()
        bar = bars.get(symbol, {})
        action = actions.get(symbol, {})
        valid_bars = int(bar.get("valid_bars") or 0)
        years = int(bar.get("valid_years") or 0)
        splits = int(action.get("splits") or 0)
        reasons = []
        if not valid_isin(isin):
            reasons.append("ISIN_ABSENT_OR_INVALID")
        elif len(by_isin[isin]) != 1:
            reasons.append("ISIN_SHARED_BY_PROVIDER_CODES")
        if valid_bars < MIN_VALID_BARS or years < 2:
            reasons.append("INSUFFICIENT_VALID_HISTORY")
        if splits:
            reasons.append("SPLIT_NOT_INDEPENDENTLY_VALIDATED")
        if not reasons:
            status = "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"
            # Ces trois preuves ne se déduisent jamais du snapshot EODHD.
            reasons = ["HISTORICAL_IDENTITY_AND_LISTING_DATES_UNVERIFIED",
                       "INDIVIDUAL_MIC_UNVERIFIED", "INDEPENDENT_PRICE_CHECK_MISSING",
                       "HISTORICAL_PIT_PUBLICATION_UNVERIFIED"]
        else:
            status = "DEFERRED"
        results.append({"symbol": symbol, "isin_reported": isin or None,
                        "provider_status_current": row["provider_status"],
                        "verified_mic": row.get("verified_mic"),
                        "valid_bars": valid_bars, "valid_years": years,
                        "first_valid": str(bar.get("first_valid")) if bar.get("first_valid") else None,
                        "last_valid": str(bar.get("last_valid")) if bar.get("last_valid") else None,
                        "zero_volume_bars": int(bar.get("zero_volume_bars") or 0),
                        "other_bad_bars": int(bar.get("other_bad_bars") or 0),
                        "splits": splits, "dividends": int(action.get("dividends") or 0),
                        "status": status, "reasons": reasons})
    counts = Counter(item["status"] for item in results)
    candidate_status = Counter(item["provider_status_current"] for item in results
                               if item["status"] == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS")
    candidates_starting_2016 = Counter(
        item["provider_status_current"] for item in results
        if item["status"] == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"
        and item["first_valid"] and item["first_valid"] <= "2016-12-31")
    reason_counts = Counter(reason for item in results for reason in item["reasons"])
    pilot = []
    for provider_status in ("active", "delisted"):
        stratum = [item for item in results
                   if item["status"] == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"
                   and item["provider_status_current"] == provider_status]
        stratum.sort(key=lambda item: hashlib.sha256(
            f"{RULE_VERSION}:{item['symbol']}".encode("utf-8")).hexdigest())
        pilot.extend(item["symbol"] for item in stratum[:10])
    return {"rule_version": RULE_VERSION, "min_valid_bars": MIN_VALID_BARS,
            "summary": {"provider_codes": len(results), "verified_for_canonical": 0,
                        "candidate_pending_proofs": counts["CANDIDATE_REQUIRES_EXTERNAL_PROOFS"],
                        "deferred": counts["DEFERRED"],
                        "candidate_current_status": dict(candidate_status),
                        "candidates_with_bar_in_2016": sum(candidates_starting_2016.values()),
                        "candidates_with_bar_in_2016_by_current_status":
                            dict(candidates_starting_2016),
                        "reasons": dict(sorted(reason_counts.items()))},
            "pilot_symbols_preregistered": pilot,
            "warning": "Pool de vérification seulement : aucun instrument, listing ou prix canonique autorisé.",
            "symbols": results}


def run(output: Path) -> dict:
    engine = create_engine(build_database_url("fr_primary", "FR_EQ"), pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            database = conn.execute(text("SELECT DATABASE()")).scalar()
            if database != "alpha_trade_fr":
                raise RuntimeError(f"qualification FR refuse {database!r}")
            rows = [dict(row) for row in conn.execute(text("""
                SELECT provider_symbol,reported_isin,provider_status,verified_mic
                FROM fr_provider_universe_staging WHERE provider='EODHD'
            """)).mappings()]
            bars = {row["provider_symbol"]: dict(row) for row in conn.execute(text("""
                SELECT provider_symbol,
                  SUM(quality_code='VALID') AS valid_bars,
                  COUNT(DISTINCT CASE WHEN quality_code='VALID' THEN YEAR(session_date) END) AS valid_years,
                  MIN(CASE WHEN quality_code='VALID' THEN session_date END) AS first_valid,
                  MAX(CASE WHEN quality_code='VALID' THEN session_date END) AS last_valid,
                  SUM(quality_code='ZERO_VOLUME') AS zero_volume_bars,
                  SUM(quality_code NOT IN ('VALID','ZERO_VOLUME')) AS other_bad_bars
                FROM fr_provider_bars_staging WHERE provider='EODHD'
                GROUP BY provider_symbol
            """)).mappings()}
            actions = {row["provider_symbol"]: dict(row) for row in conn.execute(text("""
                SELECT provider_symbol,
                  SUM(action_type='splits') AS splits,
                  SUM(action_type='div') AS dividends
                FROM fr_provider_actions_staging WHERE provider='EODHD'
                GROUP BY provider_symbol
            """)).mappings()}
    finally:
        engine.dispose()
    report = qualify(rows, bars, actions)
    report["generated_at"] = datetime.now(UTC).isoformat()
    _atomic_json(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json"))
    args = parser.parse_args()
    report = run(args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
