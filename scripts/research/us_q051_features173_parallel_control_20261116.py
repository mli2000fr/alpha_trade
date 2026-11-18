"""Run a sealed matched control; defer IHM publication until explicit release.

Native economic calculations are untouched. Release files serialize publication
after the main coordinator, whose older in-memory sequence remains active.
"""
import argparse
import time
from pathlib import Path
from unittest.mock import patch

from scripts.research.us_q051_features173_replay_20261116 import ROOT,run_case,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def main(name):
    from ihm.services import backtesting_import
    original=backtesting_import.import_continuous_winner
    base=ROOT/'cases'/name
    atomic_json(ROOT/(name+'-parallel-launch.json'),dict(case=name,launcher_sha256=digest(Path(__file__)),
        sealed_replay_protocol_sha256=digest(ROOT/'replay-protocol.json'),
        native_economics_unchanged=True,publication_deferred=True))
    def deferred(source,**kwargs):
        atomic_json(base/'import-ready.json',dict(status='WAITING_PUBLICATION_RELEASE',run_id=kwargs['run_id']))
        while not (base/'import-release.json').is_file():time.sleep(1)
        result=original(source,**kwargs)
        atomic_json(base/'import-completed.json',dict(status='PUBLISHED',run_id=result['run_id']))
        return result
    with patch.object(backtesting_import,'import_continuous_winner',deferred):run_case(name)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=['CONTROL_SIMPLE','CONTROL_VOL20_REGIME'],required=True)
    main(p.parse_args().case)
