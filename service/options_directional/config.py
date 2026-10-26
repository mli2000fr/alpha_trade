from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class OptionsFilterConfig:
    enabled: bool = False
    oracle_top_n: int = 20
    min_combined_score: float = .5
    min_covered: int = 4
    min_oracle_coverage_ratio: float = .95
    max_age_hours: int = 72
    default_oracle_batch_id: str = 'model-factory-20261016180250-3b0515'

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError('options_directional_filter.enabled doit être booléen')
        for key, low, high in [('oracle_top_n', 1, 100), ('min_covered', 2, 100), ('max_age_hours', 1, 96)]:
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'{key}: entier entre {low} et {high}')
        for key, low, high in [('min_combined_score', 0, 1), ('min_oracle_coverage_ratio', .01, 1)]:
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f'{key}: valeur finie entre {low} et {high}')
        if not self.default_oracle_batch_id or any(c not in '-_' and not c.isalnum() for c in self.default_oracle_batch_id):
            raise ValueError('Identifiant Oracle explicite requis')

    def snapshot(self):
        return asdict(self)


def load_options_filter_config():
    from common.config_loader import load_config
    return OptionsFilterConfig(**((load_config() or {}).get('options_directional_filter') or {}))
