"""Read-only clock semantics evidence, no timestamp repair or production change."""
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from scripts.research import us_consensus_reliability_20261022 as parent
from scripts.research.us_consensus_reliability_sip_20261022 import CHILD


def run():
    parent.check(CHILD)
    root=CHILD/'clock-audit'
    if root.exists():raise FileExistsError('Immutable clock audit')
    root.mkdir()
    parent.save(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_sha256=parent.digest(Path(__file__)),parent_report_sha256=parent.digest(CHILD/'report.json'),
        purpose='Diagnose ingestion default CURRENT_TIMESTAMP versus explicit UTC observations; no correction applied',
        sql='One SELECT session/global/system zones and UTC/local clocks, then ROLLBACK',sql_writes=False))
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            clock=dict(conn.execute(text('''SELECT @@session.time_zone AS session_zone,
                @@global.time_zone AS global_zone,@@system_time_zone AS system_zone,
                UTC_TIMESTAMP() AS utc_now,CURRENT_TIMESTAMP() AS db_now''')).mappings().one())
            conn.rollback()
    finally:engine.dispose()
    parent.save(root/'server-clock.json',clock)
    f=pd.read_parquet(CHILD/'consensus.parquet')
    runs=pd.read_parquet(CHILD/'runs.parquet').set_index('run_id')
    observed=pd.to_datetime(f.observed_at,utc=True)
    ingested=pd.to_datetime(f.ingestion_at,utc=True)
    available=pd.to_datetime(f.available_at,utc=True)
    finish=pd.to_datetime(f.run_id.map(runs.finished_at),utc=True)
    completed=f.run_id.map(runs.status).eq('COMPLETED')
    offset=(ingested-observed).dt.total_seconds()
    with_ingestion=pd.concat([observed,ingested,available,finish],axis=1).max(axis=1)
    without_ingestion=pd.concat([observed,available,finish],axis=1).max(axis=1)
    opens=parent.schedule().opening.astype('int64').to_numpy()
    a=np.searchsorted(opens,with_ingestion[completed].astype('int64'),side='right')
    b=np.searchsorted(opens,without_ingestion[completed].astype('int64'),side='right')
    result=dict(status='INGESTION_TIMEZONE_UNQUALIFIED_NO_REPAIR_APPLIED',rows=len(f),
        completed_run_rows=int(completed.sum()),
        completed_rows_ingestion_naively_after_run_finish=int((completed&ingested.gt(finish)).sum()),
        ingestion_minus_observed_seconds=dict(min=float(offset.min()),median=float(offset.median()),max=float(offset.max())),
        server_db_minus_utc_seconds=(clock['db_now']-clock['utc_now']).total_seconds(),
        next_open_changes_if_ingestion_excluded=int((a!=b).sum()),
        interpretation='Server defaults local Paris(+2h here); default naive ingestion conflicts with explicitly UTC observed/available/run timestamps. Current max delays receipt conservatively; NOT a qualified UTC ingestion history.',
        conclusion='All completed sample rows retain same first eligible NYSE open without ingestion; primary results not recalculated or improved. Production needs explicit UTC ingestion on future writes; legacy evidence retained.',
        sql_writes=False,production_changes=False,
        files={p.name:parent.digest(p) for p in root.iterdir() if p.is_file()})
    parent.save(root/'report.json',result)
    print(result['status'],result['completed_rows_ingestion_naively_after_run_finish'],flush=True)


if __name__=='__main__':run()
