"""Phase C / S15 — Tests des preuves Z3 (skippés sans z3-solver)."""
from __future__ import annotations

import pytest

z3 = pytest.importorskip("z3")  # noqa: F841 — declare optional dep


def test_idempotence_corporate_actions_proved():
    from formal.z3_invariants import idempotence_corporate_actions
    res = idempotence_corporate_actions.prove()
    assert res["determinism"] == "proved"
    assert res["discrimination"] == "proved"


def test_oco_synthetic_bracket_proved():
    from formal.z3_invariants import oco_synthetic_bracket
    res = oco_synthetic_bracket.prove()
    assert res["oco_exclusivity"] == "proved"


def test_no_double_execution_proved():
    from formal.z3_invariants import no_double_execution
    res = no_double_execution.prove()
    assert res["no_double_execution"] == "proved"

