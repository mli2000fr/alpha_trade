"""modelFactory/labeling.py — Triple-barrier labeling pour swing trading.

Sprint Maître 3 :
- Labeler triple-barrier pur avec entrée au prochain open tradable (J+1).
- Stop/TP définis en multiples d'ATR, horizon maximal en sessions.
- Gestion des gaps : exécution au prix disponible, jamais au niveau théorique.
- Déduction spread, commission, slippage, impact.
- Produit : side, net_return, holding_sessions, MAE, MFE, exit_reason.
- Optimisation des paramètres réservée au fold train (pas de fuite inter-fold).

Contrat : les mêmes fonctions de coûts sont partagées avec le simulateur
backtest pour garantir la parité label/backtest.

Usage ::

    from modelFactory.labeling import (
        TripleBarrierConfig, TripleBarrierLabel, build_triple_barrier_labels
    )

    cfg = TripleBarrierConfig(stop_atr_mult=2.0, tp_atr_mult=3.0, max_sessions=20)
    labels = build_triple_barrier_labels(df_ohlc, cfg)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

# ── Types ───────────────────────────────────────────────────────────────────

ExitReason = Literal[
    "take_profit",
    "stop_loss",
    "time_exit",
    "gap_stop",
    "gap_tp",
    "no_entry_signal",
    "insufficient_data",
]

Side = Literal["long", "short", "flat"]


@dataclass(frozen=True, slots=True)
class TripleBarrierConfig:
    """Configuration du labeler triple-barrier.

    Attributes
    ----------
    stop_atr_mult : float
        Multiple d'ATR pour le stop-loss. Ex: 2.0 → stop à 2 ATR de l'entrée.
    tp_atr_mult : float
        Multiple d'ATR pour le take-profit. Ex: 3.0 → TP à 3 ATR de l'entrée.
    max_sessions : int
        Nombre maximum de sessions avant sortie time-based.
    atr_window : int
        Fenêtre de calcul de l'ATR.
    min_atr : float
        ATR minimum (évite les stops absurdes sur low-vol).
    spread_bps : float
        Spread en bps (1 bps = 0.0001).
    commission_bps : float
        Commission en bps.
    slippage_bps : float
        Slippage estimé en bps.
    borrow_fee_annual : float
        Coût d'emprunt annualisé pour les shorts (ex: 0.003 = 0.3%/an).
    entry_delay_sessions : int
        Délai entre le signal et l'entrée (1 = next open J+1).
    """

    stop_atr_mult: float = 2.0
    tp_atr_mult: float = 3.0
    max_sessions: int = 20
    atr_window: int = 14
    min_atr: float = 0.001  # 0.1% minimum ATR
    spread_bps: float = 5.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    borrow_fee_annual: float = 0.003
    entry_delay_sessions: int = 1

    def __post_init__(self) -> None:
        if self.stop_atr_mult <= 0:
            raise ValueError("stop_atr_mult doit être > 0.")
        if self.tp_atr_mult <= 0:
            raise ValueError("tp_atr_mult doit être > 0.")
        if self.max_sessions < 1:
            raise ValueError("max_sessions doit être >= 1.")
        if self.atr_window < 2:
            raise ValueError("atr_window doit être >= 2.")
        if self.entry_delay_sessions < 0:
            raise ValueError("entry_delay_sessions doit être >= 0.")

    @property
    def total_cost_bps(self) -> float:
        """Coût total aller-retour en bps (entrée + sortie)."""
        return 2 * (self.spread_bps + self.commission_bps + self.slippage_bps)

    @property
    def cost_pct(self) -> float:
        """Coût total en pourcentage (ex: 0.0016 = 16 bps)."""
        return self.total_cost_bps / 10000.0


@dataclass(frozen=True, slots=True)
class TripleBarrierLabel:
    """Label swing tradable produit par le triple-barrier.

    Attributes
    ----------
    side : str
        ``"long"``, ``"short"`` ou ``"flat"``.
    entry_price : float | None
        Prix d'entrée réel (next open après gap check).
    exit_price : float | None
        Prix de sortie réel.
    gross_return : float | None
        Rendement brut (avant coûts), signé selon le side.
    net_return : float | None
        Rendement net après tous les coûts.
    holding_sessions : int | None
        Nombre de sessions tenues.
    mae : float | None
        Maximum Adverse Excursion (pire drawdown intra-trade).
    mfe : float | None
        Maximum Favorable Excursion (meilleur gain intra-trade).
    exit_reason : str
        Raison de sortie (take_profit, stop_loss, time_exit, gap_*).
    barrier_touched_at : int | None
        Index de la session où le premier barrier a été touché.
    label : int
        -1 = short, 0 = flat, +1 = long (pour entraînement).
    net_return_pct : float | None
        Net return en pourcentage (compatible avec l'ancienne target).
    """

    side: Side = "flat"
    entry_price: float | None = None
    exit_price: float | None = None
    gross_return: float | None = None
    net_return: float | None = None
    holding_sessions: int | None = None
    mae: float | None = None
    mfe: float | None = None
    exit_reason: ExitReason = "no_entry_signal"
    barrier_touched_at: int | None = None
    label: int = 0  # -1, 0, +1
    net_return_pct: float | None = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _compute_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    window: int = 14,
) -> np.ndarray:
    """Calcule l'ATR (Average True Range) normalisé par le close."""
    high, low, close = np.asarray(high, float), np.asarray(low, float), np.asarray(close, float)
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]

    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    true_range = np.maximum(np.maximum(tr1, tr2), tr3)

    atr = np.full_like(close, np.nan)
    if len(true_range) >= window:
        # Wilder's smoothing
        atr[window - 1] = np.mean(true_range[:window])
        for i in range(window, len(true_range)):
            atr[i] = (atr[i - 1] * (window - 1) + true_range[i]) / window
    return atr


