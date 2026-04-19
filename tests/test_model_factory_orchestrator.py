from modelFactory import orchestrator

def test_orchestrator_importable():
    assert hasattr(orchestrator, "__doc__")

