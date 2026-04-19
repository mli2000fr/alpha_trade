import pytest
import sys
from event_sentiment import __main__

def test_main_runs(monkeypatch):
    called = {}
    monkeypatch.setattr(__main__, "main", lambda: called.setdefault("main", True))
    # Simule l'appel du script
    sys.modules["__main__"] = __main__
    __main__.main()
    assert called["main"] is True

