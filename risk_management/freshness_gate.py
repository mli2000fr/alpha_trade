"""risk_management/freshness_gate.py — Gate de fraîcheur unifié (Sprint Maître 13).

Vérifie la fraîcheur maximale de 5 dimensions :
1. Données (prix, ADV, earnings, corporate actions)
2. Modèle ML (dernier entraînement)
3. Calibration (dernière calibration)
4. Régime marché (dernier snapshot)
5. Borrow (dernière mise à jour disponibilité short)

Usage ::

    from risk_management.freshness_gate import (
        FreshnessGate, FreshnessConfig, FreshnessResult, FreshnessDimension,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


# ── FreshnessDimension ──────────────────────────────────────────────────────


class FreshnessDimension(StrEnum):
    """Dimensions de fraîcheur surveillées (Sprint Maître 13)."""

    PRICE_DATA = "price_data"
    VOLUME_ADV = "volume_adv"
    EARNINGS_CALENDAR = "earnings_calendar"
    CORPORATE_ACTIONS = "corporate_actions"
    ML_MODEL = "ml_model"
    CALIBRATION = "calibration"
    MARKET_REGIME = "market_regime"
    BORROW_AVAILABILITY = "borrow_availability"


# ── FreshnessConfig ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FreshnessConfig:
    """Configuration des seuils de fraîcheur par dimension (Sprint Maître 13).

    Tous les seuils sont en secondes. None = pas de limite.
    """

    max_age_price_data: float | None = 300.0       # 5 minutes
    max_age_volume_adv: float | None = 86400.0     # 24 heures
    max_age_earnings: float | None = 86400.0       # 24 heures
    max_age_corporate_actions: float | None = 86400.0
    max_age_ml_model: float | None = 604800.0      # 7 jours
    max_age_calibration: float | None = 604800.0   # 7 jours
    max_age_market_regime: float | None = 300.0    # 5 minutes
    max_age_borrow: float | None = 3600.0          # 1 heure

    def get_threshold(self, dim: FreshnessDimension) -> float | None:
        mapping: dict[FreshnessDimension, float | None] = {
            FreshnessDimension.PRICE_DATA: self.max_age_price_data,
            FreshnessDimension.VOLUME_ADV: self.max_age_volume_adv,
            FreshnessDimension.EARNINGS_CALENDAR: self.max_age_earnings,
            FreshnessDimension.CORPORATE_ACTIONS: self.max_age_corporate_actions,
            FreshnessDimension.ML_MODEL: self.max_age_ml_model,
            FreshnessDimension.CALIBRATION: self.max_age_calibration,
            FreshnessDimension.MARKET_REGIME: self.max_age_market_regime,
            FreshnessDimension.BORROW_AVAILABILITY: self.max_age_borrow,
        }
        return mapping.get(dim)

    def to_dict(self) -> dict[str, float | None]:
        return {dim.value: self.get_threshold(dim) for dim in FreshnessDimension}


# ── DimensionFreshness ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DimensionFreshness:
    """État de fraîcheur d'une dimension (Sprint Maître 13)."""

    dimension: FreshnessDimension
    last_updated: datetime | None = None
    age_seconds: float | None = None
    max_age_seconds: float | None = None
    is_fresh: bool = True
    is_stale: bool = False
    is_critical_stale: bool = False
    detail: str | None = None

    @property
    def status(self) -> str:
        if self.is_critical_stale:
            return "critical_stale"
        if self.is_stale:
            return "stale"
        return "fresh"


# ── FreshnessResult ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FreshnessResult:
    """Résultat du gate de fraîcheur (Sprint Maître 13).

    Attributes
    ----------
    all_fresh : bool
        True si toutes les dimensions sont fraîches.
    can_trade : bool
        True si le trading est autorisé (peut être false même si pas critique).
    must_block : bool
        True si au moins une dimension critique est stale → blocage.
    is_degraded : bool
        True si au moins une dimension non-critique est stale → dégradé.
    dimensions : tuple[DimensionFreshness, ...]
        État détaillé par dimension.
    degraded_dimensions : tuple[str, ...]
        Noms des dimensions dégradées.
    blocked_dimensions : tuple[str, ...]
        Noms des dimensions bloquantes.
    """

    all_fresh: bool = True
    can_trade: bool = True
    must_block: bool = False
    is_degraded: bool = False
    dimensions: tuple[DimensionFreshness, ...] = ()
    degraded_dimensions: tuple[str, ...] = ()
    blocked_dimensions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "all_fresh": self.all_fresh,
            "can_trade": self.can_trade,
            "must_block": self.must_block,
            "is_degraded": self.is_degraded,
            "degraded_dimensions": list(self.degraded_dimensions),
            "blocked_dimensions": list(self.blocked_dimensions),
            "dimensions": [
                {
                    "dimension": d.dimension.value,
                    "age_seconds": round(d.age_seconds, 1) if d.age_seconds else None,
                    "max_age_seconds": round(d.max_age_seconds, 1) if d.max_age_seconds else None,
                    "status": d.status,
                }
                for d in self.dimensions
            ],
        }


# ── FreshnessGate ───────────────────────────────────────────────────────────


