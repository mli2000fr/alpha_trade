"""risk_management/model_registry.py — Cycle de vie des modèles (Sprint Maître 13).

Définit le statut d'un modèle ML tout au long de son cycle de vie :
candidate → shadow → paper → champion → degraded → retired.

Usage ::

    from risk_management.model_registry import (
        ModelStatus, ModelRegistryEntry, ModelRegistry,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


# ── ModelStatus ─────────────────────────────────────────────────────────────


class ModelStatus(StrEnum):
    """Statut d'un modèle dans son cycle de vie (Sprint Maître 13).

    Cycle nominal : CANDIDATE → SHADOW → PAPER → CHAMPION
    Dégradation : CHAMPION → DEGRADED → RETIRED
    """

    CANDIDATE = "candidate"   # En cours d'entraînement/évaluation
    SHADOW = "shadow"         # Exécuté en parallèle, pas de décision réelle
    PAPER = "paper"           # Décisions simulées avec capital paper
    CHAMPION = "champion"     # Modèle actif en production
    DEGRADED = "degraded"     # Champion dégradé (drift, stale, underperformance)
    RETIRED = "retired"       # Retiré définitivement

    # ── Classification ──────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        """True si le modèle peut prendre des décisions réelles."""
        return self in (ModelStatus.PAPER, ModelStatus.CHAMPION)

    @property
    def is_production(self) -> bool:
        """True si le modèle est en production (champion uniquement)."""
        return self == ModelStatus.CHAMPION

    @property
    def can_be_promoted(self) -> bool:
        """True si le modèle peut être promu au statut supérieur."""
        return self in (ModelStatus.CANDIDATE, ModelStatus.SHADOW, ModelStatus.PAPER)

    @property
    def can_be_demoted(self) -> bool:
        """True si le modèle peut être rétrogradé."""
        return self in (ModelStatus.CHAMPION, ModelStatus.DEGRADED)

    def next_in_cycle(self) -> ModelStatus:
        """Statut suivant dans le cycle de promotion."""
        cycle: dict[ModelStatus, ModelStatus] = {
            ModelStatus.CANDIDATE: ModelStatus.SHADOW,
            ModelStatus.SHADOW: ModelStatus.PAPER,
            ModelStatus.PAPER: ModelStatus.CHAMPION,
        }
        return cycle.get(self, self)


# ── ModelRegistryEntry ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ModelRegistryEntry:
    """Entrée du registre des modèles (Sprint Maître 13).

    Attributes
    ----------
    model_id : str
        Identifiant unique du modèle.
    symbol : str
        Symbole ou "global".
    architecture : str
        Architecture (lightgbm, catboost, lstm_attention, etc.).
    version : int
        Version du modèle.
    status : ModelStatus
        Statut dans le cycle de vie.
    promoted_at : datetime | None
        Date de promotion au statut actuel.
    demoted_at : datetime | None
        Date de rétrogradation (si DEGRADED ou RETIRED).
    reason : str
        Raison du dernier changement de statut.
    previous_status : ModelStatus | None
        Statut précédent.
    metrics_snapshot : dict | None
        Métriques clés au moment du changement (Sharpe, F1, edge, etc.).
    artifact_path : str | None
        Chemin de l'artefact modèle.
    fingerprint : str
        SHA256 de l'artefact.
    """

    model_id: str
    symbol: str
    architecture: str = "lightgbm"
    version: int = 1
    status: ModelStatus = ModelStatus.CANDIDATE
    promoted_at: datetime | None = None
    demoted_at: datetime | None = None
    reason: str = ""
    previous_status: ModelStatus | None = None
    metrics_snapshot: dict[str, object] | None = None
    artifact_path: str | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id est obligatoire")
        if not self.symbol.strip():
            raise ValueError("symbol est obligatoire")
        if self.version < 1:
            raise ValueError("version doit être >= 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "symbol": self.symbol,
            "architecture": self.architecture,
            "version": self.version,
            "status": self.status.value,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
            "demoted_at": self.demoted_at.isoformat() if self.demoted_at else None,
            "reason": self.reason,
            "previous_status": self.previous_status.value if self.previous_status else None,
            "metrics_snapshot": self.metrics_snapshot,
            "artifact_path": self.artifact_path,
            "fingerprint": self.fingerprint,
        }


# ── ModelRegistry ───────────────────────────────────────────────────────────


@dataclass
class ModelRegistry:
    """Gère le cycle de vie des modèles (Sprint Maître 13).

    Règles :
    - Un seul CHAMPION par symbole à la fois.
    - La promotion suit le cycle : CANDIDATE → SHADOW → PAPER → CHAMPION.
    - Un champion dégradé peut être rétrogradé en DEGRADED ou RETIRED.
    - Le rollback restaure le champion précédent.

    Le registre est IN-MEMORY pour les tests. En production, il est
    persisté dans la table ``champion_history``.
    """

    def __init__(self) -> None:
        self._entries: dict[str, ModelRegistryEntry] = {}  # model_id → entry
        self._champions: dict[str, str] = {}  # symbol → model_id du champion
        self._history: dict[str, list[str]] = {}  # symbol → [model_ids in order]

    def register(self, entry: ModelRegistryEntry) -> None:
        """Enregistre un nouveau modèle."""
        if entry.model_id in self._entries:
            raise ValueError(f"Modèle déjà enregistré: {entry.model_id}")
        self._entries[entry.model_id] = entry
        self._history.setdefault(entry.symbol, []).append(entry.model_id)

    def promote(self, model_id: str, reason: str = "") -> ModelRegistryEntry:
        """Promeut un modèle au statut suivant dans le cycle.

        Si le modèle est promu à CHAMPION, l'ancien champion est rétrogradé.
        """
        if model_id not in self._entries:
            raise ValueError(f"Modèle inconnu: {model_id}")

        entry = self._entries[model_id]
        if not entry.status.can_be_promoted:
            raise ValueError(f"Le modèle {model_id} ne peut pas être promu (status={entry.status.value})")

        new_status = entry.status.next_in_cycle()
        now = datetime.now()

        # Si promotion vers CHAMPION → rétrograder l'ancien champion
        if new_status == ModelStatus.CHAMPION:
            old_champion_id = self._champions.get(entry.symbol)
            if old_champion_id and old_champion_id in self._entries:
                self._demote_internal(old_champion_id, f"remplacé par {model_id}", now)

            self._champions[entry.symbol] = model_id

        new_entry = ModelRegistryEntry(
            model_id=entry.model_id,
            symbol=entry.symbol,
            architecture=entry.architecture,
            version=entry.version,
            status=new_status,
            promoted_at=now,
            reason=reason,
            previous_status=entry.status,
            metrics_snapshot=entry.metrics_snapshot,
            artifact_path=entry.artifact_path,
            fingerprint=entry.fingerprint,
        )
        self._entries[model_id] = new_entry
        return new_entry

    def degrade(self, model_id: str, reason: str) -> ModelRegistryEntry:
        """Dégrade un champion (drift, stale, underperformance)."""
        if model_id not in self._entries:
            raise ValueError(f"Modèle inconnu: {model_id}")

        entry = self._entries[model_id]
        if not entry.status.can_be_demoted:
            raise ValueError(f"Le modèle {model_id} ne peut pas être dégradé (status={entry.status.value})")

        return self._demote_internal(model_id, reason, datetime.now())

    def retire(self, model_id: str, reason: str) -> ModelRegistryEntry:
        """Retire définitivement un modèle."""
        if model_id not in self._entries:
            raise ValueError(f"Modèle inconnu: {model_id}")
        return self._demote_internal(model_id, reason, datetime.now(), target=ModelStatus.RETIRED)

    def rollback(self, symbol: str, reason: str) -> ModelRegistryEntry | None:
        """Rollback : restaure le champion précédent.

        Returns
        -------
        ModelRegistryEntry | None
            Le nouveau champion, ou None si pas de précédent.
        """
        history = self._history.get(symbol, [])
        if len(history) < 2:
            return None  # Pas de précédent

        current_champion_id = self._champions.get(symbol)
        # Trouver le champion précédent (le dernier qui n'est pas le courant)
        previous_id = None
        for mid in reversed(history):
            if mid != current_champion_id and mid in self._entries:
                entry = self._entries[mid]
                if entry.status == ModelStatus.RETIRED:
                    continue  # Retired = définitivement hors service
                # DEGRADED est acceptable (le modèle a été dégradé par la promotion du nouveau)
                previous_id = mid
                break

        if previous_id is None:
            return None

        # Dégrader le champion actuel
        if current_champion_id and current_champion_id in self._entries:
            self._demote_internal(current_champion_id, reason, datetime.now())

        # Restaurer le précédent comme champion
        return self._promote_to_champion(previous_id, f"rollback: {reason}")

    def get_champion(self, symbol: str) -> ModelRegistryEntry | None:
        """Retourne le champion actuel pour un symbole."""
        champ_id = self._champions.get(symbol)
        if champ_id:
            return self._entries.get(champ_id)
        return None

    def get_by_status(self, symbol: str, status: ModelStatus) -> list[ModelRegistryEntry]:
        """Retourne tous les modèles d'un statut donné pour un symbole."""
        return [
            e for e in self._entries.values()
            if e.symbol == symbol and e.status == status
        ]

    def list_all(self, symbol: str | None = None) -> list[ModelRegistryEntry]:
        """Liste tous les modèles, optionnellement filtrés par symbole."""
        entries = list(self._entries.values())
        if symbol:
            entries = [e for e in entries if e.symbol == symbol]
        return sorted(entries, key=lambda e: (e.symbol, e.version), reverse=True)

    def count_by_status(self) -> dict[str, int]:
        """Compte les modèles par statut."""
        counts: dict[str, int] = {}
        for e in self._entries.values():
            counts[e.status.value] = counts.get(e.status.value, 0) + 1
        return counts

    # ── Internals ───────────────────────────────────────────────────────

    def _demote_internal(
        self,
        model_id: str,
        reason: str,
        now: datetime,
        target: ModelStatus = ModelStatus.DEGRADED,
    ) -> ModelRegistryEntry:
        entry = self._entries[model_id]
        new_entry = ModelRegistryEntry(
            model_id=entry.model_id,
            symbol=entry.symbol,
            architecture=entry.architecture,
            version=entry.version,
            status=target,
            demoted_at=now,
            reason=reason,
            previous_status=entry.status,
            metrics_snapshot=entry.metrics_snapshot,
            artifact_path=entry.artifact_path,
            fingerprint=entry.fingerprint,
        )
        self._entries[model_id] = new_entry
        # Nettoyer le champion mapping
        if self._champions.get(entry.symbol) == model_id:
            del self._champions[entry.symbol]
        return new_entry

    def _promote_to_champion(self, model_id: str, reason: str) -> ModelRegistryEntry:
        """Promeut directement un modèle au statut CHAMPION (pour rollback)."""
        entry = self._entries[model_id]
        new_entry = ModelRegistryEntry(
            model_id=entry.model_id,
            symbol=entry.symbol,
            architecture=entry.architecture,
            version=entry.version,
            status=ModelStatus.CHAMPION,
            promoted_at=datetime.now(),
            reason=reason,
            previous_status=entry.status,
            metrics_snapshot=entry.metrics_snapshot,
            artifact_path=entry.artifact_path,
            fingerprint=entry.fingerprint,
        )
        self._entries[model_id] = new_entry
        self._champions[entry.symbol] = model_id
        return new_entry


# ── Helpers ─────────────────────────────────────────────────────────────────


def create_model_entry(
    model_id: str,
    symbol: str,
    *,
    architecture: str = "lightgbm",
    version: int = 1,
    status: ModelStatus = ModelStatus.CANDIDATE,
    fingerprint: str = "",
) -> ModelRegistryEntry:
    """Crée une entrée de registre modèle."""
    return ModelRegistryEntry(
        model_id=model_id,
        symbol=symbol,
        architecture=architecture,
        version=version,
        status=status,
        fingerprint=fingerprint,
    )
