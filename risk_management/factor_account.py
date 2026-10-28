"""Project entry exposure from observed holdings, pending entries and sizing.

No credit for unfilled exits; no inferred price for an unbounded pending entry.
Targets are reserved as additional entry amounts, never as an assumed sale of
an existing holding. This upper bound is conservative for overlapping targets.
"""
import math


def projected_factor_weights(entries, equity, snapshot=None):
    equity = float(equity)
    if not math.isfinite(equity) or equity <= 0:
        raise ValueError('Positive observed equity required for factor weights')
    weights = {}
    holdings = {}

    def add(symbol, side, notional):
        if notional < 0 or not math.isfinite(notional):
            raise ValueError('Invalid factor notional: '+symbol)
        sign = -1 if side in ('short','sell') else 1
        weight = sign*notional/equity
        if weights.get(symbol,0.)*weight < 0:
            raise ValueError('Opposite overlapping exposure requires explicit close/open: '+symbol)
        weights[symbol] = weights.get(symbol,0.)+weight

    if snapshot is not None:
        if abs(float(snapshot.account.equity)-equity) > .005:
            raise ValueError('Factor snapshot equity differs from sizing equity')
        for holding in snapshot.positions:
            mark = holding.current_price
            if mark is None or not math.isfinite(mark) or mark <= 0:
                raise ValueError('Qualified current position mark required: '+holding.symbol)
            if holding.symbol in holdings:
                raise ValueError('Duplicate held symbol: '+holding.symbol)
            holdings[holding.symbol] = holding
            add(holding.symbol,holding.side,abs(holding.quantity)*mark)
        seen = set()
        for order in snapshot.open_orders:
            if order.order_id in seen:
                raise ValueError('Duplicate pending order: '+order.order_id)
            seen.add(order.order_id)
            remaining = float(order.quantity)-float(order.filled_quantity)
            if not math.isfinite(remaining) or remaining < 0:
                raise ValueError('Invalid remaining pending quantity: '+order.symbol)
            if remaining == 0:
                continue
            holding = holdings.get(order.symbol)
            if holding and ((holding.side=='long' and order.side=='sell')
                    or (holding.side=='short' and order.side=='buy')):
                if remaining > abs(holding.quantity)+1e-9:
                    raise ValueError('Unqualified pending side flip: '+order.symbol)
                continue  # An unfilled exit does not reduce observed exposure.
            price = order.limit_price
            if price is None or not math.isfinite(price) or price <= 0:
                raise ValueError('Bounded pending entry price required: '+order.symbol)
            add(order.symbol,order.side,remaining*price)
    for entry in entries:
        if entry.decision in ('ACCEPTED','REDUCED') and entry.approved_shares > 0:
            add(entry.symbol,entry.side,float(entry.target_notional))
    return weights
