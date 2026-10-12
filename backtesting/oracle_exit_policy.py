"""Explicit research exits, separate from Oracle training and broker defaults."""
from dataclasses import dataclass
import math
from collections.abc import Mapping

from common.config_loader import load_config


@dataclass(frozen=True)
class OracleBacktestExitPolicy:
    take_profit_pct: float = .20
    stop_loss_pct: float = .10

    def __post_init__(self):
        for name in ('take_profit_pct', 'stop_loss_pct'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value < 1:
                raise ValueError(f'oracle_backtest.{name} doit être une fraction dans ]0,1[')


def load_oracle_backtest_exit_policy(path=None):
    """Missing section keeps defaults; malformed/unknown values fail closed."""
    section = load_config(path).get('oracle_backtest', {})
    if not isinstance(section, Mapping):
        raise ValueError('oracle_backtest doit être un bloc YAML')
    unknown = set(section) - {'take_profit_pct', 'stop_loss_pct'}
    if unknown:
        raise ValueError(f'Paramètres oracle_backtest inconnus : {sorted(unknown)}')
    return OracleBacktestExitPolicy(**section)
