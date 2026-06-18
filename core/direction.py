"""
core/direction.py
=================
Helpers directionnels **sans dépendance externe** pour le pipeline long+short.

Toutes les fonctions sont pures et déterministes — elles n'effectuent
aucun I/O, n'importent aucun module externe, et peuvent être utilisées
aussi bien en backtest qu'en live.

Contrat canonique (cf. ``prompt/short/plan.md`` §3.1) :
- ``side`` : ``"buy"`` | ``"sell"``
- ``qty`` / ``shares`` : toujours positif (quantité absolue)
- ``net_qty`` : signé uniquement pour les positions broker / reconciliation

Usage ::

    from core.direction import is_short_side, closing_side, compute_realized_pnl

    if is_short_side(entry.side):
        tp_price = compute_take_profit_price("sell", entry_price, 0.12)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BUY: str = "buy"
SELL: str = "sell"

_VALID_SIDES: frozenset[str] = frozenset({BUY, SELL})


# ---------------------------------------------------------------------------
# Prédicats
# ---------------------------------------------------------------------------

def is_short_side(side: str) -> bool:
    """Retourne True si le side est une ouverture short (sell).

    >>> is_short_side("sell")
    True
    >>> is_short_side("buy")
    False
    """
    return str(side).strip().lower() == SELL


def is_long_side(side: str) -> bool:
    """Retourne True si le side est une ouverture long (buy).

    >>> is_long_side("buy")
    True
    """
    return str(side).strip().lower() == BUY


def is_valid_side(side: str) -> bool:
    """Retourne True si le side est une valeur valide ('buy' ou 'sell')."""
    return str(side).strip().lower() in _VALID_SIDES


def normalize_side(side: str | None, default: str = BUY) -> str:
    """Normalise un side vers 'buy' ou 'sell', avec défaut rétrocompatible.

    >>> normalize_side(None)
    'buy'
    >>> normalize_side('SELL')
    'sell'
    """
    if side is None:
        return default
    normalized = str(side).strip().lower()
    return normalized if normalized in _VALID_SIDES else default


# ---------------------------------------------------------------------------
# Direction
# ---------------------------------------------------------------------------

def direction_sign(side: str) -> int:
    """Retourne +1 pour buy, -1 pour sell.

    >>> direction_sign("buy")
    1
    >>> direction_sign("sell")
    -1
    """
    return -1 if is_short_side(side) else 1


def closing_side(entry_side: str) -> str:
    """Retourne le side de clôture opposé à l'entrée.

    >>> closing_side("buy")
    'sell'
    >>> closing_side("sell")
    'buy'
    """
    return BUY if is_short_side(entry_side) else SELL


# ---------------------------------------------------------------------------
# Prix de protection (TP / SL / trailing)
# ---------------------------------------------------------------------------

def compute_take_profit_price(
    entry_side: str,
    entry_price: float,
    tp_pct: float = 0.12,
) -> float:
    """Calcule le prix de take-profit selon la direction.

    Long  : TP = entry_price * (1 + tp_pct)   → au-dessus
    Short : TP = entry_price * (1 - tp_pct)   → en-dessous

    >>> compute_take_profit_price("buy", 100.0, 0.12)
    112.0
    >>> compute_take_profit_price("sell", 100.0, 0.12)
    88.0
    """
    if entry_price <= 0:
        return 0.0
    sign = direction_sign(entry_side)
    return round(entry_price * (1.0 + sign * tp_pct), 4)


def compute_initial_stop_price(
    entry_side: str,
    entry_price: float,
    risk_per_share: float | None = None,
    stop_pct: float | None = None,
) -> float | None:
    """Calcule le stop-loss initial selon la direction.

    Long  : stop = entry_price - risk_per_share  (sous le prix)
    Short : stop = entry_price + risk_per_share  (au-dessus du prix)

    Si ``risk_per_share`` est None, utilise ``stop_pct`` comme fallback.
    Retourne None si aucune valeur exploitable.
    """
    if entry_price <= 0:
        return None
    if risk_per_share is not None and risk_per_share > 0:
        sign = direction_sign(entry_side)
        return round(entry_price - sign * risk_per_share, 4)
    if stop_pct is not None and 0 < stop_pct < 1:
        sign = direction_sign(entry_side)
        return round(entry_price * (1.0 - sign * stop_pct), 4)
    return None


def compute_trailing_stop_price(
    entry_side: str,
    reference_price: float,
    trailing_pct: float = 0.10,
) -> float:
    """Calcule le prix du trailing stop selon la direction.

    Long  : trailing = reference_price * (1 - trailing_pct)   → sous le pic
    Short : trailing = reference_price * (1 + trailing_pct)   → au-dessus du creux

    >>> compute_trailing_stop_price("buy", 110.0, 0.10)
    99.0
    >>> compute_trailing_stop_price("sell", 90.0, 0.10)
    99.0
    """
    if reference_price <= 0:
        return 0.0
    sign = direction_sign(entry_side)
    return round(reference_price * (1.0 - sign * trailing_pct), 4)


def compute_trailing_activation_price(
    entry_side: str,
    entry_price: float,
    r_multiple: float = 2.0,
    risk_per_share: float | None = None,
    activation_profit_pct: float | None = None,
) -> float | None:
    """Calcule le prix d'activation du trailing stop.

    Long  : activation = entry_price + r_multiple * risk_per_share
    Short : activation = entry_price - r_multiple * risk_per_share
    """
    if entry_price <= 0:
        return None
    if risk_per_share is not None and risk_per_share > 0:
        sign = direction_sign(entry_side)
        return round(entry_price + sign * r_multiple * risk_per_share, 4)
    if activation_profit_pct is not None and 0 < activation_profit_pct < 1:
        sign = direction_sign(entry_side)
        return round(entry_price * (1.0 + sign * activation_profit_pct), 4)
    return None


def compute_pullback_limit_price(
    entry_side: str,
    signal_price: float,
    offset_pct: float = 0.01,
) -> float:
    """Calcule le prix limite pour un ordre pullback.

    Long  : limit = signal_price * (1 - offset_pct)  → -1% sous le signal
    Short : limit = signal_price * (1 + offset_pct)  → +1% au-dessus du signal

    >>> compute_pullback_limit_price("buy", 100.0, 0.01)
    99.0
    >>> compute_pullback_limit_price("sell", 100.0, 0.01)
    101.0
    """
    if signal_price <= 0:
        return 0.0
    sign = direction_sign(entry_side)
    return round(signal_price * (1.0 - sign * offset_pct), 4)


# ---------------------------------------------------------------------------
# PnL et exposition
# ---------------------------------------------------------------------------

def compute_realized_pnl(
    entry_side: str,
    qty: float,
    entry_price: float,
    exit_price: float,
    fees: float = 0.0,
) -> float:
    """Calcule le PnL réalisé directionnel.

    Long  : PnL = qty * (exit_price - entry_price) - fees
    Short : PnL = qty * (entry_price - exit_price) - fees

    ``qty`` doit être positif (quantité absolue).

    >>> compute_realized_pnl("buy", 10, 100, 110)
    100.0
    >>> compute_realized_pnl("sell", 10, 100, 90)
    100.0
    """
    if qty <= 0:
        return 0.0
    sign = direction_sign(entry_side)
    return round(sign * qty * (exit_price - entry_price) - fees, 4)


def compute_unrealized_pnl(
    entry_side: str,
    qty: float,
    current_price: float,
    entry_price: float,
) -> float:
    """Calcule le PnL non réalisé directionnel.

    Long  : uPnL = qty * (current_price - entry_price)
    Short : uPnL = qty * (entry_price - current_price)

    >>> compute_unrealized_pnl("buy", 10, 105, 100)
    50.0
    >>> compute_unrealized_pnl("sell", 10, 95, 100)
    50.0
    """
    return compute_realized_pnl(entry_side, qty, entry_price, current_price, fees=0.0)


def compute_return_pct(
    entry_side: str,
    entry_price: float,
    exit_price: float,
) -> float:
    """Calcule le retour en % directionnel.

    Long  : return = (exit_price / entry_price) - 1
    Short : return = (entry_price / exit_price) - 1

    >>> compute_return_pct("buy", 100, 110)
    10.0
    >>> compute_return_pct("sell", 100, 90)
    11.11...
    """
    if entry_price <= 0 or exit_price <= 0:
        return 0.0
    if is_short_side(entry_side):
        return round((entry_price / exit_price - 1.0) * 100.0, 4)
    return round((exit_price / entry_price - 1.0) * 100.0, 4)


# ---------------------------------------------------------------------------
# Exposition
# ---------------------------------------------------------------------------

def compute_gross_notional(qty: float, price: float) -> float:
    """Exposition brute absolue (= abs(qty) * price), toujours positive.

    >>> compute_gross_notional(10, 100)
    1000.0
    >>> compute_gross_notional(-10, 100)  # short via net_qty signé
    1000.0
    """
    return abs(qty) * price


def compute_net_notional(side: str, qty: float, price: float) -> float:
    """Exposition nette signée.

    Long  : +qty * price  (positive)
    Short : -qty * price  (négative)

    >>> compute_net_notional("buy", 10, 100)
    1000.0
    >>> compute_net_notional("sell", 10, 100)
    -1000.0
    """
    if qty <= 0:
        return 0.0
    return direction_sign(side) * qty * price


def compute_gross_exposure_pct(
    long_notional: float,
    short_notional: float,
    equity: float,
) -> float:
    """Exposition brute en % equity = (abs(long) + abs(short)) / equity."""
    if equity <= 0:
        return 0.0
    return (abs(long_notional) + abs(short_notional)) / equity


def compute_net_exposure_pct(
    long_notional: float,
    short_notional: float,
    equity: float,
) -> float:
    """Exposition nette en % equity = (long - short) / equity."""
    if equity <= 0:
        return 0.0
    return (long_notional - short_notional) / equity


# ---------------------------------------------------------------------------
# Helpers de compatibilité / migration
# ---------------------------------------------------------------------------

def normalize_target_side(target: object) -> str:
    """Extrait et normalise le side d'un objet target (PortfolioEntry, ExecutionTarget, etc.).

    Promotion de ``execution_engine/order_intents._normalized_target_side()``
    pour centraliser la logique dans ``core/direction.py``.
    """
    raw_side = getattr(target, "side", None)
    if raw_side is None:
        return BUY
    normalized = str(raw_side).strip().lower()
    return normalized if normalized in _VALID_SIDES else BUY


__all__ = [
    "BUY",
    "SELL",
    "closing_side",
    "compute_gross_exposure_pct",
    "compute_gross_notional",
    "compute_initial_stop_price",
    "compute_net_exposure_pct",
    "compute_net_notional",
    "compute_pullback_limit_price",
    "compute_realized_pnl",
    "compute_return_pct",
    "compute_take_profit_price",
    "compute_trailing_activation_price",
    "compute_trailing_stop_price",
    "compute_unrealized_pnl",
    "direction_sign",
    "is_long_side",
    "is_short_side",
    "is_valid_side",
    "normalize_side",
    "normalize_target_side",
]
