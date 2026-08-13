import sys
import traceback

sys.path.insert(0, r"F:\projets")

try:
    import ihm.pages.backtesting as page
    print("import OK")
    print("DEFAULT_SECTOR_MULTIPLIERS_PATH =", page.DEFAULT_SECTOR_MULTIPLIERS_PATH)
    print(page._summarize_sector_multipliers(page.DEFAULT_SECTOR_MULTIPLIERS_PATH))
    print("runs avec trades.csv :", len(page._list_backtest_runs_with_trades()))
except Exception:
    traceback.print_exc()
