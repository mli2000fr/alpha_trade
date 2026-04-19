from risk_management import run_risk

def test_run_risk_importable():
    assert hasattr(run_risk, "__doc__")

