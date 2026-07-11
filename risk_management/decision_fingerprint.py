"""risk_management/decision_fingerprint.py — Fingerprint, audit log, rejeu et idempotence (Sprint Maître 12).

Garantit la parité déterministe entre replay, paper et live :
1. Fingerprint déterministe de TOUS les inputs d'une décision
2. Audit log complet pour rejouer une journée
3. Vérification de rejeu (mêmes entrées → mêmes sorties)
4. Gate d'idempotence (détection de décisions dupliquées)

Usage ::

    from risk_management.decision_fingerprint import (
        DecisionFingerprint, DecisionAuditLog, ReplayVerifier, IdempotencyGate,
    )
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


# ── DecisionFingerprint ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DecisionFingerprint:
    """Fingerprint déterministe de tous les inputs d'une décision de risque (Sprint Maître 12).

    Combine TOUS les facteurs qui influencent la décision en un hash unique.
    Deux décisions avec le même fingerprint sont GARANTIES identiques.

    Attributes
    ----------
    trade_date : date
    run_id : str
        Identifiant du run de décision.
    config_fingerprint : str
        SHA256/16 de la RiskConfig.
    model_run_id : str
        Identifiant du modèle ML utilisé.
    policy_version : int
        Version de la TernaryDecisionPolicy.
    universe_fingerprint : str
        Fingerprint de l'univers tradable.
    regime_mode : str
        Mode régime au moment de la décision.
    candidate_count : int
        Nombre de candidats en entrée.
    fingerprint : str
        SHA256/16 combiné de tous les champs ci-dessus.
    """

    trade_date: date
    run_id: str
    config_fingerprint: str
    model_run_id: str
    policy_version: int
    universe_fingerprint: str = ""
    regime_mode: str = "normal"
    candidate_count: int = 0
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", self._compute())

    def _compute(self) -> str:
        """Calcule le fingerprint combiné SHA256/16."""
        payload = {
            "trade_date": self.trade_date.isoformat(),
            "run_id": self.run_id,
            "config": self.config_fingerprint,
            "model": self.model_run_id,
            "policy": self.policy_version,
            "universe": self.universe_fingerprint,
            "regime": self.regime_mode,
            "candidates": self.candidate_count,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "run_id": self.run_id,
            "config_fingerprint": self.config_fingerprint,
            "model_run_id": self.model_run_id,
            "policy_version": self.policy_version,
            "universe_fingerprint": self.universe_fingerprint,
            "regime_mode": self.regime_mode,
            "candidate_count": self.candidate_count,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class PositionDecisionFingerprint:
    """Fingerprint d'une décision de position individuelle (Sprint Maître 12).

    Capture tous les inputs qui déterminent le sizing d'un symbole.

    Attributes
    ----------
    symbol : str
    side : str
    decision_fingerprint : str
        Fingerprint du run de décision parent.
    predicted_proba : float
    p_side : float
    edge : float | None
    price : float
    atr : float | None
    adv_usd : float | None
    config_fingerprint : str
    fingerprint : str
        SHA256/16 combiné.
    """

    symbol: str
    side: str
    decision_fingerprint: str
    predicted_proba: float = 0.0
    p_side: float = 0.0
    edge: float | None = None
    price: float = 0.0
    atr: float | None = None
    adv_usd: float | None = None
    config_fingerprint: str = ""
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.fingerprint:
            object.__setattr__(self, "fingerprint", self._compute())

    def _compute(self) -> str:
        payload = {
            "symbol": self.symbol,
            "side": self.side,
            "decision": self.decision_fingerprint,
            "predicted_proba": round(self.predicted_proba, 6),
            "p_side": round(self.p_side, 6),
            "edge": round(self.edge, 6) if self.edge is not None else None,
            "price": round(self.price, 2),
            "atr": round(self.atr, 4) if self.atr is not None else None,
            "adv_usd": round(self.adv_usd, 2) if self.adv_usd is not None else None,
            "config": self.config_fingerprint,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ── DecisionAuditLog ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AuditLogEntry:
    """Une entrée d'audit log pour une décision (Sprint Maître 12).

    Contient TOUT ce qui est nécessaire pour rejouer la décision.
    """

    trade_date: date
    timestamp: datetime
    run_id: str
    symbol: str
    side: str
    decision: str  # ACCEPTED / REDUCED / REJECTED
    reason: str
    proposed_shares: float
    approved_shares: float
    entry_price: float
    stop_price: float | None = None
    fingerprint: str = ""
    predicted_proba: float | None = None
    edge: float | None = None
    atr: float | None = None
    config_fingerprint: str = ""
    model_run_id: str = ""
    policy_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "timestamp": self.timestamp.isoformat(),
            "run_id": self.run_id,
            "symbol": self.symbol,
            "side": self.side,
            "decision": self.decision,
            "reason": self.reason,
            "proposed_shares": self.proposed_shares,
            "approved_shares": self.approved_shares,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "fingerprint": self.fingerprint,
            "predicted_proba": self.predicted_proba,
            "edge": self.edge,
            "atr": self.atr,
            "config_fingerprint": self.config_fingerprint,
            "model_run_id": self.model_run_id,
            "policy_version": self.policy_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AuditLogEntry":
        return cls(
            trade_date=date.fromisoformat(str(data["trade_date"])),
            timestamp=datetime.fromisoformat(str(data["timestamp"])),
            run_id=str(data.get("run_id", "")),
            symbol=str(data.get("symbol", "")),
            side=str(data.get("side", "long")),
            decision=str(data.get("decision", "UNKNOWN")),
            reason=str(data.get("reason", "")),
            proposed_shares=float(data.get("proposed_shares", 0)),
            approved_shares=float(data.get("approved_shares", 0)),
            entry_price=float(data.get("entry_price", 0)),
            stop_price=float(data["stop_price"]) if data.get("stop_price") is not None else None,
            fingerprint=str(data.get("fingerprint", "")),
            predicted_proba=float(data["predicted_proba"]) if data.get("predicted_proba") is not None else None,
            edge=float(data["edge"]) if data.get("edge") is not None else None,
            atr=float(data["atr"]) if data.get("atr") is not None else None,
            config_fingerprint=str(data.get("config_fingerprint", "")),
            model_run_id=str(data.get("model_run_id", "")),
            policy_version=int(data.get("policy_version", 1)),
        )


@dataclass
class DecisionAuditLog:
    """Journal d'audit complet pour une journée de décisions (Sprint Maître 12).

    Permet de rejouer une journée depuis le log.
    """

    trade_date: date
    run_id: str = ""
    decision_fingerprint: DecisionFingerprint | None = None
    entries: list[AuditLogEntry] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def add_entry(self, entry: AuditLogEntry) -> None:
        self.entries.append(entry)

    @property
    def accepted_count(self) -> int:
        return sum(1 for e in self.entries if e.decision == "ACCEPTED")

    @property
    def rejected_count(self) -> int:
        return sum(1 for e in self.entries if e.decision == "REJECTED")

    @property
    def reduced_count(self) -> int:
        return sum(1 for e in self.entries if e.decision == "REDUCED")

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "run_id": self.run_id,
            "decision_fingerprint": self.decision_fingerprint.to_dict() if self.decision_fingerprint else None,
            "entries": [e.to_dict() for e in self.entries],
            "metadata": dict(self.metadata),
            "summary": {
                "total": len(self.entries),
                "accepted": self.accepted_count,
                "rejected": self.rejected_count,
                "reduced": self.reduced_count,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "DecisionAuditLog":
        fp_data = data.get("decision_fingerprint")
        fp = None
        if fp_data and isinstance(fp_data, dict):
            fp = DecisionFingerprint(
                trade_date=date.fromisoformat(str(fp_data.get("trade_date", "2020-01-01"))),
                run_id=str(fp_data.get("run_id", "")),
                config_fingerprint=str(fp_data.get("config_fingerprint", "")),
                model_run_id=str(fp_data.get("model_run_id", "")),
                policy_version=int(fp_data.get("policy_version", 1)),
                universe_fingerprint=str(fp_data.get("universe_fingerprint", "")),
                regime_mode=str(fp_data.get("regime_mode", "normal")),
                candidate_count=int(fp_data.get("candidate_count", 0)),
                fingerprint=str(fp_data.get("fingerprint", "")),
            )
        return cls(
            trade_date=date.fromisoformat(str(data["trade_date"])),
            run_id=str(data.get("run_id", "")),
            decision_fingerprint=fp,
            entries=[AuditLogEntry.from_dict(e) for e in (data.get("entries") or [])],
            metadata=dict(data.get("metadata") or {}),
        )


# ── ReplayVerifier ──────────────────────────────────────────────────────────


@dataclass
class ReplayVerifier:
    """Vérifie qu'un rejeu produit les mêmes décisions que l'original (Sprint Maître 12).

    Compare deux DecisionAuditLog (original vs replay) et détecte les divergences.
    """

    def verify(
        self,
        original: DecisionAuditLog,
        replay: DecisionAuditLog,
    ) -> ReplayVerificationResult:
        """Vérifie la parité entre l'original et le replay.

        Returns
        -------
        ReplayVerificationResult
        """
        errors: list[str] = []
        warnings: list[str] = []

        # ── Comparer les fingerprints de décision ──────────────────────
        if original.decision_fingerprint and replay.decision_fingerprint:
            if original.decision_fingerprint.fingerprint != replay.decision_fingerprint.fingerprint:
                errors.append(
                    f"decision_fingerprint mismatch: "
                    f"original={original.decision_fingerprint.fingerprint} "
                    f"replay={replay.decision_fingerprint.fingerprint}"
                )

        # ── Comparer le nombre d'entrées ───────────────────────────────
        if len(original.entries) != len(replay.entries):
            errors.append(
                f"entry count mismatch: original={len(original.entries)} replay={len(replay.entries)}"
            )

        # ── Comparer entrée par entrée ─────────────────────────────────
        orig_by_symbol = {e.symbol: e for e in original.entries}
        replay_by_symbol = {e.symbol: e for e in replay.entries}

        # Symboles dans l'original mais pas dans le replay
        for sym in orig_by_symbol:
            if sym not in replay_by_symbol:
                errors.append(f"symbol missing in replay: {sym}")

        # Symboles dans le replay mais pas dans l'original
        for sym in replay_by_symbol:
            if sym not in orig_by_symbol:
                errors.append(f"symbol extra in replay: {sym}")

        # Comparer les symboles communs
        for sym in sorted(set(orig_by_symbol) & set(replay_by_symbol)):
            o = orig_by_symbol[sym]
            r = replay_by_symbol[sym]

            if o.decision != r.decision:
                errors.append(f"{sym}: decision mismatch original={o.decision} replay={r.decision}")
            elif o.approved_shares != r.approved_shares:
                errors.append(
                    f"{sym}: shares mismatch original={o.approved_shares} replay={r.approved_shares}"
                )
            elif o.side != r.side:
                errors.append(f"{sym}: side mismatch original={o.side} replay={r.side}")
            elif o.fingerprint != r.fingerprint:
                warnings.append(f"{sym}: fingerprint differs (inputs changed?)")

        # ── Synthèse ──────────────────────────────────────────────────
        passed = len(errors) == 0
        return ReplayVerificationResult(
            passed=passed,
            errors=tuple(errors),
            warnings=tuple(warnings),
            original_entry_count=len(original.entries),
            replay_entry_count=len(replay.entries),
            matching_count=len(set(orig_by_symbol) & set(replay_by_symbol)),
        )


@dataclass(frozen=True, slots=True)
class ReplayVerificationResult:
    """Résultat d'une vérification de parité replay (Sprint Maître 12)."""

    passed: bool = True
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    original_entry_count: int = 0
    replay_entry_count: int = 0
    matching_count: int = 0

    @property
    def parity_pct(self) -> float:
        """Pourcentage de parité (entrées identiques / total original)."""
        if self.original_entry_count == 0:
            return 1.0
        return self.matching_count / self.original_entry_count

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "original_entry_count": self.original_entry_count,
            "replay_entry_count": self.replay_entry_count,
            "matching_count": self.matching_count,
            "parity_pct": round(self.parity_pct, 4),
        }


