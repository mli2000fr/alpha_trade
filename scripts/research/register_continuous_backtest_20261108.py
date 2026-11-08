"""Add the completed annual-model continuous replay to IHM history, without replaying."""
import json
from pathlib import Path

from ihm.services.backtesting_import import import_continuous_winner


if __name__=='__main__':
    record=import_continuous_winner(
        Path('artifacts/research/us_winner_continuous_annual_models/20261108-v6'),
        run_id='20261108_continu_2021_2026_v6')
    print(json.dumps({k:record[k] for k in ('run_id','run_label','status','stdout_path')},ensure_ascii=False))
