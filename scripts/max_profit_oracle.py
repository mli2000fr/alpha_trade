"""
Oracle du profit maximum (« perfect foresight »).

À partir des candidats historiques dans ``stock_scores_history``, calcule le
profit maximum théorique qu'il aurait été possible de réaliser en connaissant
l'historique complet des prix à l'avance, **tout en respectant toutes les
contraintes du preset capital** (max positions, poids max par position,
cap secteur, drawdown max, perte quotidienne max, position sizing).

--------------------------------------------------------------------------------
CONCEPT : Oracle vs Réalité
--------------------------------------------------------------------------------

L'oracle choisit les candidats en fonction du **forward return** (connu).
En réalité, on ne dispose que du **signal** (final_score, trend_score, etc.).

    Oracle  → sélection par forward_return (parfait)    → profit max théorique
    Réalité → sélection par final_score (imparfait)     → profit réel
                        ↑
                   gap à réduire

Le ratio « taux de capture » = profit_réel / profit_oracle × 100 dépend de la
corrélation entre le signal et le forward return.

Plus l'horizon est long, plus le signal devient prédictif (résultats mesurés) :

    Horizon 1 jour  → corr ~ -0.01   (bruit pur)
    Horizon 5 jours → corr ~ +0.005  (très faible)
    Horizon 10 jours → corr ~ +0.018 (faible, directionnel)
    Horizon 20 jours → corr ~ +0.030 (~3% de l'info capturée)

→ Pour un oracle réaliste, utiliser ``--holding-days 10`` ou ``20``,
pas 1 jour.

--------------------------------------------------------------------------------
VALIDATION DU SIGNAL (SQL)
--------------------------------------------------------------------------------

Vérifier que les données existent sur la période cible :

.. code-block:: sql

    -- 1) Plage des candidats dans stock_scores_history
    SELECT MIN(snapshot_date), MAX(snapshot_date), COUNT(*)
    FROM stock_scores_history
    WHERE selection_rank IS NOT NULL
      AND capital_preset_key = 'capital_2001_5000';

    -- 2) Plage des prix dans stock_bars_daily
    SELECT MIN(date), MAX(date), COUNT(DISTINCT date)
    FROM stock_bars_daily
    WHERE symbol = 'AAPL';

Mesurer la corrélation signal ↔ forward return (Pearson manuel, MySQL < 8.0) :

.. code-block:: sql

    SELECT
        COUNT(*) AS n,
        ROUND(
            (COUNT(*) * SUM(s.final_score * fwd.fwd) - SUM(s.final_score) * SUM(fwd.fwd))
            / SQRT(
                (COUNT(*) * SUM(POW(s.final_score,2)) - POW(SUM(s.final_score),2))
                * (COUNT(*) * SUM(POW(fwd.fwd,2)) - POW(SUM(fwd.fwd),2))
            ), 4
        ) AS corr_score_vs_fwd_return
    FROM stock_scores_history s
    JOIN (
        SELECT b.symbol, b.date,
               (b5.close - b.close) / NULLIF(b.close, 0) AS fwd
        FROM stock_bars_daily b
        JOIN stock_bars_daily b5 ON b5.symbol = b.symbol
            AND b5.date = DATE_ADD(b.date, INTERVAL 10 DAY)
        WHERE b.date BETWEEN '2018-01-02' AND '2023-09-14'
    ) fwd ON fwd.symbol = s.symbol AND fwd.date = s.snapshot_date
    WHERE s.selection_rank IS NOT NULL
      AND s.capital_preset_key = 'capital_2001_5000'
      AND s.snapshot_date BETWEEN '2018-01-02' AND '2023-09-14';

Remplacer ``INTERVAL 10 DAY`` par 5, 20 et ``s.final_score`` par
``s.trend_score``, ``s.short_score``, ``s.sentiment_net_agg`` pour explorer.

--------------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------------

.. code-block:: bash

    # Preset par clé explicite
    python scripts/max_profit_oracle.py --start 2018-01-01 --end 2023-09-14 \\
        --capital-preset-key capital_2001_5000

    # Preset auto-résolu par tranche d'equity (ex: 3000 $ → capital_2001_5000)
    python scripts/max_profit_oracle.py --start 2018-01-01 --end 2023-09-14 \\
        --equity 3000

    # Oracle réaliste : horizon 10 jours (aligné avec le pouvoir prédictif du signal)
    python scripts/max_profit_oracle.py --start 2018-01-01 --end 2023-09-14 \\
        --equity 4000 --holding-days 10

    # Lister les presets disponibles et leurs tranches
    python scripts/max_profit_oracle.py --list-presets

--------------------------------------------------------------------------------
INTERPRÉTATION DES RÉSULTATS
--------------------------------------------------------------------------------

Le rendement est **additif** (non composé) : la taille de position reste fixe,
le cash des gains s'accumule sans être réinvesti.

Avec un taux de capture de ~3% (corr 0.03 à horizon 20j), un oracle à +5000%
suggère un potentiel réel autour de +150% sur la période — soit ~15-20%/an.

Le résultat réel dépendra aussi de :
- Frais de transaction / slippage (non modélisés ici)
- Liquidité réelle (spread, impact marché)
- Qualité de l'exécution (prix d'entrée open vs close)
"""


