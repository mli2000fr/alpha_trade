from execution_engine import executor

def test_executor_importable():
    assert hasattr(executor, "__doc__")

