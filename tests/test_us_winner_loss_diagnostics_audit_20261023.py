import pandas as pd
import pytest
from scripts.research.us_winner_loss_diagnostics_audit_20261023 import scalar_excursions


def test_scalar_bounds_reserve_exit_bar_order():
    stamp=pd.Timestamp('2026-01-02 15:00Z')
    f=pd.DataFrame(dict(bar_timestamp=[stamp,stamp+pd.Timedelta(minutes=5)],
        bar_end_timestamp=[stamp+pd.Timedelta(minutes=5),stamp+pd.Timedelta(minutes=10)],
        high=[103,120],low=[99,85]))
    lo,hi,mae_lo,mae_hi=scalar_excursions(f,stamp,stamp+pd.Timedelta(minutes=5),100,93,'STOP')
    assert [lo,hi,mae_lo,mae_hi]==pytest.approx([3,20,7,15])
    assert scalar_excursions(f,stamp,stamp+pd.Timedelta(minutes=5),100,93,'STOP_GAP')==pytest.approx([3,3,7,7])


def test_instant_exit_has_no_completed_entry_bar():
    stamp=pd.Timestamp('2026-01-02 15:00Z')
    f=pd.DataFrame(dict(bar_timestamp=[stamp],bar_end_timestamp=[stamp+pd.Timedelta(minutes=5)],high=[120],low=[80]))
    assert scalar_excursions(f,stamp,stamp,100,93,'STOP')==pytest.approx([0,20,7,20])
