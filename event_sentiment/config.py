from dataclasses import dataclass
from datetime import datetime
from typing import Literal

NewsProvider = Literal["alpaca", "finnhub"]
TickerRelevanceMode = Literal["provider_default", "strict", "scored"]

#: Mapping centralisé ``news_provider`` → (``source_name``, ``provider_name``).
#: Permet de garantir des valeurs cohérentes entre l'identifiant de checkpoint
#: (``source_name`` dans ``news_ingestion_checkpoint``) et le préfixe d'article
#: (``provider_name:<id>`` stocké dans ``news_raw.ingestion_source``).
PROVIDER_REGISTRY: dict[str, tuple[str, str]] = {
    "alpaca": ("alpaca_news", "alpaca"),
    "finnhub": ("finnhub_news", "finnhub"),
}


@dataclass(frozen=True, slots=True)
class EventSentimentConfig:
    source_name: str = "alpaca_news"
    provider_name: str = "alpaca"
    news_provider: NewsProvider = "alpaca"
    start_utc: datetime | None = None
    end_utc: datetime | None = None
    page_limit: int = 50
    sleep_between_requests: float = 0.35
    regular_session_maps_to_same_day: bool = False
    checkpoint_overlap_minutes: int = 60
    initial_backfill_days: int = 365
    candidate_reactivation_backfill_days: int = 365

    finbert_model_name: str = "ProsusAI/finbert"
    finbert_model_version: str = "finbert_v1"
    finbert_model_revision: str | None = None
    finbert_batch_size: int = 16
    finbert_max_length: int = 256

    allow_sector_fallback: bool = True
    sentiment_pending_limit: int = 1000
    feature_version: str = "v2"
    macro_rule_version: str = "macro_rules_v1"
    feature_rolling_windows: tuple[int, ...] = (3, 5, 10, 20)
    feature_history_buffer_days: int = 45
    bootstrap_default_years: int = 10
    bootstrap_batch_days: int = 63

    # Garde-fous mapping article → ticker (cf. addendum métier add_Finnhub.md).
    provider_ticker_relevance_mode: TickerRelevanceMode = "provider_default"
    max_tickers_per_article: int = 25
    #: Seuil minimum de pertinence (mode ``"scored"`` uniquement). Les
    #: paires (article, symbole) sous ce seuil sont **filtrées** avant
    #: insertion dans ``news_ticker_map`` (compteur ``relevance_filtered``).
    #: Borne stricte : ``0.0 <= min_relevance_score <= 1.0``. ``0.0`` =
    #: pas de filtrage (les scores restent stockés pour audit + pondération
    #: downstream).
    min_relevance_score: float = 0.0

    # Niveau 4 — re-scoring FinBERT contextualisé par couple (article, symbol).
    # Désactivé par défaut (opt-in via CLI/IHM). Quand activé, le pipeline
    # produit une ligne dans ``news_ticker_sentiment`` pour chaque paire
    # ``(article, symbol)`` issue de ``news_ticker_map`` qui n'a pas encore
    # de score contextualisé. Garde-fous perf :
    #
    # * ``contextual_scoring_min_relevance`` : skip les paires dont
    #   ``relevance_score < seuil`` (réutilise le Niveau 2/3).
    # * ``contextual_scoring_max_pairs_per_run`` : cap dur sur le nombre de
    #   paires scorées par run (évite l'explosion N×M tokenisations).
    enable_contextual_scoring: bool = False
    contextual_scoring_min_relevance: float = 0.0
    contextual_scoring_max_pairs_per_run: int = 5000

    def __post_init__(self) -> None:
        if self.page_limit < 1:
            raise ValueError("page_limit doit être >= 1.")
        if self.sleep_between_requests < 0:
            raise ValueError("sleep_between_requests doit être >= 0.")
        if self.checkpoint_overlap_minutes < 0:
            raise ValueError("checkpoint_overlap_minutes doit être >= 0.")
        if self.initial_backfill_days < 1:
            raise ValueError("initial_backfill_days doit être >= 1.")
        if self.candidate_reactivation_backfill_days < 1:
            raise ValueError("candidate_reactivation_backfill_days doit être >= 1.")
        if self.finbert_batch_size < 1:
            raise ValueError("finbert_batch_size doit être >= 1.")
        if self.finbert_max_length < 32:
            raise ValueError("finbert_max_length doit être >= 32.")
        if self.sentiment_pending_limit < 1:
            raise ValueError("sentiment_pending_limit doit être >= 1.")
        if not self.feature_rolling_windows:
            raise ValueError("feature_rolling_windows ne doit pas être vide.")
        if any(window < 2 for window in self.feature_rolling_windows):
            raise ValueError("feature_rolling_windows doit contenir des fenêtres >= 2.")
        if tuple(sorted(set(self.feature_rolling_windows))) != self.feature_rolling_windows:
            raise ValueError("feature_rolling_windows doit être trié, sans doublons.")
        if self.feature_history_buffer_days < max(self.feature_rolling_windows):
            raise ValueError("feature_history_buffer_days doit couvrir au moins la plus grande fenêtre rolling.")
        if self.bootstrap_default_years < 1:
            raise ValueError("bootstrap_default_years doit être >= 1.")
        if self.bootstrap_batch_days < 1:
            raise ValueError("bootstrap_batch_days doit être >= 1.")
        if self.news_provider not in PROVIDER_REGISTRY:
            raise ValueError(
                f"news_provider doit être l'un de {sorted(PROVIDER_REGISTRY)} (reçu: {self.news_provider!r})."
            )
        if self.provider_ticker_relevance_mode not in {"provider_default", "strict", "scored"}:
            raise ValueError(
                "provider_ticker_relevance_mode doit valoir 'provider_default', 'strict' ou 'scored'."
            )
        if self.max_tickers_per_article < 1:
            raise ValueError("max_tickers_per_article doit être >= 1.")
        if not 0.0 <= self.min_relevance_score <= 1.0:
            raise ValueError("min_relevance_score doit être dans [0.0, 1.0].")
        if not 0.0 <= self.contextual_scoring_min_relevance <= 1.0:
            raise ValueError("contextual_scoring_min_relevance doit être dans [0.0, 1.0].")
        if self.contextual_scoring_max_pairs_per_run < 1:
            raise ValueError("contextual_scoring_max_pairs_per_run doit être >= 1.")

    @classmethod
    def for_provider(cls, news_provider: NewsProvider, **overrides: object) -> "EventSentimentConfig":
        """Fabrique une config avec ``source_name``/``provider_name`` cohérents.

        Les ``overrides`` explicites priment sur le mapping par défaut, ce qui
        permet aux tests de forcer un alias particulier si besoin.
        """
        if news_provider not in PROVIDER_REGISTRY:
            raise ValueError(
                f"news_provider inconnu: {news_provider!r} (attendu: {sorted(PROVIDER_REGISTRY)})."
            )
        source_name, provider_name = PROVIDER_REGISTRY[news_provider]
        kwargs: dict[str, object] = {
            "news_provider": news_provider,
            "source_name": source_name,
            "provider_name": provider_name,
        }
        kwargs.update(overrides)
        return cls(**kwargs)  # type: ignore[arg-type]


