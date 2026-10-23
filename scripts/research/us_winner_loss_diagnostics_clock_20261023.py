"""Preserve v1; correct native STOP timestamps (bar END) in a separate audit v2."""
from pathlib import Path
import pandas as pd
from scripts.research import us_winner_loss_diagnostics_20261023 as base

ROOT=Path('artifacts/research/us_winner_loss_diagnostics/20261023-v2')
DOC=Path('doc/ml/winner_audit_pertes_amendement_horloge_20261023.md')
ORIGINAL_SIGNATURES=base.path_signatures


def corrected_signatures(held,future,**kw):
    actual_exit=kw['exit_time']
    if kw['reason']=='STOP':
        after=held[held.bar_timestamp.eq(actual_exit)]
        # The original caller retained the bar starting at actual_exit, when it
        # exists. It is the first fully POST-exit bar, not the exit bar.
        corrected_future=pd.concat([after,future],ignore_index=True) if kw['complete'] else future
        adjusted=dict(kw,exit_time=actual_exit-pd.Timedelta(minutes=5))
        out=ORIGINAL_SIGNATURES(held[held.bar_timestamp.lt(actual_exit)],corrected_future,**adjusted)
        if out['post_stop_1R_time'] is not None:
            out['post_stop_1R_calendar_days']=(out['post_stop_1R_time']-actual_exit).total_seconds()/86400
        return out
    return ORIGINAL_SIGNATURES(held,future,**kw)


def run():
    original_save,original_doc=base.save_new,base.DOC
    def bind(path,value):
        if Path(path).name=='protocol.json':
            extra=[Path(__file__),DOC,Path('scripts/research/us_winner_loss_diagnostics_clock_audit_20261023.py'),
                Path('tests/test_us_winner_loss_diagnostics_clock_20261023.py'),Path('backtesting/winner_intraday.py')]
            value['sources'].update({str(x):base.digest(x) for x in extra})
            value['source_clock']='Native STOP intrabar at bar END; open exits at bar START'
            value['technical_amendment']='Separate clock adapter; no economic replay or original source edit'
        return original_save(path,value)
    base.path_signatures=corrected_signatures;base.DOC=DOC;base.save_new=bind
    try:base.run(ROOT)
    finally:base.path_signatures=ORIGINAL_SIGNATURES;base.DOC=original_doc;base.save_new=original_save
    from scripts.research.us_winner_loss_diagnostics_clock_audit_20261023 import audit
    audit(ROOT)


if __name__=='__main__':run()
