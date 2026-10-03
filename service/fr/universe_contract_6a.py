"""Audit Sprint 6-A du contrat d'univers PIT France.

Ce module ne publie aucun univers tradable. Il transforme le GO limité du
Sprint 5 en quatre états explicites (observable, entraînable, tradable,
servable) et échoue si le contrat de recherche J+1 est utilisé comme une
autorisation économique ou de production.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

ROOT = Path(__file__).resolve().parents[2]
ScopeState = Literal["ELIGIBLE", "INELIGIBLE", "UNKNOWN", "PROHIBITED"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_path(value: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


@dataclass(frozen=True)
class FRUniversePolicy:
    schema_version: int
    policy_version: str
    market_code: str
    database_alias: str
    source_verdict: str
    source_policy_version: str
    source_report_path: str
    source_manifest_path: str
    start_date: date
    end_date: date
    allowed_mics: tuple[str, ...]
    min_history_sessions: int
    liquidity_gate: str
    tradable_enabled: bool
    tradable_blocker: str
    servable_enabled: bool
    servable_blocker: str
    prohibitions: tuple[str, ...]

    @classmethod
    def from_yaml(cls, path: Path) -> "FRUniversePolicy":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        source = raw.get("source_contract") or {}
        scope = raw.get("scope") or {}
        training = raw.get("training") or {}
        tradable = raw.get("tradable") or {}
        servable = raw.get("servable") or {}
        policy = cls(
            schema_version=int(raw.get("schema_version") or 0),
            policy_version=str(raw.get("policy_version") or ""),
            market_code=str(raw.get("market_code") or ""),
            database_alias=str(raw.get("database_alias") or ""),
            source_verdict=str(source.get("verdict") or ""),
            source_policy_version=str(source.get("policy_version") or ""),
            source_report_path=str(source.get("report_path") or ""),
            source_manifest_path=str(source.get("manifest_path") or ""),
            start_date=date.fromisoformat(str(scope.get("start_date"))),
            end_date=date.fromisoformat(str(scope.get("end_date"))),
            allowed_mics=tuple(str(value) for value in scope.get("allowed_mics") or ()),
            min_history_sessions=int(training.get("min_history_sessions") or 0),
            liquidity_gate=str(training.get("liquidity_gate") or ""),
            tradable_enabled=bool(tradable.get("enabled", False)),
            tradable_blocker=str(tradable.get("blocker") or ""),
            servable_enabled=bool(servable.get("enabled", False)),
            servable_blocker=str(servable.get("blocker") or ""),
            prohibitions=tuple(str(value) for value in raw.get("prohibitions") or ()),
        )
        policy.validate()
        return policy

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ValueError("schema_version France 6-A inattendue")
        if (self.market_code, self.database_alias) != ("FR_EQ", "fr_primary"):
            raise ValueError("La politique 6-A doit cibler FR_EQ/fr_primary")
        if self.source_verdict != "GO_RESEARCH_J1":
            raise ValueError("6-A exige le verdict source GO_RESEARCH_J1")
        if self.source_policy_version != "fr_s5_limited_v1":
            raise ValueError("Politique source Sprint 5 inattendue")
        if self.start_date < date(2018, 1, 1) or self.end_date < self.start_date:
            raise ValueError("Période France 6-A invalide")
        if not self.allowed_mics or not set(self.allowed_mics) <= {"XPAR", "ALXP", "XMLI"}:
            raise ValueError("MIC France 6-A non autorisé")
        if self.min_history_sessions <= 0:
            raise ValueError("Historique minimum France invalide")
        if self.liquidity_gate != "pending_sprint_6b":
            raise ValueError("Le gate de liquidité doit rester en attente du Sprint 6-B")
        required = {"no_live", "no_paper", "no_serving", "no_canonical_write"}
        if not required <= set(self.prohibitions):
            raise ValueError("Prohibitions de recherche France incomplètes")
        if self.tradable_enabled or self.servable_enabled:
            raise ValueError("6-A interdit d'activer tradable ou serving")
        if not self.tradable_blocker or not self.servable_blocker:
            raise ValueError("Les blockers tradable/servable doivent être explicites")


@dataclass(frozen=True)
class ScopeDecision:
    symbol: str
    session_date: str
    observable_state: ScopeState
    observable_reason: str
    training_state: ScopeState
    training_reason: str
    tradable_state: ScopeState
    tradable_reason: str
    servable_state: ScopeState
    servable_reason: str


def classify_manifest_row(row: dict[str, Any], policy: FRUniversePolicy) -> ScopeDecision:
    """Classe une ligne sans inventer la liquidité, la cap ou le spread."""
    symbol = str(row.get("symbol") or "")
    session = str(row.get("session_date") or "")
    if not symbol or not session:
        raise ValueError("Ligne manifeste sans symbole/date")
    day = date.fromisoformat(session)
    if not policy.start_date <= day <= policy.end_date:
        observable_state: ScopeState = "INELIGIBLE"
        observable_reason = "OUTSIDE_REGISTERED_PERIOD"
    elif not bool(row.get("research_j1_eligible")):
        reasons = row.get("research_rejection_reasons") or []
        observable_state = "INELIGIBLE"
        observable_reason = str(reasons[0] if reasons else "SOURCE_CONTRACT_REJECTED")
    elif str(row.get("mic") or "") not in policy.allowed_mics:
        observable_state = "INELIGIBLE"
        observable_reason = "MIC_NOT_ALLOWED"
    else:
        observable_state = "ELIGIBLE"
        observable_reason = "SPRINT5_RESEARCH_J1_ELIGIBLE"

    if observable_state != "ELIGIBLE":
        training_state: ScopeState = "INELIGIBLE"
        training_reason = "OBSERVABLE_SCOPE_REJECTED"
    else:
        training_state = "UNKNOWN"
        training_reason = "HISTORY_AND_LIQUIDITY_PENDING_SPRINT6B"

    return ScopeDecision(
        symbol=symbol,
        session_date=session,
        observable_state=observable_state,
        observable_reason=observable_reason,
        training_state=training_state,
        training_reason=training_reason,
        tradable_state="PROHIBITED",
        tradable_reason=policy.tradable_blocker,
        servable_state="PROHIBITED",
        servable_reason=policy.servable_blocker,
    )


def audit_contract(
    policy: FRUniversePolicy,
    *,
    source_report_path: Path | None = None,
    source_manifest_path: Path | None = None,
) -> dict[str, Any]:
    report_path = source_report_path or _resolve_path(policy.source_report_path)
    manifest_path = source_manifest_path or _resolve_path(policy.source_manifest_path)
    source_report = json.loads(report_path.read_text(encoding="utf-8"))
    if source_report.get("verdict") != policy.source_verdict:
        raise ValueError("Verdict du rapport Sprint 5 incompatible")
    if source_report.get("policy_version") != policy.source_policy_version:
        raise ValueError("Version du rapport Sprint 5 incompatible")
    if source_report.get("canonical_writes_performed") is not False:
        raise ValueError("Le contrat 6-A exige un rapport sans écriture canonique")
    expected_hash = str((source_report.get("manifest") or {}).get("sha256") or "")
    actual_hash = _sha256(manifest_path)
    if not expected_hash or actual_hash != expected_hash:
        raise ValueError("Hash du manifeste Sprint 5 incompatible")

    stage_counts: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: dict[str, Counter[str]] = defaultdict(Counter)
    symbols: set[str] = set()
    sessions: set[str] = set()
    samples: list[dict[str, Any]] = []
    rows = 0
    with gzip.open(manifest_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            decision = classify_manifest_row(row, policy)
            rows += 1
            symbols.add(decision.symbol)
            sessions.add(decision.session_date)
            for stage in ("observable", "training", "tradable", "servable"):
                state = str(getattr(decision, f"{stage}_state"))
                reason = str(getattr(decision, f"{stage}_reason"))
                stage_counts[stage][state] += 1
                reason_counts[stage][reason] += 1
            if len(samples) < 20:
                samples.append(asdict(decision))

    forbidden_eligibles = (
        stage_counts["tradable"]["ELIGIBLE"] + stage_counts["servable"]["ELIGIBLE"]
    )
    verdict = (
        "GO_6A_CONTRACT_ONLY"
        if rows and stage_counts["observable"]["ELIGIBLE"] and not forbidden_eligibles
        else "NO_GO_6A_CONTRACT"
    )
    policy_payload = asdict(policy)
    return {
        "verdict": verdict,
        "market_code": policy.market_code,
        "database_alias": policy.database_alias,
        "policy_version": policy.policy_version,
        "policy_fingerprint": _fingerprint(policy_payload),
        "source_contract": {
            "report_path": str(report_path),
            "manifest_path": str(manifest_path),
            "manifest_sha256": actual_hash,
            "verdict": source_report["verdict"],
            "policy_version": source_report["policy_version"],
        },
        "rows": rows,
        "symbols": len(symbols),
        "sessions": len(sessions),
        "stage_counts": {stage: dict(counts) for stage, counts in stage_counts.items()},
        "reason_counts": {stage: dict(counts.most_common()) for stage, counts in reason_counts.items()},
        "database_writes_performed": False,
        "tradable_publication_enabled": False,
        "serving_enabled": False,
        "samples": samples,
        "next_gate": "SPRINT_6B_HISTORY_LIQUIDITY",
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=Path("config/universe_fr.yaml"))
    parser.add_argument("--source-report", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/fr/sprint6a_universe_contract/report.json"),
    )
    args = parser.parse_args()
    policy = FRUniversePolicy.from_yaml(args.policy)
    report = audit_contract(
        policy,
        source_report_path=args.source_report,
        source_manifest_path=args.source_manifest,
    )
    _atomic_json(args.output, report)
    print(json.dumps({
        "status": report["verdict"],
        "rows": report["rows"],
        "symbols": report["symbols"],
        "sessions": report["sessions"],
        "output": str(args.output),
    }, ensure_ascii=False))
    if report["verdict"] != "GO_6A_CONTRACT_ONLY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