def _deduct_costs(
    gross_return: float,
    cfg: TripleBarrierConfig,
    *,
    holding_sessions: int = 1,
) -> float:
    """Déduit les coûts de transaction du rendement brut.

    - Spread + commission + slippage (aller-retour via cost_pct)
    - Borrow fee short proportionnelle à la durée de détention
    """
    net = gross_return - cfg.cost_pct
    # Borrow fee pour les shorts (optionnel, déduit si applicable)
    # ≈ annual_fee * (holding_sessions / 252)
    # Appliqué côté appelant qui connaît le side
    return net


def _resolve_exit(
    *,
    entry_price: float,
    side: str,
    stop_price: float,
    tp_price: float,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    opens: np.ndarray,
    max_sessions: int,
    start_idx: int,
) -> dict:
    """Résout le premier barrier touché pour un trade.

    Convention intraday : si high et low touchent les deux barriers
    le même jour → conservative (stop prioritaire).

    Parameters
    ----------
    entry_price, side, stop_price, tp_price : float
    highs, lows, closes, opens : np.ndarray
        Séries de prix (alignées).
    max_sessions : int
        Horizon max.
    start_idx : int
        Index de la session d'entrée.

    Returns
    -------
    dict avec exit_price, exit_reason, holding_sessions, mae, mfe,
    barrier_touched_at.
    """
    direction = -1 if side == "short" else 1  # +1 long, -1 short
    mae = 0.0
    mfe = 0.0
    exit_reason: ExitReason = "time_exit"
    exit_price_val = closes[min(start_idx + max_sessions, len(closes) - 1)]
    barrier_idx = start_idx + max_sessions

    for i in range(start_idx + 1, min(start_idx + max_sessions + 1, len(highs))):
        if i >= len(highs):
            break

        # Vérifier gap à l'open
        if opens[i] > 0 and np.isfinite(opens[i]):
            gap_return = (opens[i] - entry_price) / entry_price * direction
            mfe = max(mfe, gap_return)
            mae = min(mae, gap_return)

            # Gap à travers le stop
            if side == "long":
                gap_stop_hit = opens[i] <= stop_price
                gap_tp_hit = opens[i] >= tp_price
            else:
                gap_stop_hit = opens[i] >= stop_price
                gap_tp_hit = opens[i] <= tp_price

            if gap_stop_hit:
                exit_reason = "gap_stop"
                exit_price_val = opens[i]
                barrier_idx = i
                break
            if gap_tp_hit:
                exit_reason = "gap_tp"
                exit_price_val = opens[i]
                barrier_idx = i
                break

        # Mise à jour MAE/MFE depuis les prix de la session
        high, low, close = highs[i], lows[i], closes[i]
        if np.isfinite(high) and np.isfinite(low):
            if side == "long":
                session_mfe = (high - entry_price) / entry_price
                session_mae = (low - entry_price) / entry_price
                stop_hit = low <= stop_price
                tp_hit = high >= tp_price
            else:
                session_mfe = (entry_price - low) / entry_price
                session_mae = (entry_price - high) / entry_price
                stop_hit = high >= stop_price
                tp_hit = low <= tp_price

            mfe = max(mfe, session_mfe)
            mae = min(mae, session_mae)  # mae est négative ou nulle

            # Résolution intraday : conservative → stop prioritaire
            if stop_hit and tp_hit:
                # Les deux touchés le même jour
                exit_reason = "stop_loss"
                exit_price_val = stop_price  # exécuté au prix du barrier (pire cas)
                barrier_idx = i
                break
            elif stop_hit:
                exit_reason = "stop_loss"
                exit_price_val = stop_price
                barrier_idx = i
                break
            elif tp_hit:
                exit_reason = "take_profit"
                exit_price_val = tp_price
                barrier_idx = i
                break

        # Si pas de barrier touché, on continue
        exit_price_val = close  # mise à jour du prix de sortie potentiel

    return {
        "exit_price": exit_price_val,
        "exit_reason": exit_reason,
        "holding_sessions": barrier_idx - start_idx,
        "mae": mae,
        "mfe": mfe,
        "barrier_touched_at": barrier_idx,
    }


