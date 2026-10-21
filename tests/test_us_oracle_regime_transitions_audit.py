import numpy as np
import pandas as pd

from scripts.research.us_oracle_regime_transitions import lot_daily_attribution
from scripts.research.us_oracle_regime_transitions_audit import cash_value_components


def test_cash_value_reconstruction_matches_price_differences_for_random_lifecycles():
    days = pd.bdate_range('2025-01-06', periods=12)
    rng = np.random.default_rng(51)
    for side in ['buy', 'sell']:
        for closed in [False, True]:
            for same_day in [False, True]:
                values = 100*np.exp(rng.normal(0., .03, len(days)))
                prices = {d: dict(open=p*.99, close=p) for d, p in zip(days, values)}
                r = dict(symbol='A', pair_id=1, qty=3., entry_price=100.,
                    entry_timestamp=days[2].tz_localize('America/New_York')+pd.Timedelta(hours=10),
                    borrow_accrued_usd=.2 if side == 'sell' else 0.)
                if closed:
                    end = 2 if same_day else 9
                    r.update(exit_timestamp=days[end].tz_localize('America/New_York')+pd.Timedelta(hours=12),
                             exit_price=103., borrow_cost=.1 if side == 'sell' and not same_day else 0.)
                primary = pd.DataFrame(lot_daily_attribution(r, days, prices, side)).set_index('date')
                scalar = cash_value_components([r], days, {1: prices}, side)
                new = primary[primary.cohort.eq('NEW_ENTRY')].net_pnl_usd.reindex(days, fill_value=0.)
                held = primary[primary.cohort.eq('HELD_OVERNIGHT')].net_pnl_usd.reindex(days, fill_value=0.)
                overnight = primary.overnight_price_pnl_usd.reindex(days, fill_value=0.)
                np.testing.assert_allclose(new, scalar['new'], atol=1e-10)
                np.testing.assert_allclose(held, scalar['held'], atol=1e-10)
                np.testing.assert_allclose(overnight, scalar['overnight'], atol=1e-10)
