from execution_engine import broker_adapter

def test_broker_adapter_importable():
    assert hasattr(broker_adapter, "__doc__")

