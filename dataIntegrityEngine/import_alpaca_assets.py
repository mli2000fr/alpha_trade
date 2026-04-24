
from database.assets import insert_assets_to_db
from service.alpaca.clientAlpaca import fetch_alpaca_assets

def main():
    assets = fetch_alpaca_assets()
    insert_assets_to_db(assets)


if __name__ == "__main__":
    main()