@dataclass
class FreshnessGate:
    """Gate de fraîcheur unifié (Sprint Maître 13).

    Évalue 5 dimensions de fraîcheur :
    1. Données (prix, ADV, earnings, corporate actions)
    2. Modèle ML (dernier entraînement)
    3. Calibration (dernière calibration)
    4. Régime marché (dernier snapshot)
    5. Borrow (dernière mise à jour disponibilité short)

    Classification :
    - CRITICAL (fail-closed) : price_data, ml_model
    - REQUIRED (fail-degraded) : volume_adv, calibration, market_regime
    - OPTIONAL (best-effort) : earnings, corporate_actions, borrow
    """

    config: FreshnessConfig = field(default_factory=FreshnessConfig)

    # Dimensions critiques → fail-closed
    CRITICAL_DIMS: tuple[FreshnessDimension, ...] = (
        FreshnessDimension.PRICE_DATA,
        FreshnessDimension.ML_MODEL,
    )

    # Dimensions requises → fail-degraded
    REQUIRED_DIMS: tuple[FreshnessDimension, ...] = (
        FreshnessDimension.VOLUME_ADV,
        FreshnessDimension.CALIBRATION,
        FreshnessDimension.MARKET_REGIME,
    )

    def evaluate(
        self,
        *,
        price_data_at: datetime | None = None,
        volume_adv_at: datetime | None = None,
        earnings_at: datetime | None = None,
        corporate_actions_at: datetime | None = None,
        ml_model_at: datetime | None = None,
        calibration_at: datetime | None = None,
        market_regime_at: datetime | None = None,
        borrow_at: datetime | None = None,
        reference_time: datetime | None = None,
    ) -> FreshnessResult:
        """Évalue la fraîcheur de toutes les dimensions.

        Parameters
        ----------
        *_at : datetime | None
            Horodatage de la dernière mise à jour de chaque dimension.
        reference_time : datetime | None
            Temps de référence (défaut: maintenant).

        Returns
        -------
        FreshnessResult
        """
        now = reference_time or datetime.now()
        timestamps: dict[FreshnessDimension, datetime | None] = {
            FreshnessDimension.PRICE_DATA: price_data_at,
            FreshnessDimension.VOLUME_ADV: volume_adv_at,
            FreshnessDimension.EARNINGS_CALENDAR: earnings_at,
            FreshnessDimension.CORPORATE_ACTIONS: corporate_actions_at,
            FreshnessDimension.ML_MODEL: ml_model_at,
            FreshnessDimension.CALIBRATION: calibration_at,
            FreshnessDimension.MARKET_REGIME: market_regime_at,
            FreshnessDimension.BORROW_AVAILABILITY: borrow_at,
        }

        dimensions: list[DimensionFreshness] = []
        blocked: list[str] = []
        degraded: list[str] = []

        for dim in FreshnessDimension:
            ts = timestamps.get(dim)
            max_age = self.config.get_threshold(dim)
            age = (now - ts).total_seconds() if ts is not None else None

            is_stale = False
            is_critical_stale = False

            if age is not None and max_age is not None and age > max_age:
                is_stale = True
                if dim in self.CRITICAL_DIMS:
                    is_critical_stale = True
                    blocked.append(dim.value)
                elif dim in self.REQUIRED_DIMS:
                    degraded.append(dim.value)
            elif ts is None:
                # Donnée jamais mise à jour → stale
                is_stale = True
                if dim in self.CRITICAL_DIMS:
                    is_critical_stale = True
                    blocked.append(dim.value)
                elif dim in self.REQUIRED_DIMS:
                    degraded.append(dim.value)

            dimensions.append(DimensionFreshness(
                dimension=dim,
                last_updated=ts,
                age_seconds=age,
                max_age_seconds=max_age,
                is_fresh=not is_stale,
                is_stale=is_stale,
                is_critical_stale=is_critical_stale,
                detail=(
                    f"age={age:.0f}s > max={max_age:.0f}s"
                    if age is not None and max_age is not None and age > max_age
                    else "jamais mis à jour" if ts is None
                    else None
                ),
            ))

        must_block = len(blocked) > 0
        is_degraded = len(degraded) > 0
        all_fresh = not must_block and not is_degraded

        return FreshnessResult(
            all_fresh=all_fresh,
            can_trade=not must_block,
            must_block=must_block,
            is_degraded=is_degraded,
            dimensions=tuple(dimensions),
            degraded_dimensions=tuple(degraded),
            blocked_dimensions=tuple(blocked),
        )

    @classmethod
    def all_fresh(cls) -> FreshnessResult:
        """Raccourci : tout est frais (pour les tests)."""
        now = datetime.now()
        gate = cls()
        return gate.evaluate(
            price_data_at=now,
            volume_adv_at=now,
            earnings_at=now,
            corporate_actions_at=now,
            ml_model_at=now,
            calibration_at=now,
            market_regime_at=now,
            borrow_at=now,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def check_freshness(
    *,
    price_data_age_seconds: float | None = None,
    ml_model_age_seconds: float | None = None,
    market_regime_age_seconds: float | None = None,
    calibration_age_seconds: float | None = None,
) -> FreshnessResult:
    """Évalue rapidement la fraîcheur des dimensions principales."""
    now = datetime.now()
    gate = FreshnessGate()
    return gate.evaluate(
        price_data_at=now - timedelta(seconds=price_data_age_seconds) if price_data_age_seconds is not None else now,
        ml_model_at=now - timedelta(seconds=ml_model_age_seconds) if ml_model_age_seconds is not None else now,
        market_regime_at=now - timedelta(seconds=market_regime_age_seconds) if market_regime_age_seconds is not None else now,
        calibration_at=now - timedelta(seconds=calibration_age_seconds) if calibration_age_seconds is not None else now,
        volume_adv_at=now,
        borrow_at=now,
    )
