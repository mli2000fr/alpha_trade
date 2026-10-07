"""Sprint 6-B France : historique et liquidité PIT avec disponibilité J+1."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import groupby
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

from common.market_calendar import get_market_calendar
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


@dataclass(frozen=True)
class FRLiquidityPolicy:
    schema_version: int
    policy_version: str
    market_code: str
    database_alias: str
    calendar_id: str
    source_verdict: str
    source_policy_version: str
    source_report_path: str
    source_manifest_path: str
    archive_root: str
    start_date: date
    end_date: date
    allowed_mics: tuple[str, ...]
    availability_lag_sessions: int
    availability_basis: str
    min_history_sessions: int
    liquidity_lookback_sessions: int
    min_liquidity_observations: int
    min_avg_traded_value_eur: float
    min_close_eur: float
    tradable_enabled: bool
    tradable_blocker: str
    servable_enabled: bool
    servable_blocker: str

    @classmethod
    def from_yaml(cls, path: Path) -> "FRLiquidityPolicy":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        source = raw.get("source_contract") or {}
        scope = raw.get("scope") or {}
        availability = raw.get("availability") or {}
        training = raw.get("training") or {}
        tradable = raw.get("tradable") or {}
        servable = raw.get("servable") or {}
        policy = cls(
            schema_version=int(raw.get("schema_version") or 0),
            policy_version=str(raw.get("policy_version") or ""),
            market_code=str(raw.get("market_code") or ""),
            database_alias=str(raw.get("database_alias") or ""),
            calendar_id=str(raw.get("calendar_id") or ""),
            source_verdict=str(source.get("verdict") or ""),
            source_policy_version=str(source.get("policy_version") or ""),
            source_report_path=str(source.get("report_path") or ""),
            source_manifest_path=str(source.get("manifest_path") or ""),
            archive_root=str(source.get("archive_root") or ""),
            start_date=date.fromisoformat(str(scope.get("start_date"))),
            end_date=date.fromisoformat(str(scope.get("end_date"))),
            allowed_mics=tuple(str(value) for value in scope.get("allowed_mics") or ()),
            availability_lag_sessions=int(availability.get("lag_sessions") or 0),
            availability_basis=str(availability.get("basis") or ""),
            min_history_sessions=int(training.get("min_history_sessions") or 0),
            liquidity_lookback_sessions=int(training.get("liquidity_lookback_sessions") or 0),
            min_liquidity_observations=int(training.get("min_liquidity_observations") or 0),
            min_avg_traded_value_eur=float(training.get("min_avg_traded_value_eur") or 0),
            min_close_eur=float(training.get("min_close_eur") or 0),
            tradable_enabled=bool(tradable.get("enabled", False)),
            tradable_blocker=str(tradable.get("blocker") or ""),
            servable_enabled=bool(servable.get("enabled", False)),
            servable_blocker=str(servable.get("blocker") or ""),
        )
        policy.validate()
        return policy

    def validate(self) -> None:
        if self.schema_version != 1 or not self.policy_version:
            raise ValueError("Politique France 6-B invalide")
        if (self.market_code, self.database_alias, self.calendar_id) != (
            "FR_EQ", "fr_primary", "XPAR"
        ):
            raise ValueError("6-B doit cibler FR_EQ/fr_primary/XPAR")
        if (self.source_verdict, self.source_policy_version) != (
            "GO_RESEARCH_J1", "fr_s5_limited_v1"
        ):
            raise ValueError("Contrat source Sprint 5 incompatible")
        if self.start_date < date(2018, 1, 1) or self.end_date < self.start_date:
            raise ValueError("Période France 6-B invalide")
        if not set(self.allowed_mics) <= {"XPAR", "ALXP", "XMLI"}:
            raise ValueError("MIC France 6-B non autorisé")
        if self.availability_lag_sessions != 1 or self.availability_basis != "RESEARCH_J1_SESSION":
            raise ValueError("6-B exige une disponibilité J+1 en séances")
        if not 0 < self.min_liquidity_observations <= self.liquidity_lookback_sessions:
            raise ValueError("Fenêtre de liquidité France incohérente")
        if self.min_history_sessions < self.liquidity_lookback_sessions:
            raise ValueError("Historique minimum inférieur à la fenêtre de liquidité")
        if self.min_avg_traded_value_eur <= 0 or self.min_close_eur <= 0:
            raise ValueError("Seuils de liquidité/prix France invalides")
        if self.tradable_enabled or self.servable_enabled:
            raise ValueError("6-B interdit tradable et serving")


def _iter_manifest(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def _load_symbol_bars(archive_root: Path, symbol: str) -> dict[str, dict[str, Any]]:
    key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
    metadata_path = archive_root / "symbols" / f"{key}.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Métadonnées EODHD absentes : {symbol}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("symbol") != symbol or metadata.get("status") != "COMPLETED":
        raise ValueError(f"Archive EODHD incomplète : {symbol}")
    payload_meta = (metadata.get("payloads") or {}).get("eod") or {}
    payload_path = archive_root / str(payload_meta.get("file") or "")
    if not payload_path.is_file():
        raise ValueError(f"Payload EODHD absent : {symbol}")
    with gzip.open(payload_path, "rb") as stream:
        payload = stream.read()
    if hashlib.sha256(payload).hexdigest() != payload_meta.get("sha256"):
        raise ValueError(f"Hash du payload EODHD invalide : {symbol}")
    rows = json.loads(payload)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        day = str(row.get("date") or "")
        if day in result:
            raise ValueError(f"Barre EODHD dupliquée : {symbol}/{day}")
        result[day] = row
    return result


def build_symbol_snapshots(
    *,
    symbol: str,
    manifest_rows: Iterable[dict[str, Any]],
    bars_by_date: dict[str, dict[str, Any]],
    policy: FRLiquidityPolicy,
    session_index: dict[date, int],
    sessions: list[date],
) -> list[dict[str, Any]]:
    """Produit les métriques connues à J+1, sans utiliser une barre future."""
    eligible_rows = sorted(
        (
            row for row in manifest_rows
            if bool(row.get("research_j1_eligible"))
            and policy.start_date <= date.fromisoformat(str(row["session_date"])) <= policy.end_date
        ),
        key=lambda row: str(row["session_date"]),
    )
    recent: deque[tuple[int, float, float, float]] = deque()
    history_sessions = 0
    snapshots: list[dict[str, Any]] = []
    for row in eligible_rows:
        source_day_text = str(row["session_date"])
        source_day = date.fromisoformat(source_day_text)
        try:
            source_index = session_index[source_day]
        except KeyError as exc:
            raise ValueError(f"Séance XPAR inconnue : {symbol}/{source_day}") from exc
        decision_index = source_index + policy.availability_lag_sessions
        if decision_index >= len(sessions):
            raise ValueError(f"Séance de décision J+1 absente : {symbol}/{source_day}")
        bar = bars_by_date.get(source_day_text)
        if bar is None:
            raise ValueError(f"Barre source absente : {symbol}/{source_day}")
        close = float(bar.get("close") or 0.0)
        volume = float(bar.get("volume") or 0.0)
        if close <= 0 or volume <= 0:
            raise ValueError(f"Barre source invalide malgré éligibilité : {symbol}/{source_day}")
        history_sessions += 1
        traded_value = close * volume
        recent.append((source_index, close, volume, traded_value))
        oldest_index = source_index - policy.liquidity_lookback_sessions + 1
        while recent and recent[0][0] < oldest_index:
            recent.popleft()
        observations = len(recent)
        avg_volume = sum(item[2] for item in recent) / observations
        avg_value = sum(item[3] for item in recent) / observations
        history_state = (
            "KNOWN" if history_sessions >= policy.min_history_sessions else "INSUFFICIENT"
        )
        liquidity_state = (
            "KNOWN" if observations >= policy.min_liquidity_observations else "INSUFFICIENT"
        )
        if history_state != "KNOWN":
            training_state, reason = "INELIGIBLE", "INSUFFICIENT_HISTORY"
        elif liquidity_state != "KNOWN":
            training_state, reason = "INELIGIBLE", "INSUFFICIENT_LIQUIDITY_OBSERVATIONS"
        elif close < policy.min_close_eur:
            training_state, reason = "INELIGIBLE", "PRICE_BELOW_MINIMUM"
        elif avg_value < policy.min_avg_traded_value_eur:
            training_state, reason = "INELIGIBLE", "AVG_TRADED_VALUE_BELOW_MINIMUM"
        else:
            training_state, reason = "ELIGIBLE", "TRAINING_GATES_PASSED"
        snapshots.append({
            "provider_symbol": symbol,
            "mic": str(row.get("mic") or ""),
            "source_session_date": source_day.isoformat(),
            "decision_session_date": sessions[decision_index].isoformat(),
            "availability_lag_sessions": policy.availability_lag_sessions,
            "history_sessions": history_sessions,
            "liquidity_lookback_sessions": policy.liquidity_lookback_sessions,
            "liquidity_observations": observations,
            "last_close_eur": round(close, 8),
            "avg_volume_shares": round(avg_volume, 6),
            "avg_traded_value_eur": round(avg_value, 6),
            "history_state": history_state,
            "liquidity_state": liquidity_state,
            "training_state": training_state,
            "primary_reason": reason,
        })
    return snapshots


def _validate_source(
    policy: FRLiquidityPolicy, report_path: Path, manifest_path: Path
) -> tuple[str, int]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (report.get("verdict"), report.get("policy_version")) != (
        policy.source_verdict, policy.source_policy_version
    ):
        raise ValueError("Rapport source Sprint 5 incompatible")
    if report.get("canonical_writes_performed") is not False:
        raise ValueError("Le rapport source ne doit contenir aucune promotion canonique")
    actual = _sha256(manifest_path)
    if actual != str((report.get("manifest") or {}).get("sha256") or ""):
        raise ValueError("Hash du manifeste Sprint 5 incompatible")
    expected_rows = int((report.get("counts") or {}).get("RESEARCH_J1_ELIGIBLE") or 0)
    if expected_rows <= 0:
        raise ValueError("Le rapport Sprint 5 n'annonce aucune ligne de recherche")
    return actual, expected_rows


def build_liquidity_artifact(
    policy: FRLiquidityPolicy,
    *,
    output_root: Path,
    source_report_path: Path | None = None,
    source_manifest_path: Path | None = None,
    archive_root: Path | None = None,
) -> dict[str, Any]:
    report_path = source_report_path or _resolve_path(policy.source_report_path)
    manifest_path = source_manifest_path or _resolve_path(policy.source_manifest_path)
    archive = archive_root or _resolve_path(policy.archive_root)
    manifest_hash, expected_snapshots = _validate_source(policy, report_path, manifest_path)
    policy_fingerprint = _fingerprint(asdict(policy))
    run_id = f"fr6b-{policy_fingerprint[:16]}-{manifest_hash[:12]}"
    calendar = get_market_calendar(policy.market_code)
    sessions = calendar.session_dates(
        policy.start_date - timedelta(days=10), policy.end_date + timedelta(days=20)
    )
    session_index = {day: index for index, day in enumerate(sessions)}
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_root / "liquidity_snapshots.jsonl.gz"
    temporary = snapshot_path.with_suffix(snapshot_path.suffix + ".tmp")
    counts = Counter()
    by_year: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts = Counter()
    seen_symbols: set[str] = set()
    eligible_symbols: set[str] = set()
    with gzip.open(temporary, "wt", encoding="utf-8", newline="\n") as sink:
        for symbol, grouped in groupby(_iter_manifest(manifest_path), key=lambda row: str(row.get("symbol") or "")):
            if not symbol or symbol in seen_symbols:
                raise ValueError(f"Manifeste non groupé ou symbole invalide : {symbol!r}")
            seen_symbols.add(symbol)
            rows = list(grouped)
            bars = _load_symbol_bars(archive, symbol)
            snapshots = build_symbol_snapshots(
                symbol=symbol,
                manifest_rows=rows,
                bars_by_date=bars,
                policy=policy,
                session_index=session_index,
                sessions=sessions,
            )
            for snapshot in snapshots:
                sink.write(json.dumps(snapshot, ensure_ascii=False, sort_keys=True) + "\n")
                state = snapshot["training_state"]
                counts[state] += 1
                reason_counts[snapshot["primary_reason"]] += 1
                by_year[snapshot["decision_session_date"][:4]][state] += 1
                if state == "ELIGIBLE":
                    eligible_symbols.add(symbol)
    temporary.replace(snapshot_path)
    total = sum(counts.values())
    if total != expected_snapshots:
        raise ValueError(
            f"Couverture 6-B incomplète : {total} snapshots pour {expected_snapshots} attendus"
        )
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "verdict": "GO_6B_TRAINING_UNIVERSE" if counts["ELIGIBLE"] else "NO_GO_6B_EMPTY",
        "market_code": policy.market_code,
        "policy_version": policy.policy_version,
        "policy_fingerprint": policy_fingerprint,
        "liquidity_run_id": run_id,
        "source_manifest_sha256": manifest_hash,
        "source_manifest_path": str(manifest_path),
        "archive_root": str(archive),
        "snapshot_path": str(snapshot_path),
        "snapshot_sha256": _sha256(snapshot_path),
        "snapshot_count": total,
        "training_counts": dict(counts),
        "reason_counts": dict(reason_counts.most_common()),
        "by_decision_year": {year: dict(value) for year, value in sorted(by_year.items())},
        "symbols_seen": len(seen_symbols),
        "training_eligible_symbols": len(eligible_symbols),
        "thresholds": {
            "min_history_sessions": policy.min_history_sessions,
            "liquidity_lookback_sessions": policy.liquidity_lookback_sessions,
            "min_liquidity_observations": policy.min_liquidity_observations,
            "min_avg_traded_value_eur": policy.min_avg_traded_value_eur,
            "min_close_eur": policy.min_close_eur,
        },
        "database_writes_performed": False,
        "tradable_publication_enabled": False,
        "serving_enabled": False,
        "next_gate": "SPRINT_6C_BENCHMARK_SECTOR_AND_IDENTITY",
    }
    _atomic_json(output_root / "report.json", report)
    return report


def _snapshot_batches(path: Path, size: int = 5000) -> Iterator[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            batch.append(json.loads(line))
            if len(batch) >= size:
                yield batch
                batch = []
    if batch:
        yield batch


def persist_liquidity(report: dict[str, Any]) -> None:
    """Persiste le staging de recherche de manière idempotente."""
    from sqlalchemy import create_engine, text

    from database.router import build_database_url

    engine = create_engine(build_database_url("fr_primary", "FR_EQ"), pool_pre_ping=True)
    run_id = str(report["liquidity_run_id"])
    with engine.connect() as conn:
        actual = conn.execute(text("SELECT DATABASE()" )).scalar()
        if actual != "alpha_trade_fr":
            engine.dispose()
            raise RuntimeError(f"Persistance 6-B refusée sur {actual!r}")
        existing = conn.execute(text(
            "SELECT status,snapshot_count FROM fr_liquidity_runs "
            "WHERE liquidity_run_id=:run"
        ), {"run": run_id}).mappings().first()
        existing_rows = conn.execute(text(
            "SELECT COUNT(*) FROM fr_liquidity_snapshots WHERE liquidity_run_id=:run"
        ), {"run": run_id}).scalar()
    if (
        existing
        and existing["status"] == "COMPLETED"
        and int(existing["snapshot_count"] or 0) == int(report["snapshot_count"])
        and int(existing_rows or 0) == int(report["snapshot_count"])
    ):
        engine.dispose()
        return
    insert_snapshot = text(
        "INSERT INTO fr_liquidity_snapshots("
        "liquidity_run_id,provider_symbol,instrument_id,mic,source_session_date,decision_session_date,"
        "availability_lag_sessions,history_sessions,liquidity_lookback_sessions,liquidity_observations,"
        "last_close_eur,avg_volume_shares,avg_traded_value_eur,history_state,liquidity_state,"
        "training_state,primary_reason,details_json) VALUES ("
        ":run,:provider_symbol,NULL,:mic,:source_session_date,:decision_session_date,"
        ":availability_lag_sessions,:history_sessions,:liquidity_lookback_sessions,:liquidity_observations,"
        ":last_close_eur,:avg_volume_shares,:avg_traded_value_eur,:history_state,:liquidity_state,"
        ":training_state,:primary_reason,NULL) ON DUPLICATE KEY UPDATE "
        "history_sessions=VALUES(history_sessions),liquidity_observations=VALUES(liquidity_observations),"
        "last_close_eur=VALUES(last_close_eur),avg_volume_shares=VALUES(avg_volume_shares),"
        "avg_traded_value_eur=VALUES(avg_traded_value_eur),history_state=VALUES(history_state),"
        "liquidity_state=VALUES(liquidity_state),training_state=VALUES(training_state),"
        "primary_reason=VALUES(primary_reason)"
    )
    try:
        with engine.begin() as conn:
            actual = conn.execute(text("SELECT DATABASE()" )).scalar()
            if actual != "alpha_trade_fr":
                raise RuntimeError(f"Persistance 6-B refusée sur {actual!r}")
            conn.execute(text(
                "INSERT INTO fr_liquidity_runs(liquidity_run_id,market_code,policy_version,policy_fingerprint,"
                "source_manifest_sha256,status,details_json) VALUES (:run,'FR_EQ',:version,:fingerprint,:source,'RUNNING',:details) "
                "ON DUPLICATE KEY UPDATE status='RUNNING',details_json=VALUES(details_json),completed_at=NULL"
            ), {
                "run": run_id,
                "version": report["policy_version"],
                "fingerprint": report["policy_fingerprint"],
                "source": report["source_manifest_sha256"],
                "details": json.dumps(report, ensure_ascii=False, sort_keys=True),
            })
        for batch in _snapshot_batches(Path(report["snapshot_path"])):
            for row in batch:
                row["run"] = run_id
            with engine.begin() as conn:
                conn.execute(insert_snapshot, batch)
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE fr_liquidity_runs SET status='COMPLETED',snapshot_count=:total,"
                "training_eligible_count=:eligible,training_ineligible_count=:ineligible,"
                "details_json=:details,completed_at=CURRENT_TIMESTAMP(6) WHERE liquidity_run_id=:run"
            ), {
                "run": run_id,
                "total": report["snapshot_count"],
                "eligible": report["training_counts"].get("ELIGIBLE", 0),
                "ineligible": report["training_counts"].get("INELIGIBLE", 0),
                "details": json.dumps(report, ensure_ascii=False, sort_keys=True),
            })
    except Exception:
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE fr_liquidity_runs SET status='FAILED',completed_at=CURRENT_TIMESTAMP(6) "
                    "WHERE liquidity_run_id=:run"
                ), {"run": run_id})
        finally:
            engine.dispose()
        raise
    engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=Path("config/universe_fr_s6b.yaml"))
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/fr/sprint6b_liquidity"))
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()
    policy = FRLiquidityPolicy.from_yaml(args.policy)
    report = build_liquidity_artifact(policy, output_root=args.output_root)
    if args.persist:
        report["database_writes_performed"] = True
        persist_liquidity(report)
        _atomic_json(args.output_root / "report.json", report)
    print(json.dumps({
        "status": report["verdict"],
        "snapshots": report["snapshot_count"],
        "training_counts": report["training_counts"],
        "eligible_symbols": report["training_eligible_symbols"],
        "persisted": report["database_writes_performed"],
        "output": str(args.output_root / "report.json"),
    }, ensure_ascii=False))
    if report["verdict"] != "GO_6B_TRAINING_UNIVERSE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