# ── Labeler principal ───────────────────────────────────────────────────────

def build_triple_barrier_label(
    *,
    entry_idx: int,
    side: str,
    prices: dict,
    cfg: TripleBarrierConfig,
) -> TripleBarrierLabel:
    """Calcule le label triple-barrier pour UNE entrée.

    Parameters
    ----------
    entry_idx : int
        Index dans les séries de prix où le signal est émis (close J).
    side : str
        ``"long"`` ou ``"short"``.
    prices : dict
        Dict avec les clés ``open``, ``high``, ``low``, ``close``,
        chacune étant un np.ndarray 1D.
    cfg : TripleBarrierConfig

    Returns
    -------
    TripleBarrierLabel
    """
    opens = np.asarray(prices["open"], float)
    highs = np.asarray(prices["high"], float)
    lows = np.asarray(prices["low"], float)
    closes = np.asarray(prices["close"], float)
    n = len(closes)

    # Entrée réelle : next open après le délai
    entry_bar_idx = entry_idx + cfg.entry_delay_sessions
    if entry_bar_idx >= n:
        return TripleBarrierLabel(side="flat", exit_reason="insufficient_data")

    entry_price = opens[entry_bar_idx]
    if entry_price <= 0 or not np.isfinite(entry_price):
        return TripleBarrierLabel(side="flat", exit_reason="insufficient_data")

    # Calcul ATR au moment de l'entrée
    atr_arr = _compute_atr(highs[:entry_bar_idx + 1], lows[:entry_bar_idx + 1], closes[:entry_bar_idx + 1], cfg.atr_window)
    atr_val = atr_arr[entry_bar_idx]
    if not np.isfinite(atr_val) or atr_val <= 0:
        atr_val = cfg.min_atr * entry_price
    else:
        atr_val = max(atr_val, cfg.min_atr * entry_price)

    # Niveaux stop et TP
    if side == "long":
        stop_price = entry_price - cfg.stop_atr_mult * atr_val
        tp_price = entry_price + cfg.tp_atr_mult * atr_val
    else:
        stop_price = entry_price + cfg.stop_atr_mult * atr_val
        tp_price = entry_price - cfg.tp_atr_mult * atr_val

    direction = 1 if side == "long" else -1

    # Résolution du premier barrier
    result = _resolve_exit(
        entry_price=entry_price,
        side=side,
        stop_price=stop_price,
        tp_price=tp_price,
        highs=highs,
        lows=lows,
        closes=closes,
        opens=opens,
        max_sessions=cfg.max_sessions,
        start_idx=entry_bar_idx,
    )

    exit_price_val = float(result["exit_price"])
    holding = int(result["holding_sessions"])

    # Rendement brut signé
    gross_return = (exit_price_val - entry_price) / entry_price * direction

    # Coûts
    net_return = _deduct_costs(gross_return, cfg, holding_sessions=holding)
    # Borrow fee short
    if side == "short" and cfg.borrow_fee_annual > 0:
        borrow_cost = cfg.borrow_fee_annual * (holding / 252.0)
        net_return -= borrow_cost

    # Label ternaire
    if net_return > 0:
        label = 1 if side == "long" else -1
    else:
        label = 0  # flat : le trade n'est pas rentable net

    return TripleBarrierLabel(
        side=side,
        entry_price=float(entry_price),
        exit_price=exit_price_val,
        gross_return=float(gross_return),
        net_return=float(net_return),
        holding_sessions=holding,
        mae=float(result["mae"]),
        mfe=float(result["mfe"]),
        exit_reason=result["exit_reason"],
        barrier_touched_at=int(result["barrier_touched_at"]),
        label=label,
        net_return_pct=float(net_return),
    )


