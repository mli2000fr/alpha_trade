"""Reuse predecessor HTTP receipts, snapshot added symbols, recover missing tails."""
import argparse
from pathlib import Path
import gzip,json,shutil
import logging
import pandas as pd

from scripts.research.us_selected_universe_per_symbol_selection_20261104 import OUT,PREVIOUS
from scripts.research import us_selected_universe_intraday_inputs_20261104 as sql
from scripts.research import us_selected_universe_intraday_repair_20261104 as repair
from scripts.research import us_selected_universe_intraday_tail_20261104 as tail
from scripts.research import us_selected_universe_split_qualification_20261104 as splits


def main(phase):
    assert (OUT/'selection-report.json').exists()
    if phase=='sql':
        sql.OUT=OUT;sql.PRIOR=OUT/'input-cohort';sql.main()
    elif phase=='recover':
        dest=OUT/'recovery'
        if not dest.exists():
            shutil.copytree(PREVIOUS/'recovery',dest)
        repair.OUT=OUT;repair.main()
    elif phase=='tail':
        original=tail.fetch_intraday
        known=json.loads((PREVIOUS/'tail-recovery/report.json').read_text())['cases']
        known={r['symbol']:r for r in known}
        def cached(symbol,**kwargs):
            row=known.get(symbol)
            if row:
                start=int(pd.Timestamp(row['start']).tz_localize('America/New_York').tz_convert('UTC').timestamp())
                end=int((pd.Timestamp(row['end'])+pd.Timedelta(days=1)).tz_localize('America/New_York').tz_convert('UTC').timestamp())
                if start==kwargs['start_epoch'] and end==kwargs['end_epoch']:
                    logging.info('Reuse archived SIP tail %s',symbol)
                    return json.loads(gzip.decompress((PREVIOUS/'tail-recovery'/f'{symbol}.json.gz').read_bytes()))
            return original(symbol,**kwargs)
        tail.fetch_intraday=cached;tail.OUT=OUT;tail.main()
    elif phase=='splits':
        splits.OUT=OUT;splits.main()
    else:raise ValueError(phase)


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['sql','recover','tail','splits'],required=True)
    main(p.parse_args().phase)
