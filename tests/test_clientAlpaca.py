from service.alpaca import clientAlpaca

def test_clientAlpaca_importable():
    assert hasattr(clientAlpaca, "__doc__")