from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import polars as pl

# Ajouter la racine du projet au PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.capital_presets import require_capital_preset
from common.logging_setup import configure_root_logging
from common.utils import getLastDateMarche
from database.connection import SessionLocal, get_sqlalchemy_engine
from sqlalchemy import MetaData, Table, and_, select, text

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reflect_tables():
    engine = get_sqlalchemy_engine()
    metadata = MetaData()
    scores_hist = Table("stock_scores_history", metadata, autoload_with=engine)
    bars_daily = Table("stock_bars_daily", metadata, autoload_with=engine)
    return scores_hist, bars_daily


def _load_candidates(
    session,
    scores_hist: Table,
    start: date,
    end: date,
    capital_preset_key: str,
) -> pd.DataFrame:
    """Charge les candidats depuis stock_scores_history."""
    LOGGER.info(
        "Chargement candidats : %s → %s, capital_preset_key=%s",
        start, end, capital_preset_key,
    )

    # On élargit la fenêtre pour avoir les prix futurs (holding-days en plus côté end)
    q = (
        select(
            scores_hist.c.snapshot_date,
            scores_hist.c.symbol,
            scores_hist.c.sector,
            scores_hist.c.final_score,
            scores_hist.c.short_score,
            scores_hist.c.selection_rank,
        )
        .where(
            and_(
                scores_hist.c.snapshot_date.between(start, end),
                scores_hist.c.capital_preset_key == capital_preset_key,
                scores_hist.c.selection_rank.is_not(None),
            )
        )
        .order_by(scores_hist.c.snapshot_date, scores_hist.c.selection_rank)
    )
    rows = session.execute(q).mappings().all()
    df = pd.DataFrame(rows)
    if df.empty:
        LOGGER.warning("Aucun candidat trouvé pour la période.")
        return df
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    LOGGER.info(
        "Candidats chargés : %d lignes, %d jours uniques, %d symboles uniques",
        len(df),
        df["snapshot_date"].nunique(),
        df["symbol"].nunique(),
    )
    return df


def _load_prices(
    session,
    bars_daily: Table,
    symbols: list[str],
    start: date,
    end_buffer: date,
) -> pl.DataFrame:
    """Charge les prix close depuis stock_bars_daily.

    ``end_buffer`` = end + holding_days pour avoir les prix futurs.
    """
    LOGGER.info("Chargement prix : %d symboles, %s → %s", len(symbols), start, end_buffer)
    # Découpage par lots pour éviter les requêtes trop larges
    all_frames: list[pl.DataFrame] = []
    batch_size = 2000
    symbol_list = sorted(set(str(s) for s in symbols if s))

    for i in range(0, len(symbol_list), batch_size):
        batch = symbol_list[i : i + batch_size]
        q = (
            select(
                bars_daily.c.symbol,
                bars_daily.c.date,
                bars_daily.c.close,
            )
            .where(
                and_(
                    bars_daily.c.symbol.in_(batch),
                    bars_daily.c.date.between(start, end_buffer),
                )
            )
            .order_by(bars_daily.c.symbol, bars_daily.c.date)
        )
        rows = session.execute(q).mappings().all()
        if rows:
            batch_df = pl.DataFrame(
                {
                    "symbol": [r["symbol"] for r in rows],
                    "date": [r["date"] for r in rows],
                    "close": [float(r["close"]) for r in rows],
                }
            )
            all_frames.append(batch_df)

    if not all_frames:
        return pl.DataFrame(schema={"symbol": pl.Utf8, "date": pl.Date, "close": pl.Float64})

    prices = pl.concat(all_frames).unique(subset=["symbol", "date"])
    LOGGER.info("Prix chargés : %d lignes", len(prices))
    return prices


