from risk_management import circuit_breaker

def test_circuit_breaker_importable():
    assert hasattr(circuit_breaker, "__doc__")

