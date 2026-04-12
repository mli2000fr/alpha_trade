from service.alpaca.client import fetch_hourly_bars

if __name__ == "__main__":
    bars = fetch_hourly_bars('AAPL')
    print(f"Nombre de bars récupérés : {len(bars)}")
    if bars:
        print("Premier bar :", bars[0])

