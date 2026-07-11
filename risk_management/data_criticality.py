"""risk_management/data_criticality.py — Classification et gates de disponibilité (Sprint Maître 9).

Classifie les données et contrôles en trois niveaux :
- **CRITICAL** : fail-closed — absence → blocage total des entrées
- **REQUIRED** : fail-degraded — absence → mode dégradé (sizing réduit, contraintes resserrées)
- **OPTIONAL_OVERLAY** : best-effort — absence → ignoré silencieusement

Usage ::

    from risk_management.data_criticality import (
        DataCriticality, DataAvailabilityGate, classify_data_source,
    )
    gate = DataAvailabilityGate()
    result = gate.evaluate(
        earnings_data_available=True,
        tradability_data_available=False,
        macro_overlay_available=True,
    )
    if result.must_block:
        reject_all_entries()
    elif result.is_degraded:
        apply_degraded_constraints(result)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


# ── DataCriticality ─────────────────────────────────────────────────────────


class DataCriticality(StrEnum):
    """Niveau de criticité d'une source de données ou d'un contrôle.

    - CRITICAL : fail-closed. L'absence bloque tout.
    - REQUIRED : fail-degraded. L'absence réduit le risque.
    - OPTIONAL_OVERLAY : best-effort. L'absence est ignorée.
    """

    CRITICAL = "critical"
    REQUIRED = "required"
    OPTIONAL_OVERLAY = "optional_overlay"


# ── Classification canonique par source ─────────────────────────────────────

# Mapping canonique des sources de données → criticité (Sprint Maître 9).
# Toute nouvelle source doit être classifiée ici AVANT intégration.
CANONICAL_CRITICALITY: dict[str, DataCriticality] = {
    # ── CRITICAL (fail-closed) ─────────────────────────────────────────
    "price_data": DataCriticality.CRITICAL,
    "tradable_universe": DataCriticality.CRITICAL,
    "earnings_calendar": DataCriticality.CRITICAL,
    "corporate_actions": DataCriticality.CRITICAL,
    "tradability_check": DataCriticality.CRITICAL,
    "broker_connection": DataCriticality.CRITICAL,
    "account_snapshot": DataCriticality.CRITICAL,
    "circuit_breaker": DataCriticality.CRITICAL,
    # ── REQUIRED (fail-degraded) ───────────────────────────────────────
    "ml_predictions": DataCriticality.REQUIRED,
    "market_regime": DataCriticality.REQUIRED,
    "atr_data": DataCriticality.REQUIRED,
    "volume_adv": DataCriticality.REQUIRED,
    "sector_mapping": DataCriticality.REQUIRED,
    "correlation_matrix": DataCriticality.REQUIRED,
    "factor_exposures": DataCriticality.REQUIRED,
    # ── OPTIONAL_OVERLAY (best-effort) ─────────────────────────────────
    "sentiment_overlay": DataCriticality.OPTIONAL_OVERLAY,
    "macro_overlay": DataCriticality.OPTIONAL_OVERLAY,
    "news_sentiment": DataCriticality.OPTIONAL_OVERLAY,
    "borrow_availability": DataCriticality.OPTIONAL_OVERLAY,
    "short_locates": DataCriticality.OPTIONAL_OVERLAY,
    "calendar_patterns": DataCriticality.OPTIONAL_OVERLAY,
    "yield_curve": DataCriticality.OPTIONAL_OVERLAY,
}


def classify_data_source(source_name: str) -> DataCriticality:
    """Retourne la criticité canonique d'une source de données.

    Les sources inconnues sont classées CRITICAL par défaut
    (principe de précaution : fail-closed).
    """
    return CANONICAL_CRITICALITY.get(source_name, DataCriticality.CRITICAL)


# ── AvailabilityStatus ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AvailabilityStatus:
    """Statut de disponibilité d'une source de données.

    Attributes
    ----------
    source_name : str
        Nom canonique de la source.
    criticality : DataCriticality
        Niveau de criticité.
    available : bool
        True si la donnée est disponible et fraîche.
    age_seconds : float | None
        Âge de la donnée en secondes (None si non applicable).
    quality : str | None
        Indicateur de qualité (ex: "stale", "partial", "ok").
    detail : str | None
        Détail additionnel pour le diagnostic.
    """

    source_name: str
    criticality: DataCriticality
    available: bool
    age_seconds: float | None = None
    quality: str | None = None
    detail: str | None = None

    @property
    def is_blocking(self) -> bool:
        """True si l'indisponibilité de cette source bloque les entrées."""
        return not self.available and self.criticality == DataCriticality.CRITICAL

    @property
    def is_degrading(self) -> bool:
        """True si l'indisponibilité de cette source dégrade le mode."""
        return not self.available and self.criticality == DataCriticality.REQUIRED


