import json

import pandas as pd
import pytest

from scripts.research.us_short_loss_attribution import cost_identity, digest, excursions


@pytest.mark.parametrize('side,sign', [('sell', -1), ('buy', 1)])
def test_independent_price_fee_borrow_decomposition(tmp_path, side, sign):
    directory = tmp_path/'cases'/'test'
    directory.mkdir(parents=True)
    borrow = .12 if side == 'sell' else 0.
    gross, fees = sign*10*(110-100), .0008*10*(100+110)
    pnl = gross-fees-borrow
    pd.DataFrame([dict(quantity=10., entry_price=100., exit_price=110., borrow_cost=borrow,
        pnl=pnl)]).to_parquet(directory/'trades.parquet', index=False)
    (directory/'open-positions.json').write_text('[]')
    row = dict(year=2025, case='test', side=side, financing_usd=0., net_pnl_usd=pnl,
        files={n: digest(directory/n) for n in ['trades.parquet', 'open-positions.json']})
    _, audit = cost_identity(tmp_path, row)
    assert audit['fixed_trades_price_pnl'] == gross
    assert audit['transaction_fees'] == pytest.approx(fees)
    assert audit['borrow'] == borrow and audit['max_accounting_error'] < 1e-9
    (directory/'open-positions.json').write_text('[{}]')
    with pytest.raises(ValueError, match='artifact changed'):
        cost_identity(tmp_path, row)


def test_excursion_does_not_use_future_order_inside_exit_bar():
    path = pd.DataFrame(dict(bar_timestamp=pd.to_datetime(['2025-01-06 14:30Z', '2025-01-06 14:35Z',
        '2025-01-06 14:40Z']), low=[98., 97., 80.], high=[102., 103., 150.]))
    t = dict(side='sell', entry_price=100., exit_price=105.,
        entry_timestamp=path.bar_timestamp.iloc[0], exit_timestamp=path.bar_timestamp.iloc[2])
    favorable, adverse = excursions(t, path)
    assert favorable == pytest.approx(3.) and adverse == pytest.approx(5.)
