"""Research-only fixed initial stop; does not change live protection settings."""
from dataclasses import replace
import math

from backtesting.oracle_portfolio_ledger import OraclePortfolioLedger
from execution_engine.models import IntentRole


def fixed_stop_protections(protection, stop_pct):
    """Use actual Phase 3 fill, not signal close; leave TP/trailing/sizing intact."""
    if not math.isfinite(stop_pct) or not 0 < stop_pct < 1:
        raise ValueError('Initial stop fraction must be between zero and one')
    signals = protection.signals_df.copy()
    frame = protection.protection_frame.copy()
    orders = protection.order_lifecycle_frame.copy()
    if signals.empty:
        return replace(protection, signals_df=signals, protection_frame=frame,
                       order_lifecycle_frame=orders)
    prices = signals.set_index('symbol').fill_price.astype(float) * (1-stop_pct)
    if not prices.index.is_unique or not prices.map(lambda x: math.isfinite(x) and x > 0).all():
        raise ValueError('Invalid fixed-stop fill prices')
    for target in (signals, frame):
        if not target.empty:
            target['replay_initial_stop_price'] = target.symbol.map(prices)
    if not orders.empty:
        mask = orders.intent_role.eq(IntentRole.INITIAL_STOP)
        orders.loc[mask, 'stop_price'] = orders.loc[mask, 'symbol'].map(prices)
    diagnostics = dict(protection.diagnostics, research_initial_stop_pct=stop_pct,
                       research_stop_anchor='actual_phase3_fill', sizing_unchanged=True,
                       trailing_unchanged=True, take_profit_unchanged=True)
    return replace(protection, signals_df=signals, protection_frame=frame,
                   order_lifecycle_frame=orders, diagnostics=diagnostics)


class FixedInitialStopLedger(OraclePortfolioLedger):
    def __init__(self, *args, initial_stop_pct, **kwargs):
        if not math.isfinite(initial_stop_pct) or not 0 < initial_stop_pct < 1:
            raise ValueError('Initial stop fraction must be between zero and one')
        self.research_initial_stop_pct = initial_stop_pct
        super().__init__(*args, **kwargs)

    def _build_entry_protections(self, phase3, *, execution_config):
        native = super()._build_entry_protections(phase3, execution_config=execution_config)
        return fixed_stop_protections(native, self.research_initial_stop_pct)
