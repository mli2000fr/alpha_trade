"""Split-adjusted SIP child adapter, no editing of sealed raw-validation v1."""
import argparse
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from scripts.research import us_consensus_confirmation_exit_20261022 as study

ROOT=Path('artifacts/research/us_consensus_confirmation_exit/20261022-v2')
AMENDMENT=Path('doc/ml/consensus_confirmation_sortie_amendement_split_20261022.md')


def prepare(root):
    study.check(study.ROOT)
    if root.exists():raise FileExistsError('New immutable child required')
    root.mkdir(parents=True)
    for name in ('features.parquet','frequency.json'):
        shutil.copy2(study.ROOT/name,root/name)
    protocol=study.parent.read(study.ROOT/'protocol.json')
    protocol['preparation_parent']=str(study.ROOT)
    protocol['price_adjustment']='split'
    protocol['amendment']='Actual SIP daily storage split; fixed before new prices/returns, no relabel or fallback'
    for path in (Path(__file__),AMENDMENT,Path('tests/test_us_consensus_confirmation_exit_split_20261022.py')):
        protocol['sources'][str(path)]=study.parent.digest(path)
    study.parent.save(root/'protocol.json',protocol)
    print('Split-only child; features and cutoffs unchanged',flush=True)


def valid_window(group,days,registry,symbol):
    if group is None:return None,'MISSING_SYMBOL'
    g=group.reindex(days)
    valid=(g.is_filled.eq(0)&g[['open','high','low','close','volume']].gt(0).all(axis=1)&
        np.isfinite(g[['open','high','low','close','volume']]).all(axis=1)&
        g.high.ge(g[['open','close','low']].max(axis=1))&g.low.le(g[['open','close','high']].min(axis=1)))
    if not valid.all():return None,'MISSING_OR_INVALID_FULL_WINDOW'
    if g.data_source.isna().any() or not g.data_source.eq('alpaca_sip').all():return None,'NON_SIP'
    if g.data_adjustment.isna().any() or not g.data_adjustment.eq('split').all():return None,'NOT_SPLIT_ADJUSTED'
    if g.instrument_id.isna().any() or g.instrument_id.nunique()!=1:return None,'UNKNOWN_OR_CHANGED_IDENTITY'
    if any(e.crosses(days[0],days[-1]) for e in registry.get(symbol,())):return None,'KNOWN_IDENTITY_BREAK'
    return g,'AVAILABLE_RESEARCH_NOT_PRODUCTION_QUALIFIED'


def run(root):
    # Explicit dependency adapter; caller data still retain the true 'split' tag.
    original=study.valid_window
    try:
        study.valid_window=valid_window
        study.run(root)
    finally:study.valid_window=original


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('prepare','prices','run'),required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT)
    a=parser.parse_args()
    {'prepare':prepare,'prices':study.prices,'run':run}[a.phase](a.output_dir)
