import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_merger_replay as replay


def histories(monkeypatch):
    days = pd.bdate_range(end='2026-08-14', periods=657)
    raw = pd.DataFrame(dict(date=days, open=100., high=101., low=99., close=100., volume=1000.))
    bars = raw.assign(symbol='AVB', adj_close=100., is_filled=0, instrument_id='avb')
    columns = ['open', 'high', 'low', 'close', 'adj_close']
    bars.loc[bars.index[-25:], columns] /= replay.RATIO
    bars.loc[bars.index[-25:], 'volume'] *= replay.RATIO
    eqr = pd.DataFrame(dict(date=pd.to_datetime(['2026-08-14', '2026-08-17']),
        open=40., high=41., low=39., close=40., volume=2000.))
    successor = pd.concat([eqr, eqr.tail(1).assign(date=pd.Timestamp('2026-08-18'))], ignore_index=True)
    archive = {'AVB': raw, 'EQR': eqr, 'VMRK': successor}
    monkeypatch.setattr(replay, 'provider_frame', lambda cache, symbol: archive[symbol].copy())
    monkeypatch.setattr(replay, 'read', lambda path: {'id': 'survivor'})
    calendar = pd.to_datetime(['2026-08-17', '2026-08-18'])
    return bars, archive, calendar


def test_mixed_share_basis_restores_only_matched_recent_dates(monkeypatch, tmp_path):
    bars, archive, calendar = histories(monkeypatch)
    original = bars.copy(deep=True)
    result, proof = replay.prepare_prices(bars, tmp_path, calendar)
    avb = result.loc[result.symbol.eq('AVB')]
    assert proof['avb_raw_rows'] == 632
    assert proof['avb_successor_adjusted_rows'] == 25
    assert len(avb) == 657
    assert np.allclose(avb[['open', 'high', 'low', 'close', 'volume']],
                       archive['AVB'][['open', 'high', 'low', 'close', 'volume']])
    assert not avb.date.ge('2026-08-17').any()
    pd.testing.assert_frame_equal(bars, original)


def test_unexplained_price_basis_is_rejected(monkeypatch, tmp_path):
    bars, _, calendar = histories(monkeypatch)
    bars.loc[1, 'open'] *= .5
    with pytest.raises(ValueError, match='Historical AVB basis not qualified'):
        replay.prepare_prices(bars, tmp_path, calendar)


def test_alias_overlap_discrepancy_is_not_silently_accepted(monkeypatch, tmp_path):
    bars, archive, calendar = histories(monkeypatch)
    archive['VMRK'].loc[0, 'close'] = 39.
    with pytest.raises(ValueError, match='alias OHLC discrepancy'):
        replay.prepare_prices(bars, tmp_path, calendar)


def test_missing_successor_tail_does_not_create_predecessor_bars(monkeypatch, tmp_path):
    bars, archive, calendar = histories(monkeypatch)
    archive['VMRK'] = archive['VMRK'].iloc[:2]
    with pytest.raises(ValueError, match='Missing successor tail'):
        replay.prepare_prices(bars, tmp_path, calendar)
