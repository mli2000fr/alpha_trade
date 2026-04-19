from screener import stock_screener

def test_screener_stock_screener_importable():
    assert hasattr(stock_screener, "__doc__")

