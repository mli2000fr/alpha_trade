"""One validated source of settings for CLI, IHM and risk handoff."""
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class FilterConfig:
    enabled: bool = False
    model: str = 'gpt-6.1-sol'
    api_key_env: str = 'OPENAI_API_KEY'
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

    def __post_init__(self):
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
        if type(self.min_confidence) not in (int, float) or not math.isfinite(self.min_confidence) or not 0 <= self.min_confidence <= 1:
            raise ValueError('min_confidence doit être entre 0 et 1')
        if type(self.min_oracle_coverage_ratio) not in (int, float) or not math.isfinite(self.min_oracle_coverage_ratio) or not 0 < self.min_oracle_coverage_ratio <= 1:
            raise ValueError('min_oracle_coverage_ratio doit être dans ]0,1]')
        if self.account_id != 'default':
            raise ValueError('Filtre LLM réservé au compte principal default PAPER')
        if not self.model or self.api_key_env != 'OPENAI_API_KEY':
            raise ValueError('Modèle requis et clé OPENAI_API_KEY exclusivement')

    def snapshot(self):
        return asdict(self)  # Contains only the environment variable NAME, never its value.


def load_filter_config(path=None):
    from common.config_loader import load_config
    values = (load_config(path) or {}).get('llm_directional_filter') or {}
    unknown = set(values) - set(FilterConfig.__dataclass_fields__)
    if unknown:
        raise ValueError(f'Options LLM inconnues: {sorted(unknown)}')
    return FilterConfig(**values)
