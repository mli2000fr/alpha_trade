"""backtest_global_rank_strategies.py — Backtest PnL 3 variantes H20+H5 (2026-08-02).

Lit les ``global_rank`` depuis la DB ou un cache parquet, simule 3 stratégies
long-only avec frais de transaction, et compare les Sharpes.

Variantes :
- V1 : H20 > 0.70 (baseline, rebalancement 20j)
- V2 : H20 > 0.70 + H5 rising  (momentum trigger)
- V3 : H20 > 0.70 + H5 < 0.35  (contrarian / buy the dip)

Usage :
    python backtest_global_rank_strategies.py --batch-id model-factory-20260802013530-4f6428
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ── Paramètres ──────────────────────────────────────────────────────────────

REBALANCE_DAYS = 20            # rebalancement toutes les 4 semaines
TOP_PCT = 0.70                 # seuil H20
H5_DIP_THRESHOLD = 0.35        # seuil contrarian H5
TRANSACTION_COST_BPS = 25.0    # 0.25% aller-retour (25 bps)
CAPITAL_PER_POSITION = 1.0     # équipondéré
MAX_POSITIONS = 30             # max positions simultanées


def load_global_rank_df(batch_id: str) -> pd.DataFrame:
    """Charge les rangs globaux depuis le cache parquet généré par train_global_ranking_wf."""
    _cache = Path("artifacts") / "models" / batch_id / "global_rank_cache.parquet"
    if _cache.exists():
        LOGGER.info("Loading from cache: %s", _cache)
        _df = pd.read_parquet(_cache)
        _df["date"] = pd.to_datetime(_df["date"])
        LOGGER.info("Loaded %d symbols × %d dates", _df["symbol"].nunique(), _df["date"].nunique())
        return _df

    raise FileNotFoundError(
        f"No cache found at {_cache}. "
        f"Re-run training with the latest global_ranking.py to generate it."
    )


def compute_daily_returns(
    rank_df: pd.DataFrame,
    variant: str,
) -> pd.Series:
    """Simule les rendements journaliers équipondérés pour une variante.

    Args:
        rank_df: DataFrame avec [date, symbol, global_rank_5, global_rank_20].
        variant: "V1" (H20 seul), "V2" (H20 + H5 rising), "V3" (H20 + H5 dip).

    Returns:
        Series indexée par date, rendement journalier net de frais.
    """
    _df = rank_df.sort_values(["date", "symbol"]).copy()

    # ── H5(t-1) pour les variantes V2/V3 ──
    _df["global_rank_5_prev"] = _df.groupby("symbol")["global_rank_5"].shift(1)

    # ── Signaux ──
    _df["h20_top"] = _df["global_rank_20"] > TOP_PCT

    if variant == "V1":
        _df["signal"] = _df["h20_top"]
    elif variant == "V2":
        _df["signal"] = _df["h20_top"] & (
            _df["global_rank_5"] > _df["global_rank_5_prev"]
        )
    elif variant == "V3":
        _df["signal"] = _df["h20_top"] & (_df["global_rank_5"] < H5_DIP_THRESHOLD)

    # ── Dates de rebalancement ──
    _all_dates = sorted(_df["date"].unique())
    _rebal_dates = _all_dates[::REBALANCE_DAYS]

    # ── Suivi du portefeuille ──
    _positions: dict[str, float] = {}  # symbol → entry_rank
    _daily_returns: dict[pd.Timestamp, float] = {}
    _turnover_count = 0

    for _i, _d in enumerate(_all_dates):
        _day_df = _df[_df["date"] == _d].set_index("symbol")

        # Rebalancement
        if _d in _rebal_dates or not _positions:
            _candidates = _day_df[_day_df["signal"]].sort_values(
                "global_rank_20", ascending=False
            )
            # Vendre toutes les positions
            if _positions:
                _turnover_count += len(_positions)
            # Acheter les top N
            _new_positions: dict[str, float] = {}
            for _sym in _candidates.index[:MAX_POSITIONS]:
                _new_positions[_sym] = float(_candidates.loc[_sym, "global_rank_20"])
            _positions = _new_positions
            _turnover_count += len(_positions)

        # Calculer le rendement du jour (proxy : variation moyenne des rangs)
        _held = [s for s in _positions if s in _day_df.index]
        if _held:
            _ret = float(_day_df.loc[_held, "global_rank_20"].mean())
        else:
            _ret = 0.5  # neutre

        _daily_returns[_d] = _ret - 0.5  # centré sur 0

    # ── Déduire les frais ──
    _ret_series = pd.Series(_daily_returns).sort_index()
    # Approximation : frais répartis sur les jours de rebalancement
    _cost_per_rebal = TRANSACTION_COST_BPS / 10000.0  # bps → fraction
    _total_cost = _cost_per_rebal * _turnover_count / len(_all_dates)
    _ret_series = _ret_series - _total_cost / REBALANCE_DAYS  # lissage

    return _ret_series


def compute_sharpe(returns: pd.Series, rf_annual: float = 0.02) -> dict[str, float]:
    """Calcule les métriques de performance."""
    _ann_factor = np.sqrt(252)
    _excess = returns - rf_annual / 252
    _mean = float(_excess.mean())
    _std = float(_excess.std())
    _sharpe = float(_mean / _std * _ann_factor) if _std > 0 else 0.0

    _cum = (1 + returns).cumprod()
    _peak = _cum.cummax()
    _drawdown = (_cum - _peak) / _peak
    _max_dd = float(_drawdown.min())

    return {
        "sharpe": _sharpe,
        "ann_return": float(_mean * 252),
        "ann_vol": float(_std * _ann_factor),
        "max_drawdown": _max_dd,
        "n_days": len(returns),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Global Rank strategies")
    parser.add_argument("--batch-id", required=True, help="Batch ID")
    args = parser.parse_args()

    rank_df = load_global_rank_df(args.batch_id)
    LOGGER.info(
        "Loaded %d symbols × %d dates",
        rank_df["symbol"].nunique(),
        rank_df["date"].nunique(),
    )

    print("\n📊 Global Rank Strategy Backtest")
    print(f"   Batch: {args.batch_id}")
    print(f"   Rebalancement: {REBALANCE_DAYS}j | Top: {TOP_PCT*100:.0f}% | Frais: {TRANSACTION_COST_BPS}bps")
    print(f"   Max positions: {MAX_POSITIONS}")
    print()

    for _v in ("V1", "V2", "V3"):
        _label = {
            "V1": "H20 seul (baseline)",
            "V2": "H20 + H5 rising",
            "V3": "H20 + H5 < 0.35 (dip)",
        }[_v]
        _rets = compute_daily_returns(rank_df, _v)
        _metrics = compute_sharpe(_rets)
        print(f"   {_v} — {_label}")
        print(f"      Sharpe: {_metrics['sharpe']:.3f}")
        print(f"      Return ann: {_metrics['ann_return']*100:.2f}%")
        print(f"      Vol ann: {_metrics['ann_vol']*100:.2f}%")
        print(f"      Max DD: {_metrics['max_drawdown']*100:.2f}%")
        print()

    # ── Comparaison rapide ──
    _v1_r = compute_daily_returns(rank_df, "V1")
    _v3_r = compute_daily_returns(rank_df, "V3")
    _v1_sharpe = compute_sharpe(_v1_r)["sharpe"]
    _v3_sharpe = compute_sharpe(_v3_r)["sharpe"]
    if _v3_sharpe > _v1_sharpe:
        print(f"🏆 V3 (contrarian) gagne : Sharpe {_v3_sharpe:.3f} vs {_v1_sharpe:.3f} (+{(_v3_sharpe/_v1_sharpe-1)*100:.0f}%)")
    else:
        print(f"🏆 V1 (baseline) gagne : Sharpe {_v1_sharpe:.3f} vs {_v3_sharpe:.3f}")


if __name__ == "__main__":
    main()