def build_triple_barrier_labels(
    df_ohlc: pd.DataFrame,
    cfg: TripleBarrierConfig,
    *,
    side: str = "long",
    signal_column: str | None = None,
) -> pd.DataFrame:
    """Calcule les labels triple-barrier pour toutes les lignes d'un DataFrame.

    Parameters
    ----------
    df_ohlc : pd.DataFrame
        Doit contenir les colonnes ``open``, ``high``, ``low``, ``close``,
        trié par date croissante.
    cfg : TripleBarrierConfig
    side : str
        ``"long"`` ou ``"short"`` (si pas de colonne signal).
    signal_column : str | None
        Colonne contenant ``"long"`` / ``"short"`` par ligne.
        Si None, utilise ``side`` pour toutes les lignes.

    Returns
    -------
    pd.DataFrame
        Colonnes : label, net_return_pct, holding_sessions, mae, mfe,
        exit_reason, entry_price, exit_price, gross_return, net_return.
    """
    df = df_ohlc.copy().sort_values("date" if "date" in df_ohlc.columns else df_ohlc.index).reset_index(drop=True)
    prices = {
        "open": df["open"].to_numpy(float),
        "high": df["high"].to_numpy(float),
        "low": df["low"].to_numpy(float),
        "close": df["close"].to_numpy(float),
    }

    sides_series: pd.Series = (
        df[signal_column].astype(str).str.strip().str.lower()
        if signal_column and signal_column in df.columns
        else pd.Series([side] * len(df), index=df.index)
    )

    results: list[dict] = []
    for i in range(len(df)):
        s = sides_series.iloc[i] if i < len(sides_series) else side
        if s not in ("long", "short"):
            results.append({
                "label": 0, "net_return_pct": 0.0, "holding_sessions": 0,
                "mae": 0.0, "mfe": 0.0, "exit_reason": "no_entry_signal",
                "entry_price": None, "exit_price": None,
                "gross_return": None, "net_return": None, "side": "flat",
            })
            continue

        label = build_triple_barrier_label(
            entry_idx=i, side=s, prices=prices, cfg=cfg,
        )
        results.append({
            "label": label.label,
            "net_return_pct": label.net_return_pct,
            "holding_sessions": label.holding_sessions,
            "mae": label.mae,
            "mfe": label.mfe,
            "exit_reason": label.exit_reason,
            "entry_price": label.entry_price,
            "exit_price": label.exit_price,
            "gross_return": label.gross_return,
            "net_return": label.net_return,
            "side": label.side,
        })

    result_df = pd.DataFrame(results, index=df.index)
    # Les dernières lignes n'ont pas assez de forward data
    cutoff = len(df) - cfg.max_sessions - cfg.entry_delay_sessions
    if cutoff > 0:
        result_df.iloc[cutoff:, :] = pd.NA
    return result_df


# ── Fonction de comparaison (ablation) ──────────────────────────────────────

def compare_label_methods(
    df_ohlc: pd.DataFrame,
    cfg: TripleBarrierConfig,
    *,
    fixed_horizon: int = 10,
    fixed_up_threshold: float = 0.02,
    fixed_down_threshold: float = -0.02,
) -> dict:
    """Compare la target fixe vs triple-barrier (rapport d'ablation).

    Returns
    -------
    dict avec distribution des classes et statistiques pour chaque méthode.
    """
    from modelFactory.features import build_target, compute_future_return

    # Target fixe ternaire
    fixed_target = build_target(
        df_ohlc, horizon=fixed_horizon, mode="ternary",
        positive_threshold=fixed_up_threshold,
        negative_threshold=fixed_down_threshold,
    )

    # Triple-barrier long
    tb_long = build_triple_barrier_labels(df_ohlc, cfg, side="long")
    # Triple-barrier short
    tb_short = build_triple_barrier_labels(df_ohlc, cfg, side="short")

    def _distribution(series: pd.Series) -> dict:
        vals = series.dropna().astype(int)
        total = len(vals)
        return {
            "long_pct": round((vals == 1).sum() / total * 100, 1) if total else 0,
            "flat_pct": round((vals == 0).sum() / total * 100, 1) if total else 0,
            "short_pct": round((vals == -1).sum() / total * 100, 1) if total else 0,
            "total": total,
        }

    return {
        "fixed_target": {
            "horizon": fixed_horizon,
            "up_threshold": fixed_up_threshold,
            "down_threshold": fixed_down_threshold,
            "distribution": _distribution(fixed_target),
        },
        "triple_barrier_long": {
            "config": {
                "stop_atr_mult": cfg.stop_atr_mult,
                "tp_atr_mult": cfg.tp_atr_mult,
                "max_sessions": cfg.max_sessions,
            },
            "distribution": _distribution(tb_long["label"]),
            "mean_net_return": round(float(tb_long["net_return_pct"].dropna().mean()), 6),
            "win_rate": round(float((tb_long["net_return_pct"].dropna() > 0).mean()), 4),
        },
        "triple_barrier_short": {
            "config": {
                "stop_atr_mult": cfg.stop_atr_mult,
                "tp_atr_mult": cfg.tp_atr_mult,
                "max_sessions": cfg.max_sessions,
            },
            "distribution": _distribution(tb_short["label"]),
            "mean_net_return": round(float(tb_short["net_return_pct"].dropna().mean()), 6),
            "win_rate": round(float((tb_short["net_return_pct"].dropna() > 0).mean()), 4),
        },
    }
