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
    oracle_top_n: int = 10
    max_selected: int = 5
    min_oracle_coverage_ratio: float = .90
    min_confidence: float = .75
    min_sources: int = 2
    max_source_age_days: int = 30
    max_run_age_hours: int = 24
    timeout_seconds: int = 120
    max_output_tokens: int = 6000
    max_tool_calls: int = 5
    account_id: str = 'default'
    horizon: int = 20
    allow_short: bool = False  # Explicit opt-in; absent in historical LONG-only snapshots.
    protections: ProtectionProfile | dict | None = None

    def __post_init__(self):
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
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f'{name}: entier entre {minimum} et {maximum} requis')
        if type(self.enabled) is not bool:
            raise ValueError('enabled doit être booléen')
        if type(self.allow_short) is not bool:
            raise ValueError('allow_short doit être booléen')
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

    def snapshot(self):
        return asdict(self)  # Contains only the environment variable NAME, never its value.


def load_filter_config(path=None):
    from common.config_loader import load_config
    values = (load_config(path) or {}).get('llm_directional_filter') or {}
    unknown = set(values) - set(FilterConfig.__dataclass_fields__)
    if unknown:
        raise ValueError(f'Options LLM inconnues: {sorted(unknown)}')
    return FilterConfig(**values)
