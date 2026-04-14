# Pour exécution directe, corrige l'import relatif pour le mode script
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.assets import insert_assets_to_db
from service.alpaca.clientAlpaca import fetch_alpaca_assets

def main():
    assets = fetch_alpaca_assets()
    insert_assets_to_db(assets)


if __name__ == "__main__":
    main()