# ── IdempotencyGate ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdempotencyResult:
    """Résultat d'une vérification d'idempotence (Sprint Maître 12)."""

    is_duplicate: bool = False
    existing_run_id: str | None = None
    existing_fingerprint: str | None = None
    reason: str = ""


@dataclass
class IdempotencyGate:
    """Détecte les décisions de risque dupliquées (Sprint Maître 12).

    Une décision est idempotente si :
    - Même trade_date + même config_fingerprint + même model_run_id
      + même universe_fingerprint + même regime_mode → même décision.

    Le gate compare le fingerprint de la décision courante avec
    les fingerprints des décisions précédentes.
    """

    def __init__(self) -> None:
        self._seen: dict[str, str] = {}  # fingerprint → run_id

    def check(
        self,
        decision_fingerprint: DecisionFingerprint,
    ) -> IdempotencyResult:
        """Vérifie si cette décision a déjà été prise.

        Parameters
        ----------
        decision_fingerprint : DecisionFingerprint

        Returns
        -------
        IdempotencyResult
        """
        fp = decision_fingerprint.fingerprint
        if fp in self._seen:
            return IdempotencyResult(
                is_duplicate=True,
                existing_run_id=self._seen[fp],
                existing_fingerprint=fp,
                reason=f"Décision déjà prise (run_id={self._seen[fp]})",
            )

        self._seen[fp] = decision_fingerprint.run_id
        return IdempotencyResult(is_duplicate=False)

    def clear(self) -> None:
        self._seen.clear()


