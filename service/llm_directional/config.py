"""One validated source of settings for CLI, IHM and risk handoff."""
from dataclasses import asdict, dataclass
import math
from .protections import ProtectionProfile


@dataclass(frozen=True)
class FilterConfig:
    enabled: bool = False
    provider: str = 'openai'  # Absent in archived runs: preserve GPT semantics.
    model: str = 'gpt-6.1-sol'
    api_key_env: str = 'OPENAI_API_KEY'
    deepseek_model: str = 'deepseek-flash'
    deepseek_api_key_env: str = 'DEEPSEEK_API_KEY'
    default_symbol_source: str = 'universe-file:univers_filtred_tradable.txt'
    default_oracle_batch_id: str = 'model-factory-20261003082853-e98332'
    oracle_top_n: int = 20
    max_selected: int = 5
    min_oracle_coverage_ratio: float = .90
    min_confidence: float = .75
    # Absent from old archived configurations: preserve their exact semantics.
    scoring_mode: str = 'legacy_confidence'
    long_score_threshold: int = 8
    short_score_threshold: int = 3
    min_sources: int = 2
    max_source_age_days: int = 30
    max_run_age_hours: int = 24
    timeout_seconds: int = 120
    max_output_tokens: int = 6000
    max_tool_calls: int = 5
    account_id: str = 'default'
    horizon: int = 20
    allow_long: bool = True  # Missing from historical snapshots: LONG remains allowed.
    allow_short: bool = False  # Explicit opt-in; absent in historical LONG-only snapshots.
    protections: ProtectionProfile | dict | None = None
    analysis_mode: str = 'web_search'
    consensus_max_periods: int = 4
    consensus_history_count: int = 3
    consensus_max_age_days: int = 7
    local_news_max_articles: int = 8
    local_news_max_chars: int = 2400
    min_local_sources: int = 1
    deepseek_search_queries: int = 2
    deepseek_search_results: int = 5
    deepseek_fetch_pages: int = 2
    deepseek_web_text_chars: int = 6000
    evidence_consensus_max_age_hours: int = 72
    evidence_news_max_age_days: int = 7
    evidence_news_max_receipt_age_hours: int = 72
    evidence_calendar_max_age_hours: int = 72
    evidence_sec_max_age_days: int = 14
    evidence_sec_max_documents: int = 3
    evidence_sec_excerpt_chars: int = 1800
    evidence_fundamental_max_fetch_age_days: int = 45
    evidence_fundamental_max_filing_age_days: int = 120
    evidence_fundamental_max_period_age_days: int = 200
    evidence_context_max_age_minutes: int = 30

    def __post_init__(self):
        if self.scoring_mode not in ('legacy_confidence', 'direction_1_10'):
            raise ValueError('scoring_mode : legacy_confidence | direction_1_10')
        if (type(self.short_score_threshold) is not int or type(self.long_score_threshold) is not int
                or not 1 <= self.short_score_threshold < self.long_score_threshold <= 10):
            raise ValueError('Seuils score : entiers 1 <= short_score_threshold < long_score_threshold <= 10')
        if isinstance(self.protections, dict):
            object.__setattr__(self, 'protections', ProtectionProfile(**self.protections))
        elif self.protections is not None and not isinstance(self.protections, ProtectionProfile):
            raise ValueError('protections doit être une configuration valide')
        for name, minimum, maximum in (
            ('oracle_top_n', 1, 100), ('max_selected', 0, self.oracle_top_n),
            ('min_sources', 1, 20), ('max_source_age_days', 1, 365),
            ('max_run_age_hours', 1, 48), ('timeout_seconds', 10, 600),
            ('max_output_tokens', 1000, 32000), ('max_tool_calls', 1, 20),
            ('horizon', 1, 60),
            ('consensus_max_periods',1,8), ('consensus_history_count',0,10),
            ('consensus_max_age_days',1,30), ('local_news_max_articles',0,20),
            ('local_news_max_chars',300,6000), ('min_local_sources',1,20),
            ('deepseek_search_queries',1,2), ('deepseek_search_results',1,10),
            ('deepseek_fetch_pages',0,5), ('deepseek_web_text_chars',500,12000),
            ('evidence_consensus_max_age_hours',1,168), ('evidence_news_max_age_days',1,30),
            ('evidence_news_max_receipt_age_hours',1,168), ('evidence_calendar_max_age_hours',1,168),
            ('evidence_sec_max_age_days',1,60), ('evidence_sec_max_documents',0,5),
            ('evidence_sec_excerpt_chars',500,4000), ('evidence_fundamental_max_fetch_age_days',1,90),
            ('evidence_fundamental_max_filing_age_days',30,180), ('evidence_fundamental_max_period_age_days',90,400),
            ('evidence_context_max_age_minutes',1,120),
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f'{name}: entier entre {minimum} et {maximum} requis')
        if type(self.enabled) is not bool:
            raise ValueError('enabled doit être booléen')
        for name in ('allow_long', 'allow_short'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'{name} doit être booléen')
        if self.analysis_mode not in ('web_search','local_data_only'):
            raise ValueError('analysis_mode doit être web_search ou local_data_only')
        if not isinstance(self.default_symbol_source, str) or not self.default_symbol_source.strip():
            raise ValueError('default_symbol_source doit être une source non vide')
        if (not isinstance(self.default_oracle_batch_id, str)
                or not self.default_oracle_batch_id.strip()
                or any(not (c.isalnum() or c in '-_') for c in self.default_oracle_batch_id)):
            raise ValueError('default_oracle_batch_id doit être un identifiant de batch explicite')
        if type(self.min_confidence) not in (int, float) or not math.isfinite(self.min_confidence) or not 0 <= self.min_confidence <= 1:
            raise ValueError('min_confidence doit être entre 0 et 1')
        if type(self.min_oracle_coverage_ratio) not in (int, float) or not math.isfinite(self.min_oracle_coverage_ratio) or not 0 < self.min_oracle_coverage_ratio <= 1:
            raise ValueError('min_oracle_coverage_ratio doit être dans ]0,1]')
        if self.account_id != 'default':
            raise ValueError('Filtre LLM réservé au compte principal default PAPER')
        if self.provider not in ('openai', 'deepseek'):
            raise ValueError('provider doit être openai ou deepseek')
        if not isinstance(self.model, str) or not self.model.strip() or self.api_key_env != 'OPENAI_API_KEY':
            raise ValueError('Modèle Web OpenAI requis et clé OPENAI_API_KEY exclusivement')
        if not isinstance(self.deepseek_model, str) or not self.deepseek_model.strip() or self.deepseek_api_key_env != 'DEEPSEEK_API_KEY':
            raise ValueError('Modèle DeepSeek requis et clé DEEPSEEK_API_KEY exclusivement')

    @property
    def provider_label(self):
        return 'DeepSeek' if self.provider == 'deepseek' else 'GPT'

    @property
    def analysis_model(self):
        return self.deepseek_model if self.provider == 'deepseek' else self.model

    @property
    def mode_label(self):
        return 'données locales uniquement' if self.analysis_mode=='local_data_only' else 'recherche Web + données locales'

    def snapshot(self):
        return asdict(self)  # Contains only the environment variable NAME, never its value.


def load_filter_config(path=None):
    from common.config_loader import load_config
    values = dict((load_config(path) or {}).get('llm_directional_filter') or {})
    unknown = set(values) - set(FilterConfig.__dataclass_fields__)
    if unknown:
        raise ValueError(f'Options LLM inconnues: {sorted(unknown)}')
    return FilterConfig(**values)
