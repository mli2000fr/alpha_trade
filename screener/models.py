from dataclasses import asdict, dataclass, field
from math import ceil
from typing import Any, ClassVar

# Phase 3.2.c — la source de vérité des seuils communs (close, ADV20,
# RSI relatif) est ``core.filter_profiles.StrictFilterProfile``.
# ``ScreenerConfig`` reste libre d'avoir des champs spécifiques au screener
# (poids, fenêtres, two-pass loading) mais peut désormais être instancié
# directement à partir du profil partagé via :meth:`from_filter_profile`.
from core.filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile
from common.tradable_universe import UniverseMember


@dataclass(frozen=True, slots=True)
class ScreenerConfig:
    chunk_size: int = 500
    liquidity_threshold_usd: float = 10_000_000.0
    benchmark_symbol: str = "SPY"
    min_history_days: int = 252
    min_close_price: float = 5.0
    lookback_liquidity_bars: int = 30
    lookback_relative_days: int = 183
    lookback_history_years: int = 10
    historical_range_lookback_days: int = 504
    min_relative_strength_index: float = 100.0
    min_historical_range_score: float = 70.0
    weight_liquidity: float = 0.15
    weight_relative_strength: float = 0.55
    weight_historical_range: float = 0.30
    enable_two_pass_loading: bool = True
    first_pass_window_days: int = 400

    APPROX_TRADING_DAYS_PER_YEAR: ClassVar[int] = 252
    APPROX_CALENDAR_DAYS_PER_YEAR: ClassVar[int] = 365
    FIRST_PASS_WINDOW_SAFETY_DAYS: ClassVar[int] = 35

    def __post_init__(self) -> None:
        if self.chunk_size < 1:
            raise ValueError("chunk_size doit être supérieur ou égal à 1.")
        if self.liquidity_threshold_usd < 0:
            raise ValueError("liquidity_threshold_usd doit être positif.")
        if self.min_history_days < 2:
            raise ValueError("min_history_days doit être supérieur ou égal à 2.")
        if self.min_close_price <= 0:
            raise ValueError("min_close_price doit être strictement positif.")
        if self.lookback_liquidity_bars < 1:
            raise ValueError("lookback_liquidity_bars doit être supérieur ou égal à 1.")
        if self.lookback_relative_days < 1:
            raise ValueError("lookback_relative_days doit être supérieur ou égal à 1.")
        if self.lookback_history_years < 1:
            raise ValueError("lookback_history_years doit être supérieur ou égal à 1.")
        if self.historical_range_lookback_days < 2:
            raise ValueError("historical_range_lookback_days doit être supérieur ou égal à 2.")
        if self.min_relative_strength_index <= 0:
            raise ValueError("min_relative_strength_index doit être strictement positif.")
        if not 0.0 <= self.min_historical_range_score <= 100.0:
            raise ValueError("min_historical_range_score doit être compris entre 0 et 100.")
        if self.first_pass_window_days < 1:
            raise ValueError("first_pass_window_days doit être supérieur ou égal à 1.")
        if self.effective_first_pass_window_days < self.lookback_relative_days:
            raise ValueError("effective_first_pass_window_days doit couvrir au minimum lookback_relative_days.")

        weights = (
            self.weight_liquidity,
            self.weight_relative_strength,
            self.weight_historical_range,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("Les poids du screener doivent être positifs.")
        if sum(weights) <= 0:
            raise ValueError("La somme des poids du screener doit être strictement positive.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def min_calendar_window_for_history_days(cls, history_days: int) -> int:
        """Convertit un minimum de séances en fenêtre calendaire réaliste.

        Le screener charge ses prix sur une fenêtre exprimée en jours calendrier,
        mais ``min_history_days`` représente un nombre de séances. On applique une
        conversion 252 -> 365 jours puis une petite marge de sécurité pour couvrir
        jours fériés, débuts/fin d'année et dates PIT serrées.
        """
        normalized_history_days = max(1, int(history_days))
        calendar_days = ceil(
            normalized_history_days * cls.APPROX_CALENDAR_DAYS_PER_YEAR / cls.APPROX_TRADING_DAYS_PER_YEAR
        )
        return calendar_days + cls.FIRST_PASS_WINDOW_SAFETY_DAYS

    @property
    def effective_first_pass_window_days(self) -> int:
        return max(
            int(self.first_pass_window_days),
            int(self.lookback_relative_days),
            self.min_calendar_window_for_history_days(int(self.min_history_days)),
        )

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> "ScreenerConfig":
        normalized_payload = dict(payload)
        normalized_payload.pop("timeframe", None)
        return ScreenerConfig(**normalized_payload)

    # -- Phase 3.2.c — alignement sur core.filter_profiles ------------------
    @classmethod
    def from_filter_profile(
        cls,
        profile: StrictFilterProfile,
        **overrides: Any,
    ) -> "ScreenerConfig":
        """Construit une ``ScreenerConfig`` à partir d'un profil partagé.

        Mapping des champs communs (cf. ``StrictFilterProfile``) :

        - ``min_close``               → ``min_close_price``
        - ``min_avg_dollar_volume_20d`` → ``liquidity_threshold_usd``
        - ``min_relative_strength_index`` → ``min_relative_strength_index``
          (conserve le défaut screener si ``None`` côté profil).

        Les champs spécifiques au screener (poids, two-pass, fenêtres)
        gardent leurs défauts sauf override explicite. Cela évite la
        divergence des seuils communs entre screener et selector.
        """
        merged: dict[str, Any] = {
            "min_close_price": profile.min_close,
            "liquidity_threshold_usd": profile.min_avg_dollar_volume_20d,
        }
        if profile.min_relative_strength_index is not None:
            merged["min_relative_strength_index"] = profile.min_relative_strength_index
        merged.update(overrides)
        return cls(**merged)

    @classmethod
    def strict_swing_cash(cls, **overrides: Any) -> "ScreenerConfig":
        """Phase 3.2.c — raccourci aligné sur ``STRICT_SWING_CASH_FILTERS``."""
        return cls.from_filter_profile(STRICT_SWING_CASH_FILTERS, **overrides)


@dataclass(frozen=True, slots=True)
class ScreenerChunkMetrics:
    input_symbols: int = 0
    recent_rows_loaded: int = 0
    range_rows_loaded: int = 0
    symbols_pass_history: int = 0
    symbols_pass_liquidity: int = 0
    symbols_pass_relative_strength: int = 0
    symbols_final: int = 0
    rows_avoided_estimate: int = 0
    pass1_seconds: float = 0.0
    pass2_seconds: float = 0.0
    duration_seconds: float = 0.0
    failed: bool = False
    error_message: str | None = None
    universe_members: tuple[UniverseMember, ...] = ()


@dataclass(frozen=True, slots=True)
class ScreenerRunReport:
    run_id: str
    benchmark_symbol: str
    chunk_size: int
    workers: int
    as_of_date: str | None
    started_at: str
    finished_at: str | None = None
    duration_seconds: float = 0.0
    targeted_symbols: int = 0
    chunks_total: int = 0
    chunks_completed: int = 0
    chunk_failures: int = 0
    recent_rows_loaded: int = 0
    range_rows_loaded: int = 0
    symbols_pass_history: int = 0
    symbols_pass_liquidity: int = 0
    symbols_pass_relative_strength: int = 0
    symbols_final: int = 0
    rows_avoided_estimate: int = 0
    benchmark_load_seconds: float = 0.0
    pass1_seconds: float = 0.0
    pass2_seconds: float = 0.0
    upsert_seconds: float = 0.0
    persistence_status: str = "pending"
    persisted_rows: int = 0
    purge_performed: bool = False
    archive_performed: bool = False
    universe_run_id: str | None = None
    universe_persistence_status: str = "pending"
    universe_rows_written: int = 0
    chunk_error_samples: list[dict[str, object]] = field(default_factory=list)

    @property
    def chunk_failure_ratio(self) -> float:
        """Phase 3.2.b — ratio chunks en échec sur chunks totaux (0 si aucun chunk)."""
        if self.chunks_total <= 0:
            return 0.0
        return round(self.chunk_failures / self.chunks_total, 4)

    def to_summary_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["chunk_failure_ratio"] = self.chunk_failure_ratio
        return payload