# ── DataAvailabilityGate ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GateResult:
    """Résultat de l'évaluation des gates de disponibilité.

    Attributes
    ----------
    must_block : bool
        True si au moins une source CRITICAL est indisponible → fail-closed.
    is_degraded : bool
        True si au moins une source REQUIRED est indisponible → fail-degraded.
    block_reasons : tuple[str, ...]
        Raisons de blocage (sources CRITICAL manquantes).
    degraded_reasons : tuple[str, ...]
        Raisons de dégradation (sources REQUIRED manquantes).
    statuses : tuple[AvailabilityStatus, ...]
        Statut détaillé de chaque source évaluée.
    degraded_multiplier : float
        Multiplicateur de risque en mode dégradé (1.0 = normal, 0.0 = tout bloqué).
    """

    must_block: bool = False
    is_degraded: bool = False
    block_reasons: tuple[str, ...] = ()
    degraded_reasons: tuple[str, ...] = ()
    statuses: tuple[AvailabilityStatus, ...] = ()
    degraded_multiplier: float = 1.0

    @property
    def can_trade(self) -> bool:
        """True si le trading est autorisé (même en mode dégradé)."""
        return not self.must_block


@dataclass
class DataAvailabilityGate:
    """Évalue la disponibilité des données et détermine le mode de fonctionnement.

    Principes (Sprint Maître 9) :
    - **Fail-closed** : si une donnée CRITICAL manque → blocage total.
    - **Fail-degraded** : si une donnée REQUIRED manque → sizing réduit,
      contraintes resserrées, shorts interdits.
    - **Best-effort** : si une donnée OPTIONAL_OVERLAY manque → ignoré.

    Le gate NE décide PAS du régime — il informe le régime des
    indisponibilités pour que la state machine prenne la décision finale.
    """

    # Seuils de fraîcheur par source (en secondes)
    max_age_seconds: dict[str, float] = field(default_factory=lambda: {
        "price_data": 300,         # 5 minutes
        "tradable_universe": 3600, # 1 heure
        "earnings_calendar": 86400, # 24 heures
        "account_snapshot": 300,
        "ml_predictions": 3600,
        "market_regime": 300,
        "correlation_matrix": 86400,
    })

    def evaluate(
        self,
        *,
        price_data_available: bool = True,
        tradable_universe_available: bool = True,
        earnings_data_available: bool = True,
        corporate_actions_available: bool = True,
        tradability_check_available: bool = True,
        broker_connection_available: bool = True,
        account_snapshot_available: bool = True,
        circuit_breaker_ok: bool = True,
        ml_predictions_available: bool = True,
        market_regime_available: bool = True,
        atr_data_available: bool = True,
        volume_adv_available: bool = True,
        sector_mapping_available: bool = True,
        correlation_matrix_available: bool = True,
        factor_exposures_available: bool = True,
        sentiment_overlay_available: bool = True,
        macro_overlay_available: bool = True,
    ) -> GateResult:
        """Évalue toutes les gates de disponibilité.

        Returns
        -------
        GateResult
        """
        statuses: list[AvailabilityStatus] = []
        critical_missing: list[str] = []
        required_missing: list[str] = []

        # ── CRITICAL ───────────────────────────────────────────────────
        critical_sources = [
            ("price_data", price_data_available),
            ("tradable_universe", tradable_universe_available),
            ("earnings_calendar", earnings_data_available),
            ("corporate_actions", corporate_actions_available),
            ("tradability_check", tradability_check_available),
            ("broker_connection", broker_connection_available),
            ("account_snapshot", account_snapshot_available),
            ("circuit_breaker", circuit_breaker_ok),
        ]
        for name, available in critical_sources:
            crit = classify_data_source(name)
            status = AvailabilityStatus(
                source_name=name,
                criticality=crit,
                available=available,
                quality="ok" if available else "missing",
                detail=None if available else f"{name} indisponible — fail-closed",
            )
            statuses.append(status)
            if not available:
                critical_missing.append(name)

        # ── REQUIRED ───────────────────────────────────────────────────
        required_sources = [
            ("ml_predictions", ml_predictions_available),
            ("market_regime", market_regime_available),
            ("atr_data", atr_data_available),
            ("volume_adv", volume_adv_available),
            ("sector_mapping", sector_mapping_available),
            ("correlation_matrix", correlation_matrix_available),
            ("factor_exposures", factor_exposures_available),
        ]
        for name, available in required_sources:
            crit = classify_data_source(name)
            status = AvailabilityStatus(
                source_name=name,
                criticality=crit,
                available=available,
                quality="ok" if available else "degraded",
                detail=None if available else f"{name} indisponible — mode dégradé",
            )
            statuses.append(status)
            if not available:
                required_missing.append(name)

        # ── OPTIONAL_OVERLAY ───────────────────────────────────────────
        optional_sources = [
            ("sentiment_overlay", sentiment_overlay_available),
            ("macro_overlay", macro_overlay_available),
        ]
        for name, available in optional_sources:
            crit = classify_data_source(name)
            status = AvailabilityStatus(
                source_name=name,
                criticality=crit,
                available=available,
                quality="ok" if available else "missing_ignored",
                detail=None if available else f"{name} indisponible — ignoré (best-effort)",
            )
            statuses.append(status)

        # ── Synthèse ───────────────────────────────────────────────────
        must_block = len(critical_missing) > 0
        is_degraded = len(required_missing) > 0

        # Multiplicateur dégradé : 1.0 → 0.5 → 0.25 selon nombre de REQUIRED manquantes
        degraded_multiplier = 1.0
        if is_degraded:
            n_missing = len(required_missing)
            degraded_multiplier = max(0.1, 1.0 - 0.25 * n_missing)

        return GateResult(
            must_block=must_block,
            is_degraded=is_degraded,
            block_reasons=tuple(critical_missing),
            degraded_reasons=tuple(required_missing),
            statuses=tuple(statuses),
            degraded_multiplier=degraded_multiplier,
        )

    @classmethod
    def all_available(cls) -> GateResult:
        """Raccourci : toutes les données sont disponibles."""
        return cls().evaluate()

    @classmethod
    def critical_missing(cls, *sources: str) -> GateResult:
        """Raccourci pour les tests : sources CRITICAL spécifiques manquantes.

        Les noms de sources sont mappés vers les noms de paramètres
        de ``evaluate()`` (ex: "price_data" → price_data_available=False).
        """
        # Mapping nom canonique → nom paramètre evaluate()
        param_map: dict[str, str] = {
            "price_data": "price_data_available",
            "tradable_universe": "tradable_universe_available",
            "earnings_calendar": "earnings_data_available",
            "corporate_actions": "corporate_actions_available",
            "tradability_check": "tradability_check_available",
            "broker_connection": "broker_connection_available",
            "account_snapshot": "account_snapshot_available",
            "circuit_breaker": "circuit_breaker_ok",
        }
        kwargs: dict[str, bool] = {}
        for src in sources:
            param_name = param_map.get(src, f"{src}_available")
            kwargs[param_name] = False
        return cls().evaluate(**kwargs)


# ── Helpers ─────────────────────────────────────────────────────────────────


def check_data_availability(
    *,
    price_ok: bool = True,
    earnings_ok: bool = True,
    tradability_ok: bool = True,
    broker_ok: bool = True,
    ml_ok: bool = True,
    regime_ok: bool = True,
) -> GateResult:
    """Évalue rapidement la disponibilité des sources principales.

    Fonction pure utilisable comme veto dans un pipeline.
    """
    gate = DataAvailabilityGate()
    return gate.evaluate(
        price_data_available=price_ok,
        earnings_data_available=earnings_ok,
        tradability_check_available=tradability_ok,
        broker_connection_available=broker_ok,
        ml_predictions_available=ml_ok,
        market_regime_available=regime_ok,
    )
