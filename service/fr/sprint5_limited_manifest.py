"""Construit le manifeste limité Sprint 5 France, sans écriture canonique.

Le manifeste sépare strictement :
- la preuve officielle nécessaire au canonique ;
- une convention de recherche conservatrice J+1 ;
- les simples barres de staging, qui ne sont jamais promues implicitement.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import yaml

from service.fr.eodhd_backfill import _atomic_json
from service.fr.esma_firds_bar_coverage import valid_bar

POLICY_VERSION = "fr_s5_limited_v1"
TERMINAL_EVENTS = {"TermntdRcrd", "CancRcrd"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _price_windows(yahoo_report: dict, euronext_dir: Path,
                   euronext_delisted_report: dict | None = None) -> dict[str, list[dict]]:
    windows: dict[str, list[dict]] = defaultdict(list)
    for result in yahoo_report.get("results", []):
        first, last = result.get("first_overlap"), result.get("last_overlap")
        if not first or not last:
            continue
        windows[result["symbol"]].append({
            "source": "YAHOO_INDEPENDENT",
            "official": False,
            "from": first,
            "to": last,
            "difference_days": {
                row["date"] for row in result.get("price_difference_examples", [])
            },
            "difference_count": int(result.get("price_difference_count") or 0),
            "examples_complete": int(result.get("price_difference_count") or 0)
                                 <= len(result.get("price_difference_examples", [])),
        })
    for path in sorted(euronext_dir.glob("*_price_audit.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        first, last = report.get("first_overlap"), report.get("last_overlap")
        if not first or not last:
            continue
        symbol = path.name.removesuffix("_price_audit.json") + ".PA"
        windows[symbol].append({
            "source": "EURONEXT_OFFICIAL_EXPORT",
            "official": True,
            "from": first,
            "to": last,
            "difference_days": {
                row["date"] for row in report.get("difference_examples", [])
            },
            "difference_count": int(report.get("difference_count") or 0),
            "examples_complete": int(report.get("difference_count") or 0)
                                 <= len(report.get("difference_examples", [])),
        })
    for result in (euronext_delisted_report or {}).get("results", []):
        exact_dates = set(result.get("corroborated_dates", []))
        if result.get("status") != "COMPLETED" or not exact_dates:
            continue
        windows[result["symbol"]].append({
            "source": "EURONEXT_OFFICIAL_DELISTED",
            "official": bool((euronext_delisted_report or {}).get("tls_verified")),
            "exact_dates": exact_dates,
        })
    return windows


def price_proof(symbol: str, day: str, windows: dict[str, list[dict]]) -> tuple[bool, bool, list[str]]:
    sources = []
    official = False
    for window in windows.get(symbol, []):
        if "exact_dates" in window:
            if day in window["exact_dates"]:
                sources.append(window["source"])
                official = official or bool(window["official"])
            continue
        if not window["examples_complete"]:
            continue
        if window["from"] <= day <= window["to"] and day not in window["difference_days"]:
            sources.append(window["source"])
            official = official or bool(window["official"])
    return bool(sources), official, sorted(set(sources))


def reference_state(day: str, markets: list[dict], missing_days: set[str],
                    first_full: str) -> dict:
    if day < first_full:
        return {"verified": False, "reason": "BEFORE_INITIAL_FULL", "mic": None}
    if day in missing_days:
        return {"verified": False, "reason": "MISSING_DELTA_PUBLICATION_DAY", "mic": None}
    applicable = []
    for market in markets:
        versions = [row for row in market.get("versions", [])
                    if row["asof_from"] <= day
                    and (row.get("asof_to") is None or day <= row["asof_to"])]
        if len(versions) > 1:
            return {"verified": False, "reason": "AMBIGUOUS_REFERENCE_VERSION", "mic": market["mic"]}
        if versions:
            applicable.append((market["mic"], versions[0]))
    active = [(mic, row) for mic, row in applicable if row.get("event") not in TERMINAL_EVENTS]
    equities = [(mic, row) for mic, row in active
                if isinstance(row.get("cfi"), str) and row["cfi"].upper().startswith("E")]
    if len(equities) == 1:
        mic, row = equities[0]
        return {"verified": True, "reason": None, "mic": mic,
                "cfi": row.get("cfi"), "source_file": row.get("source_file")}
    if len(equities) > 1:
        return {"verified": False, "reason": "MULTIPLE_ACTIVE_TARGET_MICS", "mic": None}
    if active:
        return {"verified": False, "reason": "NON_EQUITY_CFI", "mic": active[0][0]}
    return {"verified": False, "reason": "NO_OBSERVED_ACTIVE_TARGET_MIC", "mic": None}


def passes_survivorship_gate(status_counts: Counter, total: int, *,
                              minimum_delisted: int,
                              minimum_delisted_ratio: float) -> bool:
    delisted = int(status_counts.get("delisted", 0))
    ratio = delisted / total if total else 0.0
    return delisted >= minimum_delisted and ratio >= minimum_delisted_ratio


def _bar_rows(root: Path, symbol: str) -> Iterable[dict]:
    key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
    metadata_path = root / "symbols" / f"{key}.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"archive symbole absente : {symbol}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("symbol") != symbol or metadata.get("status") != "COMPLETED":
        raise ValueError(f"archive symbole incomplète : {symbol}")
    with gzip.open(root / metadata["payloads"]["eod"]["file"], "rt", encoding="utf-8") as stream:
        yield from json.load(stream)


def build_manifest(*, history: dict, subset: dict, archive_root: Path,
                   yahoo_report: dict, euronext_dir: Path,
                   euronext_delisted_report: dict | None = None, policy: dict,
                   output_jsonl_gz: Path) -> dict:
    if policy.get("policy_version") != POLICY_VERSION:
        raise ValueError("version de politique Sprint 5 inattendue")
    start, end = policy["start_date"].isoformat(), policy["end_date"].isoformat()
    if end > history["end"]:
        raise ValueError("politique au-delà du rejeu FIRDS")
    subset_rows = {row["symbol"]: row for row in subset["symbols"]
                   if row["status"] == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"}
    windows = _price_windows(yahoo_report, euronext_dir, euronext_delisted_report)
    missing_days = set(history.get("missing_delta_days", []))
    counters = Counter()
    research_rejection_counts = Counter()
    strict_rejection_counts = Counter()
    price_proof_counts = Counter()
    by_year: dict[str, Counter] = defaultdict(Counter)
    symbol_summary: dict[str, Counter] = defaultdict(Counter)
    eligible_days: dict[str, set[str]] = defaultdict(set)
    output_jsonl_gz.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_jsonl_gz.with_suffix(output_jsonl_gz.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", newline="\n") as sink:
        for symbol in history["symbols"]:
            code = symbol["symbol"]
            candidate = subset_rows.get(code)
            if candidate is None:
                continue
            provider_split_free = int(candidate.get("splits") or 0) == 0
            for bar in _bar_rows(archive_root, code):
                day = bar.get("date")
                if not isinstance(day, str) or not start <= day <= end:
                    continue
                reference = reference_state(
                    day, symbol["market_reference"], missing_days, history["start"])
                bar_ok = valid_bar(bar)
                corroborated, official_price, proof_sources = price_proof(code, day, windows)
                identity_verified = bool(reference["verified"])
                venue_verified = identity_verified
                historical_pit_verified = False
                corporate_action_verified = False
                research_reasons = []
                if not bar_ok:
                    research_reasons.append("INVALID_OR_ZERO_VOLUME_BAR")
                if not identity_verified:
                    research_reasons.append(reference["reason"])
                if not corroborated:
                    research_reasons.append("INDEPENDENT_PRICE_CORROBORATION_MISSING")
                if not provider_split_free:
                    research_reasons.append("PROVIDER_SPLIT_HISTORY_PRESENT")
                research_eligible = not research_reasons
                strict_reasons = list(research_reasons)
                if not official_price:
                    strict_reasons.append("OFFICIAL_PRICE_VERIFICATION_MISSING")
                if not historical_pit_verified:
                    strict_reasons.append("HISTORICAL_PIT_PROOF_MISSING")
                if not corporate_action_verified:
                    strict_reasons.append("CORPORATE_ACTION_ECONOMIC_PROOF_MISSING")
                strict_eligible = not strict_reasons
                decision = ("CANONICAL_STRICT_ELIGIBLE" if strict_eligible else
                            "RESEARCH_J1_ELIGIBLE" if research_eligible else "REJECTED")
                row = {
                    "policy_version": POLICY_VERSION,
                    "symbol": code,
                    "isin": symbol["isin"],
                    "session_date": day,
                    "mic": reference.get("mic"),
                    "cfi": reference.get("cfi"),
                    "bar_valid": bar_ok,
                    "identity_verified": identity_verified,
                    "venue_interval_verified": venue_verified,
                    "price_corroborated": corroborated,
                    "price_verified_official": official_price,
                    "price_proof_sources": proof_sources,
                    "historical_pit_verified": historical_pit_verified,
                    "research_available_lag_sessions": 1,
                    "provider_split_free": provider_split_free,
                    "corporate_action_verified": corporate_action_verified,
                    "economic_return_ready": False,
                    "research_j1_eligible": research_eligible,
                    "canonical_strict_eligible": strict_eligible,
                    "decision": decision,
                    "research_rejection_reasons": sorted(set(research_reasons)),
                    "strict_rejection_reasons": sorted(set(strict_reasons)),
                }
                sink.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                counters[decision] += 1
                counters["TOTAL_ROWS"] += 1
                research_rejection_counts.update(set(research_reasons))
                strict_rejection_counts.update(set(strict_reasons))
                price_proof_counts.update(proof_sources or ["NONE"])
                by_year[day[:4]][decision] += 1
                symbol_summary[code][decision] += 1
                if research_eligible:
                    eligible_days[day].add(code)
    temporary.replace(output_jsonl_gz)
    minimum = int(policy["research_j1"]["minimum_symbols_per_session"])
    cross_sections = sorted(len(symbols) for symbols in eligible_days.values())
    qualifying_sessions = sum(value >= minimum for value in cross_sections)
    def percentile(fraction: float) -> int:
        if not cross_sections:
            return 0
        index = round((len(cross_sections) - 1) * fraction)
        return cross_sections[index]
    research_symbols = sorted(code for code, counts in symbol_summary.items()
                              if counts["RESEARCH_J1_ELIGIBLE"] > 0)
    strict_symbols = sorted(code for code, counts in symbol_summary.items()
                            if counts["CANONICAL_STRICT_ELIGIBLE"] > 0)
    research_status_counts = Counter(
        subset_rows[code].get("provider_status_current", "unknown")
        for code in research_symbols)
    delisted_count = research_status_counts["delisted"]
    delisted_ratio = delisted_count / len(research_symbols) if research_symbols else 0.0
    minimum_delisted = int(policy["research_j1"].get("minimum_delisted_symbols", 0))
    minimum_delisted_ratio = float(policy["research_j1"].get("minimum_delisted_ratio", 0.0))
    survivorship_gate = passes_survivorship_gate(
        research_status_counts, len(research_symbols),
        minimum_delisted=minimum_delisted,
        minimum_delisted_ratio=minimum_delisted_ratio)
    verdict = ("GO_CANONICAL_STRICT" if strict_symbols else
               "GO_RESEARCH_J1" if qualifying_sessions and survivorship_gate else
               "NO_GO_RESEARCH_HISTORICAL_SURVIVORSHIP_BIAS"
               if qualifying_sessions and not survivorship_gate else
               "NO_GO_LIMITED_CROSS_SECTION_OR_PROOFS")
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "policy_version": POLICY_VERSION,
        "period": {"start": start, "end": end},
        "verdict": verdict,
        "canonical_writes_performed": False,
        "counts": dict(counters),
        "research_rejection_reasons": dict(research_rejection_counts.most_common()),
        "strict_rejection_reasons": dict(strict_rejection_counts.most_common()),
        "price_proof_counts": dict(price_proof_counts.most_common()),
        "by_year": {year: dict(counts) for year, counts in sorted(by_year.items())},
        "candidate_symbols": len(subset_rows),
        "research_j1_symbols": research_symbols,
        "research_j1_symbol_count": len(research_symbols),
        "research_j1_symbols_by_provider_status": dict(research_status_counts),
        "survivorship_gate": {
            "passed": survivorship_gate,
            "delisted_symbols": delisted_count,
            "delisted_ratio": delisted_ratio,
            "minimum_delisted_symbols": minimum_delisted,
            "minimum_delisted_ratio": minimum_delisted_ratio,
        },
        "canonical_strict_symbols": strict_symbols,
        "canonical_strict_symbol_count": len(strict_symbols),
        "research_sessions_observed": len(eligible_days),
        "research_cross_section": {
            "minimum": min(cross_sections) if cross_sections else 0,
            "median": percentile(0.50),
            "p95": percentile(0.95),
            "maximum": max(cross_sections) if cross_sections else 0,
        },
        "research_sessions_meeting_minimum_cross_section": qualifying_sessions,
        "minimum_symbols_per_session": minimum,
        "manifest": {"path": str(output_jsonl_gz), "sha256": _sha256(output_jsonl_gz)},
        "limitations": [
            "RESEARCH_J1 est une hypothèse conservatrice, pas une preuve PIT historique",
            "Yahoo corrobore des prix mais n'est pas une source officielle",
            "Le transport Python Euronext du POC n'est pas validé par certifi ; ses lignes ne valent pas preuve officielle canonique",
            "La source publique Euronext ne couvre qu'une fenêtre récente d'environ deux ans",
            "Les rendements économiques et corporate actions ne sont pas validés",
            "Aucune table canonique, aucun modèle et aucun backtest ne sont alimentés",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--subset", type=Path, default=Path(
        "artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json"))
    parser.add_argument("--archive-root", type=Path, default=Path(
        "artifacts/fr/eodhd/backfill_2016"))
    parser.add_argument("--yahoo-report", type=Path, default=Path(
        "artifacts/fr/yahoo_daily_reference/pilot_10_active_2018_2025.json"))
    parser.add_argument("--euronext-dir", type=Path, default=Path(
        "artifacts/fr/euronext_daily_reference"))
    parser.add_argument("--euronext-delisted-report", type=Path, default=Path(
        "artifacts/fr/euronext_delisted_reference/report.json"))
    parser.add_argument("--policy", type=Path, default=Path(
        "config/markets/fr_sprint5_limited.yaml"))
    parser.add_argument("--output-root", type=Path, default=Path(
        "artifacts/fr/sprint5_limited_2018_2026"))
    args = parser.parse_args()
    history = json.loads(args.history.read_text(encoding="utf-8"))
    subset = json.loads(args.subset.read_text(encoding="utf-8"))
    yahoo_report = json.loads(args.yahoo_report.read_text(encoding="utf-8"))
    euronext_delisted_report = (
        json.loads(args.euronext_delisted_report.read_text(encoding="utf-8"))
        if args.euronext_delisted_report.is_file() else {}
    )
    policy = yaml.safe_load(args.policy.read_text(encoding="utf-8"))
    manifest_path = args.output_root / "bar_manifest.jsonl.gz"
    report = build_manifest(
        history=history, subset=subset, archive_root=args.archive_root,
        yahoo_report=yahoo_report, euronext_dir=args.euronext_dir,
        euronext_delisted_report=euronext_delisted_report,
        policy=policy, output_jsonl_gz=manifest_path)
    report["inputs"] = {
        "history": {"path": str(args.history), "sha256": _sha256(args.history)},
        "subset": {"path": str(args.subset), "sha256": _sha256(args.subset)},
        "yahoo_report": {"path": str(args.yahoo_report), "sha256": _sha256(args.yahoo_report)},
        "euronext_delisted_report": {
            "path": str(args.euronext_delisted_report),
            "sha256": _sha256(args.euronext_delisted_report)
            if args.euronext_delisted_report.is_file() else None,
        },
        "policy": {"path": str(args.policy), "sha256": _sha256(args.policy)},
    }
    _atomic_json(args.output_root / "report.json", report)
    (args.output_root / "research_j1_symbols.txt").write_text(
        ",".join(report["research_j1_symbols"]), encoding="utf-8")
    (args.output_root / "canonical_strict_symbols.txt").write_text(
        ",".join(report["canonical_strict_symbols"]), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "verdict", "counts", "research_j1_symbol_count",
        "canonical_strict_symbol_count",
        "research_sessions_meeting_minimum_cross_section")}, ensure_ascii=False))


if __name__ == "__main__":
    main()




