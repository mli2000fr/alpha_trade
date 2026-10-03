"""Identités, benchmark prix et secteurs explicitement inconnus FR (Sprint 6-C).

Les identités sont de recherche : aucun instrument canonique n'est créé.
Le benchmark utilise les constituants connus avant la séance et publie J+1.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import logging
import math
import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from common.market_calendar import get_market_calendar
from service.fr.sprint5_subset_audit import valid_isin
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256
from service.fr.universe_liquidity_6b import _iter_manifest, _load_symbol_bars

LOGGER = logging.getLogger(__name__)


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_policy(path: Path) -> dict[str, Any]:
    policy = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if (policy.get("schema_version"), policy.get("market_code"), policy.get("database_alias")) != (
        1,
        "FR_EQ",
        "fr_primary",
    ):
        raise ValueError("Contrat 6-C doit cibler FR_EQ/fr_primary")
    if any(policy.get(key) for key in ("canonical_promotion", "tradable_enabled", "serving_enabled")):
        raise ValueError("6-C est limité à la recherche")
    benchmark = policy["benchmark"]
    if benchmark.get("methodology") != "equal_weight_lagged_training_eligible_raw_close":
        raise ValueError("Méthodologie benchmark non prise en charge")
    if int(benchmark["min_constituents"]) < 2 or not 0 < float(benchmark["min_return_coverage"]) <= 1:
        raise ValueError("Gates benchmark invalides")
    if float(benchmark["initial_level"]) <= 0:
        raise ValueError("Niveau initial benchmark invalide")
    if policy["sector"].get("historical_state") != "UNKNOWN":
        raise ValueError("Aucune appartenance sectorielle historique validée")
    return policy


def build_identities(symbols: list[str], history: dict[str, Any]) -> list[dict[str, Any]]:
    """Résolution par ISIN, les versions MIC restent dans la preuve historique."""
    records = {row["symbol"]: row for row in history["symbols"]}
    isin_counts = Counter(records[s].get("isin") for s in symbols if s in records)
    result = []
    for symbol in sorted(set(symbols)):
        record = records.get(symbol) or {}
        isin = str(record.get("isin") or "")
        versions = [version for market in record.get("market_reference", []) for version in market.get("versions", [])]
        version_isins = {str(v["isin"]) for v in versions if v.get("isin")}
        reasons = []
        if not valid_isin(isin):
            reasons.append("MISSING_OR_INVALID_ISIN")
        if isin and isin_counts[isin] > 1:
            reasons.append("SHARED_ISIN_BETWEEN_PROVIDER_SYMBOLS")
        if version_isins - {isin}:
            reasons.append("HISTORICAL_ISIN_CONFLICT")
        state = "VERIFIED_RESEARCH" if not reasons else ("UNKNOWN" if not isin else "AMBIGUOUS")
        uid = (
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"alpha-trade:FR_EQ:research:isin:{isin}"))
            if state == "VERIFIED_RESEARCH"
            else None
        )
        mics = sorted({str(m["mic"]) for m in record.get("market_reference", [])})
        result.append(
            {
                "provider_symbol": symbol,
                "research_uid": uid,
                "isin": isin or None,
                "instrument_id": None,
                "identity_state": state,
                "primary_reason": ";".join(reasons) if reasons else "UNIQUE_ISIN_WITH_ESMA_VERSIONED_REFERENCE",
                "mics": mics,
                "provider_status_current": record.get("provider_status_current"),
                "market_reference": record.get("market_reference", []),
                "sector_state": "UNKNOWN",
                "sector_code": None,
            }
        )
    return result


def sector_asof(memberships: list[dict], symbol: str, decision_at: datetime) -> dict:
    """Consomme une observation seulement après sa disponibilité réelle.

    Aucun secteur courant ne peut être rétropolé sur l'historique.
    """
    decision_at = decision_at.astimezone(UTC) if decision_at.tzinfo else decision_at.replace(tzinfo=UTC)
    eligible = []
    for row in memberships:
        if row.get("provider_symbol") != symbol or not row.get("sector_code"):
            continue
        observed = datetime.fromisoformat(str(row["observed_at"]).replace("Z", "+00:00"))
        available = datetime.fromisoformat(str(row["available_at"]).replace("Z", "+00:00"))
        if observed.tzinfo is None or available.tzinfo is None or available < observed:
            raise ValueError("Disponibilité sectorielle invalide")
        day = decision_at.date().isoformat()
        if (
            available <= decision_at
            and str(row["valid_from"]) <= day
            and (not row.get("valid_to") or day <= str(row["valid_to"]))
        ):
            eligible.append(row)
    if not eligible:
        return {"sector_state": "UNKNOWN", "sector_code": None}
    latest = max(datetime.fromisoformat(str(r["available_at"]).replace("Z", "+00:00")) for r in eligible)
    candidates = [
        r for r in eligible if datetime.fromisoformat(str(r["available_at"]).replace("Z", "+00:00")) == latest
    ]
    if len({(r.get("taxonomy"), r["sector_code"]) for r in candidates}) != 1:
        return {"sector_state": "AMBIGUOUS", "sector_code": None}
    return {
        "sector_state": "KNOWN",
        "sector_code": candidates[0]["sector_code"],
        "taxonomy": candidates[0].get("taxonomy"),
    }


def build_benchmark(
    snapshots: list[dict],
    bars: dict[str, dict[str, dict]],
    identities: dict[str, dict],
    sessions: list[date],
    config: dict,
) -> tuple[list[dict], list[dict]]:
    """Constituants pour J = snapshots décision J construits à J-1.

    Un rendement exige deux clôtures sur séances consécutives, sans pont
    au-dessus d'une suspension, d'un trou ou d'une exclusion du manifeste.
    """
    by_decision = defaultdict(list)
    observable = {(r["provider_symbol"], r["source_session_date"]) for r in snapshots}
    for row in snapshots:
        by_decision[row["decision_session_date"]]
        if (
            row["training_state"] == "ELIGIBLE"
            and identities.get(row["provider_symbol"], {}).get("identity_state") == "VERIFIED_RESEARCH"
        ):
            by_decision[row["decision_session_date"]].append(row)
    index = {day.isoformat(): i for i, day in enumerate(sessions)}
    daily, constituents = [], []
    cumulative = float(config["initial_level"])
    segment = 0
    previous_known = False
    for day_text, rows in sorted(by_decision.items()):
        i = index.get(day_text)
        if i is None or i == 0 or i + 1 >= len(sessions):
            raise ValueError(f"Séance benchmark hors calendrier : {day_text}")
        previous_day = sessions[i - 1].isoformat()
        returns = []
        member_start = len(constituents)
        if len({r["provider_symbol"] for r in rows}) != len(rows):
            raise ValueError("Constituant benchmark dupliqué")
        for row in rows:
            symbol = row["provider_symbol"]
            if row["source_session_date"] != previous_day:
                raise ValueError("Composition non disponible avant la séance benchmark")
            current = bars.get(symbol, {}).get(day_text) or {}
            previous = bars.get(symbol, {}).get(previous_day) or {}
            c, p = float(current.get("close") or 0), float(previous.get("close") or 0)
            valid = (
                (symbol, day_text) in observable
                and (symbol, previous_day) in observable
                and math.isfinite(c)
                and math.isfinite(p)
                and c > 0
                and p > 0
            )
            value = c / p - 1 if valid else None
            if value is not None:
                returns.append(value)
            constituents.append(
                {
                    "source_session_date": day_text,
                    "provider_symbol": symbol,
                    "research_uid": identities[symbol]["research_uid"],
                    "eligibility_source_session": previous_day,
                    "price_return": value,
                    "return_state": "KNOWN" if valid else "UNKNOWN",
                    "target_weight": 1 / len(rows),
                }
            )
        coverage = len(returns) / len(rows) if rows else 0.0
        known = len(rows) >= int(config["min_constituents"]) and coverage >= float(config["min_return_coverage"])
        value = sum(returns) / len(returns) if known else None
        for member in constituents[member_start:]:
            member["effective_return_weight"] = (
                1 / len(returns) if known and member["return_state"] == "KNOWN" else None
            )
        if known:
            if not previous_known:
                segment += 1
                cumulative = float(config["initial_level"])
            cumulative *= 1 + value
        daily.append(
            {
                "source_session_date": day_text,
                "decision_session_date": sessions[i + 1].isoformat(),
                "constituent_count": len(rows),
                "valid_return_count": len(returns),
                "return_coverage": coverage,
                "price_return": value,
                "index_level": cumulative if known else None,
                "segment_id": segment if known else None,
                "benchmark_state": "KNOWN" if known else "UNKNOWN",
                "primary_reason": "GATES_PASSED" if known else "INSUFFICIENT_CONSTITUENTS_OR_COVERAGE",
            }
        )
        previous_known = known
    return daily, constituents


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with (
        temporary.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
        io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as stream,
    ):
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def build_artifact(policy: dict, output: Path) -> dict:
    paths = {key: resolve_path(policy[key]) for key in ("source_report", "identity_history", "liquidity_report")}
    source, history, liquidity = [json.loads(paths[key].read_text(encoding="utf-8")) for key in paths]
    if source.get("verdict") != "GO_RESEARCH_J1" or source.get("canonical_writes_performed") is not False:
        raise ValueError("Source Sprint 5 incompatible")
    if liquidity.get("verdict") != "GO_6B_TRAINING_UNIVERSE":
        raise ValueError("Source Sprint 6-B incompatible")
    snapshot_path = resolve_path(liquidity["snapshot_path"])
    if (
        _sha256(snapshot_path) != liquidity["snapshot_sha256"]
        or liquidity["source_manifest_sha256"] != source["manifest"]["sha256"]
    ):
        raise ValueError("Provenances Sprint 5/6-B divergentes")
    if not history.get("complete") or _sha256(paths["identity_history"]) != source["inputs"]["history"]["sha256"]:
        raise ValueError("Historique d'identité divergent du GO limité Sprint 5")
    identities = build_identities(source["research_j1_symbols"], history)
    identity_map = {r["provider_symbol"]: r for r in identities}
    snapshots = list(_iter_manifest(snapshot_path))
    LOGGER.info("6-C snapshots chargés=%s identités=%s", len(snapshots), len(identities))
    if len(snapshots) != int(liquidity["snapshot_count"]):
        raise ValueError("Nombre snapshots 6-B divergent")
    symbols = sorted({r["provider_symbol"] for r in snapshots if r["training_state"] == "ELIGIBLE"})
    bars = {}
    for number, symbol in enumerate(symbols, 1):
        bars[symbol] = _load_symbol_bars(resolve_path(liquidity["archive_root"]), symbol)
        if number % 25 == 0 or number == len(symbols):
            LOGGER.info("6-C archives prix chargées=%s/%s", number, len(symbols))
    dates = [date.fromisoformat(r["decision_session_date"]) for r in snapshots]
    sessions = get_market_calendar("FR_EQ").session_dates(
        min(dates) - timedelta(days=10), max(dates) + timedelta(days=20)
    )
    daily, constituents = build_benchmark(snapshots, bars, identity_map, sessions, policy["benchmark"])
    LOGGER.info("6-C benchmark séances=%s observations constituants=%s", len(daily), len(constituents))
    fingerprint = _fingerprint(policy)
    hashes = {key: _sha256(path) for key, path in paths.items()}
    # Rapport 6-B comporte des horodatages : l'identité du run dépend des données.
    source_hash = _fingerprint(
        {
            "manifest": liquidity["source_manifest_sha256"],
            "snapshots": liquidity["snapshot_sha256"],
            "identity": hashes["identity_history"],
        }
    )
    run_id = f"fr6c-{fingerprint[:16]}-{source_hash[:12]}"
    output.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, rows in (
        ("identities", identities),
        ("benchmark_daily", daily),
        ("benchmark_constituents", constituents),
    ):
        path = output / f"{name}.jsonl.gz"
        _write_rows(path, rows)
        files[name] = {"path": str(path.resolve()), "sha256": _sha256(path), "rows": len(rows)}
    counts = Counter(r["identity_state"] for r in identities)
    benchmark_counts = Counter(r["benchmark_state"] for r in daily)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "verdict": "GO_6C_RESEARCH_PRICE_ONLY"
        if counts["VERIFIED_RESEARCH"] == len(identities) and benchmark_counts["KNOWN"]
        else "BLOCKED_6C_REFERENCE",
        "policy_version": policy["policy_version"],
        "policy_fingerprint": fingerprint,
        "source_fingerprint": source_hash,
        "source_hashes": hashes,
        "identity_evidence_scope": "SPRINT5_LIMITED_PUBLICATION_ASOF_RESEARCH_ONLY",
        "esma_missing_delta_days": len(history.get("missing_delta_days", [])),
        "esma_publication_continuity_confirmed": bool(history.get("publication_continuity_confirmed")),
        "market_code": "FR_EQ",
        "liquidity_run_id": liquidity["liquidity_run_id"],
        "identity_counts": dict(counts),
        "multiple_mic_symbols": sum(len(r["mics"]) > 1 for r in identities),
        "benchmark": {
            **policy["benchmark"],
            "counts": dict(benchmark_counts),
            "first_known_session": next(
                (r["source_session_date"] for r in daily if r["benchmark_state"] == "KNOWN"), None
            ),
            "last_known_session": next(
                (r["source_session_date"] for r in reversed(daily) if r["benchmark_state"] == "KNOWN"), None
            ),
            "return_basis": "RAW_PRICE_ONLY_NOT_TOTAL_RETURN",
            "availability": "NEXT_XPAR_SESSION",
        },
        "sector": {**policy["sector"], "unknown_symbols": len(identities), "historical_neutralisation_enabled": False},
        "files": files,
        "canonical_writes_performed": False,
        "database_writes_performed": False,
        "tradable_enabled": False,
        "serving_enabled": False,
        "next_gate": "SPRINT_7_FR_PRICE_ONLY_PANEL",
    }
    _atomic_json(output / "report.json", report)
    return report


def persist(report: dict) -> None:
    """Upserts isolés dans alpha_trade_fr, avec contrôle de contenu à la fin."""
    from sqlalchemy import create_engine, text

    from database.router import build_database_url

    engine = create_engine(build_database_url("fr_primary", "FR_EQ"), pool_pre_ping=True)
    run = report["run_id"]
    tables = {
        "identities": "fr_research_identities",
        "benchmark_daily": "fr_research_benchmark_daily",
        "benchmark_constituents": "fr_research_benchmark_constituents",
    }
    fields = {
        "identities": ["provider_symbol", "research_uid", "isin", "identity_state", "primary_reason", "sector_state"],
        "benchmark_daily": [
            "source_session_date",
            "decision_session_date",
            "constituent_count",
            "valid_return_count",
            "return_coverage",
            "price_return",
            "index_level",
            "segment_id",
            "benchmark_state",
            "primary_reason",
        ],
        "benchmark_constituents": [
            "source_session_date",
            "provider_symbol",
            "research_uid",
            "eligibility_source_session",
            "price_return",
            "return_state",
            "target_weight",
        ],
    }
    try:
        with engine.begin() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar() != "alpha_trade_fr":
                raise RuntimeError("Persistance 6-C refusée hors alpha_trade_fr")
            conn.execute(
                text(
                    "INSERT INTO fr_reference_runs(run_id,market_code,policy_version,policy_fingerprint,source_fingerprint,status,details_json) VALUES(:run,'FR_EQ',:version,:policy,:source,'RUNNING',:details) ON DUPLICATE KEY UPDATE status='RUNNING',completed_at=NULL,details_json=VALUES(details_json)"
                ),
                {
                    "run": run,
                    "version": report["policy_version"],
                    "policy": report["policy_fingerprint"],
                    "source": report["source_fingerprint"],
                    "details": json.dumps(report, ensure_ascii=False),
                },
            )
        for kind, table in tables.items():
            meta = report["files"][kind]
            path = Path(meta["path"])
            if _sha256(path) != meta["sha256"]:
                raise ValueError(f"Artefact 6-C corrompu : {kind}")
            columns = fields[kind] + ["details_json"]
            sql = text(
                f"INSERT INTO {table}(run_id,{','.join(columns)}) VALUES(:run,{','.join(':' + c for c in columns)}) ON DUPLICATE KEY UPDATE "
                + ",".join(f"{c}=VALUES({c})" for c in columns)
            )
            batch = []
            for row in _iter_manifest(path):
                batch.append(
                    {
                        "run": run,
                        **{c: row.get(c) for c in fields[kind]},
                        "details_json": json.dumps(row, ensure_ascii=False),
                    }
                )
                if len(batch) >= 3000:
                    with engine.begin() as conn:
                        conn.execute(sql, batch)
                    batch = []
            if batch:
                with engine.begin() as conn:
                    conn.execute(sql, batch)
            with engine.connect() as conn:
                if (
                    conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE run_id=:run"), {"run": run}).scalar()
                    != meta["rows"]
                ):
                    raise RuntimeError(f"Couverture SQL incomplète : {kind}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE fr_reference_runs SET status='COMPLETED',details_json=:details,completed_at=CURRENT_TIMESTAMP(6) WHERE run_id=:run"
                ),
                {"run": run, "details": json.dumps(report, ensure_ascii=False)},
            )
    except Exception:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE fr_reference_runs SET status='FAILED',completed_at=CURRENT_TIMESTAMP(6) WHERE run_id=:run"
                ),
                {"run": run},
            )
        raise
    finally:
        engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=Path("config/universe_fr_s6c.yaml"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/fr/sprint6c_reference"))
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    report = build_artifact(load_policy(args.policy), args.output_root)
    if report["verdict"] != "GO_6C_RESEARCH_PRICE_ONLY":
        print(json.dumps(report, ensure_ascii=False))
        raise SystemExit(2)
    if args.persist:
        report["database_writes_performed"] = True
        persist(report)
        _atomic_json(args.output_root / "report.json", report)
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("run_id", "verdict", "identity_counts", "benchmark", "sector", "database_writes_performed")
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
