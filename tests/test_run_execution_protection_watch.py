from execution_engine import protection_watcher


def test_run_execution_protection_watch_importable():
    assert callable(protection_watcher.main)
    assert callable(protection_watcher.parse_args)
