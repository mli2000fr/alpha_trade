"""Sprint S12.2 — Repository ``audit_chain_events`` (chaînage HMAC SOX-like).

Chaque appel à :meth:`AuditChainRepository.append` :

1. Calcule le payload canonique ``json.dumps(sort_keys=True, default=str)``.
2. Récupère le ``prev_hash`` (dernier maillon pour ce ``run_kind``).
3. Calcule ``HMAC-SHA256(key, f"{prev_hash}|{payload}")``.
4. Insère la ligne dans ``audit_chain_events``.

La clé est lue via ``get_audit_hmac_key()`` (env
``ALPHA_TRADE_AUDIT_HMAC_KEY``). Une rotation de clé est tracée via
``key_version``.

L'API publique :

- :class:`AuditChainRepository` (engine SQLAlchemy injecté).
- :class:`ChainAnomaly` (dataclass).
- :func:`get_audit_hmac_key` / :func:`get_audit_key_version`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)

ENV_AUDIT_HMAC_KEY = "ALPHA_TRADE_AUDIT_HMAC_KEY"
ENV_AUDIT_KEY_VERSION = "ALPHA_TRADE_AUDIT_KEY_VERSION"

_GENESIS_HASH = "0" * 64


# ---------------------------------------------------------------------------
# Clé HMAC
# ---------------------------------------------------------------------------


def get_audit_hmac_key() -> bytes:
    """Retourne la clé HMAC.

    En l'absence de la variable d'environnement, on utilise une clé
    *développement* déterministe pour ne pas casser les fixtures locales.
    En production, ``ALPHA_TRADE_AUDIT_HMAC_KEY`` doit être définie via le
    secret manager (cf. ``common/config_vault.py``).
    """
    raw = os.getenv(ENV_AUDIT_HMAC_KEY)
    if raw:
        return raw.encode("utf-8")
    LOGGER.debug("Audit HMAC key non définie (%s) — fallback dev.", ENV_AUDIT_HMAC_KEY)
    return b"alpha-trade-dev-audit-key"


def get_audit_key_version() -> int:
    raw = os.getenv(ENV_AUDIT_KEY_VERSION)
    if not raw:
        return 1
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


# ---------------------------------------------------------------------------
# Modèles
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChainAnomaly:
    """Une rupture de chaîne détectée par :meth:`AuditChainRepository.verify`."""

    run_kind: str
    event_id: int
    expected_prev_hash: str
    actual_prev_hash: str
    expected_hmac: str
    actual_hmac: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "run_kind": self.run_kind,
            "event_id": self.event_id,
            "expected_prev_hash": self.expected_prev_hash,
            "actual_prev_hash": self.actual_prev_hash,
            "expected_hmac": self.expected_hmac,
            "actual_hmac": self.actual_hmac,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _canonicalize(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))


def _compute_hmac(key: bytes, prev_hash: str, payload: str) -> str:
    msg = f"{prev_hash}|{payload}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class AuditChainRepository:
    """Persistance et vérification de la chaîne d'audit signée."""

    def __init__(
        self,
        engine: Engine,
        *,
        key: bytes | None = None,
        key_version: int | None = None,
    ) -> None:
        self.engine = engine
        self._key = key if key is not None else get_audit_hmac_key()
        self._key_version = key_version if key_version is not None else get_audit_key_version()

    # ---- write -----------------------------------------------------------

    def latest_hash(self, run_kind: str) -> str:
        stmt = text(
            "SELECT hmac_sha256 FROM audit_chain_events "
            "WHERE run_kind = :rk ORDER BY id DESC LIMIT 1"
        )
        with self.engine.connect() as conn:
            row = conn.execute(stmt, {"rk": run_kind}).first()
        return str(row[0]) if row else _GENESIS_HASH

    def append(
        self,
        run_kind: str,
        run_id: str,
        payload: Mapping[str, Any],
    ) -> str:
        """Append d'un maillon. Retourne le nouveau hash. Best-effort.

        Si la table n'existe pas (fixtures legacy), log et retourne le hash
        calculé sans persister — l'audit ne doit jamais bloquer le run métier.
        """
        canonical = _canonicalize(payload)
        prev = self.latest_hash(run_kind)
        new_hash = _compute_hmac(self._key, prev, canonical)
        stmt = text(
            "INSERT INTO audit_chain_events "
            "(run_kind, run_id, payload_canonical_json, prev_hash, hmac_sha256, "
            " key_version, signed_at) "
            "VALUES (:rk, :ri, :pl, :ph, :hh, :kv, :sa)"
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(stmt, {
                    "rk": run_kind,
                    "ri": run_id,
                    "pl": canonical,
                    "ph": prev,
                    "hh": new_hash,
                    "kv": self._key_version,
                    "sa": datetime.now(timezone.utc),
                })
        except Exception:  # noqa: BLE001
            LOGGER.debug("audit_chain_events indisponible (run_kind=%s, run_id=%s).",
                         run_kind, run_id, exc_info=True)
        return new_hash

    # ---- verify ----------------------------------------------------------

    def verify_chain(self, run_kind: str | None = None) -> list[ChainAnomaly]:
        """Vérifie l'intégrité de la chaîne.

        Si ``run_kind`` est ``None``, vérifie toutes les chaînes connues.
        """
        anomalies: list[ChainAnomaly] = []
        kinds = [run_kind] if run_kind else self._distinct_kinds()
        for kind in kinds:
            anomalies.extend(self._verify_one(kind))
        return anomalies

    def _distinct_kinds(self) -> list[str]:
        stmt = text("SELECT DISTINCT run_kind FROM audit_chain_events")
        try:
            with self.engine.connect() as conn:
                return [str(r[0]) for r in conn.execute(stmt)]
        except Exception:  # noqa: BLE001
            return []

    def _verify_one(self, run_kind: str) -> list[ChainAnomaly]:
        anomalies: list[ChainAnomaly] = []
        stmt = text(
            "SELECT id, payload_canonical_json, prev_hash, hmac_sha256 "
            "FROM audit_chain_events WHERE run_kind = :rk ORDER BY id ASC"
        )
        try:
            with self.engine.connect() as conn:
                rows = list(conn.execute(stmt, {"rk": run_kind}))
        except Exception:  # noqa: BLE001
            return anomalies

        expected_prev = _GENESIS_HASH
        for row in rows:
            event_id = int(row[0])
            payload = str(row[1])
            stored_prev = str(row[2])
            stored_hmac = str(row[3])
            expected_hmac = _compute_hmac(self._key, stored_prev, payload)
            reasons: list[str] = []
            if stored_prev != expected_prev:
                reasons.append("prev_hash_mismatch")
            if stored_hmac != expected_hmac:
                reasons.append("hmac_mismatch")
            if reasons:
                anomalies.append(ChainAnomaly(
                    run_kind=run_kind,
                    event_id=event_id,
                    expected_prev_hash=expected_prev,
                    actual_prev_hash=stored_prev,
                    expected_hmac=expected_hmac,
                    actual_hmac=stored_hmac,
                    reason=",".join(reasons),
                ))
            expected_prev = stored_hmac
        return anomalies


__all__ = [
    "AuditChainRepository",
    "ChainAnomaly",
    "ENV_AUDIT_HMAC_KEY",
    "ENV_AUDIT_KEY_VERSION",
    "get_audit_hmac_key",
    "get_audit_key_version",
]

