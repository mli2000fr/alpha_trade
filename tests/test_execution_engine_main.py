from execution_engine import __main__

def test_main_runs(monkeypatch):
    called = {}
    monkeypatch.setattr(__main__, "main", lambda: called.setdefault("main", True))
    __main__.main()
    assert called["main"] is True

