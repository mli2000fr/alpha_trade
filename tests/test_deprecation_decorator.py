"""Phase C / S18.2 — Tests décorateur deprecation v1."""
from __future__ import annotations

import warnings

from core._deprecation import deprecated_v1


def test_deprecated_v1_emits_warning_once():
    @deprecated_v1(reason="use new_api()", since="1.0")
    def old_api(x):
        return x * 2

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert old_api(3) == 6
        assert old_api(4) == 8  # second call : pas de re-warn (cache)
    deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecation_warnings) == 1
    assert "old_api" in str(deprecation_warnings[0].message)


def test_deprecated_v1_marks_function():
    @deprecated_v1(reason="x", since="1.0")
    def f():
        return 1

    assert getattr(f, "__deprecated__", False) is True
    assert f.__deprecation_reason__ == "x"