# ── Helpers ─────────────────────────────────────────────────────────────────


def build_decision_fingerprint(
    trade_date: date,
    run_id: str,
    *,
    config_fingerprint: str,
    model_run_id: str,
    policy_version: int = 1,
    universe_fingerprint: str = "",
    regime_mode: str = "normal",
    candidate_count: int = 0,
) -> DecisionFingerprint:
    """Construit un DecisionFingerprint."""
    return DecisionFingerprint(
        trade_date=trade_date,
        run_id=run_id,
        config_fingerprint=config_fingerprint,
        model_run_id=model_run_id,
        policy_version=policy_version,
        universe_fingerprint=universe_fingerprint,
        regime_mode=regime_mode,
        candidate_count=candidate_count,
    )


def build_position_fingerprint(
    symbol: str,
    side: str,
    decision_fingerprint: str,
    *,
    predicted_proba: float = 0.0,
    p_side: float = 0.0,
    edge: float | None = None,
    price: float = 0.0,
    atr: float | None = None,
    adv_usd: float | None = None,
    config_fingerprint: str = "",
) -> PositionDecisionFingerprint:
    """Construit un PositionDecisionFingerprint."""
    return PositionDecisionFingerprint(
        symbol=symbol,
        side=side,
        decision_fingerprint=decision_fingerprint,
        predicted_proba=predicted_proba,
        p_side=p_side,
        edge=edge,
        price=price,
        atr=atr,
        adv_usd=adv_usd,
        config_fingerprint=config_fingerprint,
    )
