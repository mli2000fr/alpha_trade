"""modelFactory/oracle — Oracle Layer au-dessus du Global Model B25.

L'Oracle est un **TARGET**, jamais une **FEATURE** (cf. ``doc/ml_oracle.md``).
Ce package contient :

- ``config`` : configuration dédiée à la couche Oracle (ne touche pas
  ``TrainingConfig`` / B25) ;
- ``leakage`` : garde-fous anti-leakage (§27 de la spec).

Séquençage : S0 (fondations) → S1 (labels) → … (cf. ``doc/ml_oracle_sprint.md``).
"""
from modelFactory.oracle import config, leakage
from modelFactory.oracle.config import (
    OracleConfig,
    load_backtest_batch_id,
    load_oracle_config,
    resolve_oracle_batch_id,
)
from modelFactory.oracle.leakage import (
    FORBIDDEN_ORACLE_FEATURES,
    assert_availability_after_prediction,
    assert_no_forbidden_features,
    assert_no_future_features,
)

__all__ = [
    "config",
    "leakage",
    "OracleConfig",
    "load_backtest_batch_id",
    "load_oracle_config",
    "resolve_oracle_batch_id",
    "FORBIDDEN_ORACLE_FEATURES",
    "assert_availability_after_prediction",
    "assert_no_forbidden_features",
    "assert_no_future_features",
]