# ---------------------------------------------------------------------------
# Calcul du forward return
# ---------------------------------------------------------------------------


def _compute_forward_returns(
    prices: pl.DataFrame,
    holding_days: int,
) -> pl.DataFrame:
    """Pour chaque (symbol, date), calcule le forward return sur ``holding_days``.

    forward_return = (close_{t+holding_days} / close_t) - 1

    Les jours sans prix futur (fin de série) auront forward_return = None.
    """
    prices = prices.sort(["symbol", "date"])
    # shift négatif car on veut le prix futur
    future_close = prices.group_by("symbol", maintain_order=True).agg(
        pl.col("close").shift(-holding_days).alias("future_close")
    )
    # flatten
    future_close = future_close.explode("future_close")
    prices = prices.with_columns(future_close["future_close"])
    prices = prices.with_columns(
        ((pl.col("future_close") / pl.col("close")) - 1.0).alias("forward_return")
    )
    return prices


# ---------------------------------------------------------------------------
# Simulation oracle
# ---------------------------------------------------------------------------


def _run_oracle(
    candidates: pd.DataFrame,
    prices: pl.DataFrame,
    preset_values: dict,
    top_n: int,
    holding_days: int,
    long_only: bool,
    short_only: bool,
    equity_override: float | None = None,
) -> dict:
    """Simule le profit max théorique en respectant les contraintes du preset.

    Gère un portefeuille de positions avec :
    - max_positions (total long+short)
    - max_position_weight (% equity par position)
    - max_sector_weight (% equity par secteur)
    - max_drawdown (arrêt si dépassé)
    - max_daily_loss (arrêt si perte quotidienne > seuil)
    - Position sizing : equity / max_positions, capé par max_position_weight
    """
    # Extraire les contraintes du preset
    _raw_equity = preset_values.get("risk_account_equity", None)
    if _raw_equity is None or str(_raw_equity).strip() == "__DETECTED_EQUITY__":
        # Placeholder → utiliser l'override ou le min_equity du preset ou défaut
        equity = float(equity_override or preset_values.get("_min_equity", 10_000) or 10_000)
    else:
        equity = float(_raw_equity)
    max_positions = int(preset_values.get("risk_max_positions", top_n) or top_n)
    max_position_weight = float(preset_values.get("risk_max_position_weight", 0.35) or 0.35)
    max_sector_weight = float(preset_values.get("risk_max_sector_weight", 0.55) or 0.55)
    max_drawdown_pct = float(preset_values.get("risk_max_drawdown_pct", 0.15) or 0.15)
    max_daily_loss_pct = float(preset_values.get("risk_max_daily_loss_pct", 0.025) or 0.025)
    per_trade_risk_pct = float(preset_values.get("risk_per_trade_pct", 0.01) or 0.01)

    # Position size: equal weight, capped
    base_position_notional = equity / max(max_positions, 1)
    max_position_notional = equity * max_position_weight
    position_notional = min(base_position_notional, max_position_notional)

    LOGGER.info(
        "Contraintes preset : equity=%.0f max_pos=%d pos_weight=%.0f%% sector_weight=%.0f%% "
        "dd_max=%.1f%% daily_loss_max=%.1f%% pos_size=%.0f",
        equity, max_positions, max_position_weight * 100, max_sector_weight * 100,
        max_drawdown_pct * 100, max_daily_loss_pct * 100, position_notional,
    )

    if candidates.empty:
        LOGGER.warning("Aucun candidat — simulation vide.")
        return _empty_result()

    # Index prix : (symbol, date) -> forward_return
    prices_pd = prices.to_pandas()
    prices_pd["date"] = pd.to_datetime(prices_pd["date"]).dt.date
    price_lookup: dict[str, dict] = {}
    for sym, grp in prices_pd.groupby("symbol"):
        price_lookup[sym] = dict(zip(grp["date"], grp["forward_return"]))

    # Secteurs : dict[symbol] -> sector (None si pas dispo)
    symbol_sector: dict[str, str | None] = {}
    if "sector" in candidates.columns:
        for _, row in candidates[["symbol", "sector"]].drop_duplicates("symbol").iterrows():
            symbol_sector[row["symbol"]] = row["sector"] if pd.notna(row["sector"]) else None

    trading_days = sorted(candidates["snapshot_date"].unique())

    # État du portefeuille
    open_positions: dict[str, dict] = {}  # symbol -> {side, entry_date, exit_date, entry_notional, sector}
    cash = equity
    peak_equity = equity
    max_dd_hit = False
    daily_entries: list[dict] = []
    total_trades = 0

    for day in trading_days:
        if max_dd_hit:
            break

        # --- 1) Clôturer les positions arrivées à échéance ---
        to_close = [
            sym for sym, pos in open_positions.items()
            if day >= pos["exit_date"]
        ]
        day_pnl_cash = 0.0
        for sym in to_close:
            pos = open_positions.pop(sym)
            fwd_ret = price_lookup.get(sym, {}).get(pos["entry_date"])
            if fwd_ret is None or (isinstance(fwd_ret, float) and pd.isna(fwd_ret)):
                continue
            if pos["side"] == "long":
                pnl = fwd_ret * pos["entry_notional"]
            else:
                pnl = -fwd_ret * pos["entry_notional"]
            cash += pos["entry_notional"] + pnl
            day_pnl_cash += pnl

        # --- 2) Vérifier drawdown / daily loss ---
        current_equity = cash + sum(p["entry_notional"] for p in open_positions.values())
        peak_equity = max(peak_equity, current_equity)
        dd_pct = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0.0
        if dd_pct >= max_drawdown_pct:
            LOGGER.warning("Drawdown max atteint %.1f%% ≥ %.1f%% — arrêt oracle.", dd_pct * 100, max_drawdown_pct * 100)
            max_dd_hit = True
            # Clôture forcée de toutes les positions
            day_pnl_cash = 0.0
            for sym, pos in list(open_positions.items()):
                fwd_ret = price_lookup.get(sym, {}).get(pos["entry_date"])
                if fwd_ret is not None and not (isinstance(fwd_ret, float) and pd.isna(fwd_ret)):
                    pnl = fwd_ret * pos["entry_notional"] if pos["side"] == "long" else -fwd_ret * pos["entry_notional"]
                    cash += pos["entry_notional"] + pnl
                    day_pnl_cash += pnl
                else:
                    cash += pos["entry_notional"]
            open_positions.clear()

        daily_equity = cash + sum(p["entry_notional"] for p in open_positions.values())
        daily_pnl_pct = day_pnl_cash / daily_equity if daily_equity > 0 else 0.0
        if max_daily_loss_pct > 0 and daily_pnl_pct < -max_daily_loss_pct:
            LOGGER.warning(
                "Perte quotidienne %.2f%% > %.2f%% — arrêt oracle (jour %s).",
                -daily_pnl_pct * 100, max_daily_loss_pct * 100, day,
            )
            max_dd_hit = True

        # --- 3) Sélectionner de nouveaux candidats ---
        day_candidates = candidates[candidates["snapshot_date"] == day].copy()
        if day_candidates.empty:
            daily_entries.append({
                "date": day, "equity": round(daily_equity, 2),
                "open_positions": len(open_positions), "day_pnl_pct": round(daily_pnl_pct, 6),
                "new_long": 0, "new_short": 0,
            })
            continue

        # Récupérer forward returns
        fwd_returns = []
        valid_mask = []
        for _, row in day_candidates.iterrows():
            sym = row["symbol"]
            fr = price_lookup.get(sym, {}).get(day)
            fwd_returns.append(fr)
            valid_mask.append(fr is not None and not (isinstance(fr, float) and pd.isna(fr)))

        day_candidates["forward_return"] = fwd_returns
        day_candidates = day_candidates[valid_mask].copy()

        # Exclure les symboles déjà en position
        day_candidates = day_candidates[~day_candidates["symbol"].isin(open_positions.keys())]

        if day_candidates.empty:
            daily_entries.append({
                "date": day, "equity": round(daily_equity, 2),
                "open_positions": len(open_positions), "day_pnl_pct": round(daily_pnl_pct, 6),
                "new_long": 0, "new_short": 0,
            })
            continue

        day_candidates = day_candidates.sort_values("forward_return", ascending=False)

        # --- 4) Respecter les contraintes de secteur ---
        # Calculer l'exposition actuelle par secteur
        sector_exposure: dict[str | None, float] = {}
        for pos in open_positions.values():
            sec = pos.get("sector")
            sector_exposure[sec] = sector_exposure.get(sec, 0.0) + pos["entry_notional"]

        available_slots = max_positions - len(open_positions)
        if available_slots <= 0:
            daily_entries.append({
                "date": day, "equity": round(daily_equity, 2),
                "open_positions": len(open_positions), "day_pnl_pct": round(daily_pnl_pct, 6),
                "new_long": 0, "new_short": 0,
            })
            continue

        new_long = 0
        new_short = 0

        # Long : top forward returns
        if not short_only:
            for _, row in day_candidates.iterrows():
                if new_long + new_short >= available_slots:
                    break
                sym = row["symbol"]
                sec = symbol_sector.get(sym)
                sec_exp = sector_exposure.get(sec, 0.0)
                if max_sector_weight > 0 and (sec_exp + position_notional) / daily_equity > max_sector_weight:
                    continue  # secteur saturé
                fwd_ret = row["forward_return"]
                if fwd_ret is None or (isinstance(fwd_ret, float) and pd.isna(fwd_ret)):
                    continue
                # Ne prendre que les retours positifs en long
                if fwd_ret <= 0:
                    continue
                open_positions[sym] = {
                    "side": "long",
                    "entry_date": day,
                    "exit_date": day + timedelta(days=holding_days),
                    "entry_notional": position_notional,
                    "sector": sec,
                }
                sector_exposure[sec] = sector_exposure.get(sec, 0.0) + position_notional
                cash -= position_notional
                new_long += 1
                total_trades += 1

        # Short : bottom forward returns (les plus négatifs)
        if not long_only:
            # Re-trier par forward_return ASC pour les shorts
            short_candidates = day_candidates.sort_values("forward_return", ascending=True)
            for _, row in short_candidates.iterrows():
                if new_long + new_short >= available_slots:
                    break
                sym = row["symbol"]
                if sym in open_positions:
                    continue
                sec = symbol_sector.get(sym)
                sec_exp = sector_exposure.get(sec, 0.0)
                if max_sector_weight > 0 and (sec_exp + position_notional) / daily_equity > max_sector_weight:
                    continue
                fwd_ret = row["forward_return"]
                if fwd_ret is None or (isinstance(fwd_ret, float) and pd.isna(fwd_ret)):
                    continue
                # Ne prendre que les retours négatifs en short
                if fwd_ret >= 0:
                    continue
                open_positions[sym] = {
                    "side": "short",
                    "entry_date": day,
                    "exit_date": day + timedelta(days=holding_days),
                    "entry_notional": position_notional,
                    "sector": sec,
                }
                sector_exposure[sec] = sector_exposure.get(sec, 0.0) + position_notional
                cash -= position_notional
                new_short += 1
                total_trades += 1

        daily_equity = cash + sum(p["entry_notional"] for p in open_positions.values())
        daily_entries.append({
            "date": day, "equity": round(daily_equity, 2),
            "open_positions": len(open_positions), "day_pnl_pct": round(daily_pnl_pct, 6),
            "new_long": new_long, "new_short": new_short,
        })

    if not daily_entries:
        return _empty_result()

    daily_df = pd.DataFrame(daily_entries)
    final_equity = daily_df["equity"].iloc[-1] if not daily_df.empty else equity
    total_return = (final_equity - equity) / equity

    return {
        "start_date": str(trading_days[0]),
        "end_date": str(trading_days[-1]),
        "trading_days_total": len(trading_days),
        "days_simulated": len(daily_df),
        "total_trades": total_trades,
        "max_positions": max_positions,
        "position_notional": round(position_notional, 0),
        "holding_days": holding_days,
        "starting_equity": round(equity, 0),
        "final_equity": round(final_equity, 0),
        "total_return_pct": round(total_return * 100, 2),
        "max_drawdown_hit": max_dd_hit,
        "daily_df": daily_df,
    }


