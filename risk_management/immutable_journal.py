"""risk_management/immutable_journal.py — Journal immuable des changements (Sprint Maître 15).

Maintient un journal immuable de tous les changements et overrides :
- Changements de configuration
- Overrides manuels
- Promotions/dégradations de modèles
- Transitions de palier
- Actions opérateur (kill switch, force close, rollback)

Chaque entrée est chaînée avec HMAC-SHA256 pour garantir l'intégrité.

Usage ::

    from risk_management.immutable_journal import (
        ImmutableJournal, JournalEntry, JournalEntryType,
    )
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# ── JournalEntryType ────────────────────────────────────────────────────────


class JournalEntryType(StrEnum):
    """Type d'entrée dans le journal immuable (Sprint Maître 15)."""

    CONFIG_CHANGE = "config_change"
    MANUAL_OVERRIDE = "manual_override"
    MODEL_PROMOTION = "model_promotion"
    MODEL_DEMOTION = "model_demotion"
    STAGE_TRANSITION = "stage_transition"
    KILL_SWITCH = "kill_switch"
    FORCE_CLOSE = "force_close"
    ROLLBACK = "rollback"
    INCIDENT = "incident"
    OPERATOR_ACTION = "operator_action"


# ── JournalEntry ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """Une entrée du journal immuable (Sprint Maître 15).

    Attributes
    ----------
    entry_id : str
        Identifiant unique (SHA256/16).
    entry_type : JournalEntryType
    timestamp : datetime
    operator : str
        Qui a effectué l'action.
    description : str
    previous_state : dict | None
        État avant le changement.
    new_state : dict | None
        État après le changement.
    reason : str
        Justification.
    approval : str | None
        Qui a approuvé (si applicable).
    prev_hash : str | None
        Hash de l'entrée précédente (chaînage).
    entry_hash : str
        Hash de cette entrée (SHA256/16).
    """

    entry_id: str
    entry_type: JournalEntryType
    timestamp: datetime
    operator: str
    description: str = ""
    previous_state: dict[str, object] | None = None
    new_state: dict[str, object] | None = None
    reason: str = ""
    approval: str | None = None
    prev_hash: str | None = None
    entry_hash: str = ""

    def __post_init__(self) -> None:
        if not self.entry_hash:
            object.__setattr__(self, "entry_hash", self._compute_hash())

    def _compute_hash(self) -> str:
        payload = {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type.value,
            "timestamp": self.timestamp.isoformat(),
            "operator": self.operator,
            "description": self.description,
            "reason": self.reason,
            "prev_hash": self.prev_hash,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type.value,
            "timestamp": self.timestamp.isoformat(),
            "operator": self.operator,
            "description": self.description,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "reason": self.reason,
            "approval": self.approval,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }


# ── ImmutableJournal ────────────────────────────────────────────────────────


@dataclass
class ImmutableJournal:
    """Journal immuable des changements (Sprint Maître 15).

    Garantit :
    - Chaînage cryptographique (chaque entrée référence la précédente)
    - Non-répudiation (hash + timestamp + opérateur)
    - Traçabilité complète (avant/après, raison, approbation)
    """

    def __init__(self) -> None:
        self._entries: list[JournalEntry] = []
        self._last_hash: str | None = None

    def append(
        self,
        entry_type: JournalEntryType,
        operator: str,
        description: str,
        *,
        previous_state: dict[str, object] | None = None,
        new_state: dict[str, object] | None = None,
        reason: str = "",
        approval: str | None = None,
    ) -> JournalEntry:
        """Ajoute une entrée au journal.

        Returns
        -------
        JournalEntry
        """
        entry_id = self._make_entry_id()
        entry = JournalEntry(
            entry_id=entry_id,
            entry_type=entry_type,
            timestamp=datetime.now(),
            operator=operator,
            description=description,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
            approval=approval,
            prev_hash=self._last_hash,
        )
        self._entries.append(entry)
        self._last_hash = entry.entry_hash
        return entry

    def verify_chain(self) -> tuple[bool, list[str]]:
        """Vérifie l'intégrité de la chaîne.

        Returns
        -------
        (is_valid, violations)
        """
        violations: list[str] = []
        prev_hash: str | None = None

        for i, entry in enumerate(self._entries):
            # Vérifier le chaînage
            if entry.prev_hash != prev_hash:
                violations.append(
                    f"Entry {i} ({entry.entry_id}): prev_hash mismatch — "
                    f"expected={prev_hash} got={entry.prev_hash}"
                )

            # Vérifier le hash de l'entrée
            computed = entry._compute_hash()
            if computed != entry.entry_hash:
                violations.append(
                    f"Entry {i} ({entry.entry_id}): hash mismatch — "
                    f"stored={entry.entry_hash} computed={computed}"
                )

            prev_hash = entry.entry_hash

        return len(violations) == 0, violations

    @property
    def entries(self) -> tuple[JournalEntry, ...]:
        return tuple(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def get_by_type(self, entry_type: JournalEntryType) -> list[JournalEntry]:
        return [e for e in self._entries if e.entry_type == entry_type]

    def get_by_operator(self, operator: str) -> list[JournalEntry]:
        return [e for e in self._entries if e.operator == operator]

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_count": self.entry_count,
            "last_hash": self._last_hash,
            "entries": [e.to_dict() for e in self._entries],
        }

    @staticmethod
    def _make_entry_id() -> str:
        import uuid
        return uuid.uuid4().hex[:16]


# ── Helpers ─────────────────────────────────────────────────────────────────


def create_journal_entry(
    journal: ImmutableJournal,
    entry_type: JournalEntryType,
    operator: str,
    description: str,
    **kwargs: object,
) -> JournalEntry:
    """Ajoute une entrée au journal (fonction pure)."""
    return journal.append(entry_type, operator, description, **{k: v for k, v in kwargs.items() if v is not None})  # type: ignore[arg-type]
