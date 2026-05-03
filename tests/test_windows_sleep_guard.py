from __future__ import annotations

from common import windows_sleep_guard


def test_prevent_windows_sleep_is_noop_when_disabled(monkeypatch) -> None:
    calls: list[int] = []

    monkeypatch.setattr(windows_sleep_guard, "_is_windows", lambda: True)
    monkeypatch.setattr(windows_sleep_guard, "_set_thread_execution_state", lambda flags: calls.append(flags) or 1)

    with windows_sleep_guard.prevent_windows_sleep(enabled=False) as activated:
        assert activated is False

    assert calls == []


def test_prevent_windows_sleep_activates_and_restores_state(monkeypatch) -> None:
    calls: list[int] = []

    monkeypatch.setattr(windows_sleep_guard, "_is_windows", lambda: True)
    monkeypatch.setattr(windows_sleep_guard, "_set_thread_execution_state", lambda flags: calls.append(flags) or 1)

    with windows_sleep_guard.prevent_windows_sleep() as activated:
        assert activated is True

    assert calls == [
        windows_sleep_guard.ES_CONTINUOUS | windows_sleep_guard.ES_SYSTEM_REQUIRED,
        windows_sleep_guard.ES_CONTINUOUS,
    ]


def test_prevent_windows_sleep_restores_state_even_on_error(monkeypatch) -> None:
    calls: list[int] = []

    monkeypatch.setattr(windows_sleep_guard, "_is_windows", lambda: True)
    monkeypatch.setattr(windows_sleep_guard, "_set_thread_execution_state", lambda flags: calls.append(flags) or 1)

    try:
        with windows_sleep_guard.prevent_windows_sleep():
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert calls[-1] == windows_sleep_guard.ES_CONTINUOUS