def _empty_result() -> dict:
    return {
        "start_date": None, "end_date": None,
        "trading_days_total": 0, "days_simulated": 0,
        "total_trades": 0, "max_positions": 0,
        "position_notional": 0, "holding_days": 0,
        "starting_equity": 0, "final_equity": 0,
        "total_return_pct": 0.0, "max_drawdown_hit": False,
        "daily_df": pd.DataFrame(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Oracle du profit maximum théorique (perfect foresight) sur les candidats historiques.",
        epilog=(
            "Exemples:\n"
            "  # Preset par clé explicite\n"
            "  python scripts/max_profit_oracle.py --start 2024-01-01 --end 2024-06-30 "
            "--capital-preset-key capital_2001_5000\n\n"
            "  # Preset auto-détecté par tranche d'equity (2001$ → 5000$)\n"
            "  python scripts/max_profit_oracle.py --start 2024-01-01 --end 2024-06-30 --equity 3000\n\n"
            "  # Long only, horizon 5 jours\n"
            "  python scripts/max_profit_oracle.py --start 2024-01-01 --end 2024-06-30 "
            "--equity 10000 --holding-days 5 --long-only\n\n"
            "  # Lister les presets disponibles\n"
            "  python scripts/max_profit_oracle.py --list-presets"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start", required=True, help="Date début (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Date fin (YYYY-MM-DD)")
    parser.add_argument(
        "--capital-preset-key",
        default=None,
        help="Preset capital par clé (ex: capital_2001_5000). Prioritaire sur --equity.",
    )
    parser.add_argument(
        "--equity",
        type=float,
        default=None,
        help="Capital détecté ($) — le preset est auto-résolu par tranche (ex: 3000 → capital_2001_5000). "
             "Ignoré si --capital-preset-key est fourni.",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Afficher les presets disponibles et leurs tranches d'equity, puis quitter.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=0,
        help="Nombre de positions long/short par jour (défaut: risk_max_positions du preset, 0 = auto)",
    )
    parser.add_argument(
        "--holding-days",
        type=int,
        default=1,
        help="Horizon de détention en jours (défaut: 1)",
    )
    parser.add_argument(
        "--long-only",
        action="store_true",
        help="Simuler uniquement les positions longues",
    )
    parser.add_argument(
        "--short-only",
        action="store_true",
        help="Simuler uniquement les positions courtes",
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default=None,
        help="Exporter le P&L quotidien dans un CSV",
    )
    args = parser.parse_args()

    configure_root_logging(
        level=logging.INFO,
        log_path="./log/max_profit_oracle.log",
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # --list-presets : afficher et quitter
    if args.list_presets:
        from common.capital_presets import load_capital_presets
        presets = load_capital_presets()
        print(f"{'Preset key':<35} {'Equity min':>12} {'Equity max':>12} {'Max pos':>8} {'Label'}")
        print("-" * 100)
        for p in presets:
            label = (p.label or "")[:40]
            max_pos = int(p.values.get("risk_max_positions", 0) or 0)
            max_eq = f"{p.max_equity:,.0f}" if p.max_equity else "∞"
            print(f"{p.key:<35} {p.min_equity:>12,.0f} {max_eq:>12} {max_pos:>8} {label}")
        return

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)

    if args.long_only and args.short_only:
        LOGGER.error("--long-only et --short-only sont mutuellement exclusifs.")
        sys.exit(1)

    # Résoudre le preset capital
    from common.capital_presets import resolve_capital_preset_for_equity
    if args.capital_preset_key:
        preset = require_capital_preset(args.capital_preset_key)
    elif args.equity is not None and args.equity > 0:
        preset = resolve_capital_preset_for_equity(args.equity)
        if preset is None:
            LOGGER.error("Aucun preset trouvé pour equity=%.0f $. Utilisez --list-presets.", args.equity)
            sys.exit(1)
        LOGGER.info("Preset auto-résolu : %s (equity=%.0f $)", preset.key, args.equity)
    else:
        preset = require_capital_preset("capital_50001_100000")
        LOGGER.info("Preset par défaut : %s", preset.key)
    preset_values = dict(preset.values)
    max_positions = int(preset_values.get("risk_max_positions", 10) or 10)
    top_n = args.top_n if args.top_n > 0 else max_positions
    if top_n > max_positions:
        LOGGER.warning(
            "--top-n=%d dépasse risk_max_positions=%d du preset → plafonné à %d",
            top_n, max_positions, max_positions,
        )
        top_n = max_positions
    # Injecter le top_n effectif dans les valeurs du preset pour l'oracle
    preset_values["risk_max_positions"] = top_n
    # Passer le min_equity pour le fallback du placeholder __DETECTED_EQUITY__
    preset_values["_min_equity"] = float(preset.min_equity)

    LOGGER.info(
        "=== Oracle profit max : %s → %s | top_n=%d (max_preset=%d) | holding=%dj | preset=%s ===",
        start_date, end_date, top_n, max_positions, args.holding_days, preset.key,
    )
    if args.long_only:
        LOGGER.info("Mode: LONG uniquement")
    elif args.short_only:
        LOGGER.info("Mode: SHORT uniquement")
    else:
        LOGGER.info("Mode: LONG + SHORT")

    session = SessionLocal()
    try:
        scores_hist, bars_daily = _reflect_tables()

        # 1) Charger les candidats
        candidates = _load_candidates(session, scores_hist, start_date, end_date, preset.key)
        if candidates.empty:
            LOGGER.warning("Aucun candidat — arrêt.")
            return

        # 2) Charger les prix (avec buffer pour les forward returns)
        all_symbols = candidates["symbol"].unique().tolist()
        end_buffer = end_date + timedelta(days=args.holding_days + 5)
        prices = _load_prices(session, bars_daily, all_symbols, start_date, end_buffer)
        if prices.is_empty():
            LOGGER.warning("Aucun prix trouvé — arrêt.")
            return

        # 3) Calculer les forward returns
        prices = _compute_forward_returns(prices, args.holding_days)

        # 4) Lancer l'oracle
        result = _run_oracle(
            candidates=candidates,
            prices=prices,
            preset_values=preset_values,
            top_n=top_n,
            holding_days=args.holding_days,
            long_only=args.long_only,
            short_only=args.short_only,
            equity_override=args.equity,
        )

        # 5) Afficher les résultats
        LOGGER.info("=" * 60)
        LOGGER.info("RÉSULTATS — Oracle du profit maximum (respecte les contraintes preset)")
        LOGGER.info("=" * 60)
        LOGGER.info("  Période                 : %s → %s", result["start_date"], result["end_date"])
        LOGGER.info("  Jours de trading total  : %d", result["trading_days_total"])
        LOGGER.info("  Jours simulés           : %d", result["days_simulated"])
        LOGGER.info("  Nombre total de trades  : %d", result["total_trades"])
        LOGGER.info("  Max positions (preset)  : %d", result["max_positions"])
        LOGGER.info("  Taille par position     : %.0f $", result["position_notional"])
        LOGGER.info("  Horizon (jours)         : %d", result["holding_days"])
        LOGGER.info("---")
        LOGGER.info("  Capital initial         : %.0f $", result["starting_equity"])
        LOGGER.info("  Capital final           : %.0f $", result["final_equity"])
        LOGGER.info("  Rendement total         : %.2f %%", result["total_return_pct"])
        LOGGER.info("  Drawdown max atteint    : %s", "OUI (arrêt)" if result["max_drawdown_hit"] else "NON")
        LOGGER.info("---")
        if result.get("daily_df") is not None and not result["daily_df"].empty:
            dd = result["daily_df"]
            LOGGER.info("  Positions moyennes      : %.1f", dd["open_positions"].mean())
            LOGGER.info("  P&L quotidien moyen     : %.2f $", dd["equity"].diff().mean())
            LOGGER.info("  Nouveaux longs / jour   : %.1f", dd["new_long"].mean())
            LOGGER.info("  Nouveaux shorts / jour  : %.1f", dd["new_short"].mean())

        # 6) Export CSV
        if args.export_csv:
            daily_df = result.get("daily_df")
            if daily_df is not None and not daily_df.empty:
                daily_df.to_csv(args.export_csv, index=False)
                LOGGER.info("Équité quotidienne exportée → %s", args.export_csv)
    finally:
        session.close()

    LOGGER.info("Terminé.")


if __name__ == "__main__":
    main()
