from __future__ import annotations

import os

from modelFactory.config import ReproducibilityConfig
from modelFactory.reproducibility import _MAX_NUMPY_SEED, apply_reproducibility


def test_apply_reproducibility_keeps_pythonhashseed_in_supported_range() -> None:
    state = apply_reproducibility(ReproducibilityConfig(seed=(2**63 - 2), deterministic=True))

    python_hash_seed = int(os.environ["PYTHONHASHSEED"])
    assert 0 <= python_hash_seed < _MAX_NUMPY_SEED
    assert python_hash_seed == state["python_hash_seed"]
    assert state["seed"] == 2**63 - 2

