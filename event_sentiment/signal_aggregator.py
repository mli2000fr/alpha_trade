"""
event_sentiment/signal_aggregator.py
=====================================
Fusion des scores de sentiment (pipeline FinBERT) avec les scores quantitatifs
du screener/selector (table stock_scores).

Contexte : le pipeline EventSentimentPipeline produit deux types de features :
  - ticker_daily_features  : sentiment_net_mean_1d, news_count_1d, major_event_flag, … par (symbol, trade_date)
  - sector_daily_features  : sector_impact_score, macro_event_intensity, … par (sector, trade_date)

Ces scores n'étaient JAMAIS consommés par AlphaScanner. Ce module crée la jonction.

Architecture :
  AlphaScanner.run()                         EventSentimentPipeline.run()
       │                                              │
       ▼                                              ▼
  stock_scores (DB)                    ticker_daily_features (DB)
       │                               sector_daily_features (DB)
       └──────────── SentimentSignalAggregator.merge() ─────────────┐
                                                                     ▼
                                                        final_score ajusté (sentiment boost)

Usage typique :
    from event_sentiment.signal_aggregator import SentimentSignalAggregator, SentimentBoostConfig
    from sqlalchemy.engine import Engine

    config = SentimentBoostConfig(sentiment_weight=0.15, macro_sector_weight=0.10)
    agg = SentimentSignalAggregator(engine, config)
    adjusted_scores = agg.merge(scores_df, trade_date=date.today())
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SentimentBoostConfig:
    """
    Paramètres de fusion sentiment → score quantitatif.

    sentiment_weight     : fraction du final_score attribuée au signal de sentiment
                           ticker (sentiment_net_mean_1d normalisé). Défaut 15 %.
    macro_sector_weight  : fraction attribuée au signal macro sectoriel
                           (sector_impact_score normalisé). Défaut 10 %.
    quant_weight         : fraction conservée pour le score quantitatif originel.
                           Défaut 75 %. La somme des trois doit être 1.0.
    lookback_days        : fenêtre en jours pour la moyenne glissante du sentiment
                           (robustesse au bruit d'un seul article). Défaut 5 jours.
    min_news_count       : nb minimal d'articles pour activer le boost sentiment
                           (évite les signaux sur 1 seul article). Défaut 2.

    Validation : sentiment_weight + macro_sector_weight + quant_weight doit ≈ 1.0.
    Pour calibrer les poids, calculer IC (Information Coefficient) sentiment → retour
    J+1/J+5 sur historique via backtest.
    """
    sentiment_weight: float = 0.15
    macro_sector_weight: float = 0.10
    quant_weight: float = 0.75
    lookback_days: int = 5
    min_news_count: int = 2

    def __post_init__(self) -> None:
        total = self.sentiment_weight + self.macro_sector_weight + self.quant_weight
        if not np.isclose(total, 1.0, atol=1e-4):
            raise ValueError(
                f"sentiment_weight + macro_sector_weight + quant_weight doit être égal à 1.0 "
                f"(actuel : {total:.4f})."
            )
        if self.lookback_days < 1:
            raise ValueError("lookback_days doit être >= 1.")
        if self.min_news_count < 1:
            raise ValueError("min_news_count doit être >= 1.")


class SentimentSignalAggregator:
    """
    Fusionne les scores du screener (stock_scores) avec les features de sentiment
    (ticker_daily_features, sector_daily_features) pour produire un final_score ajusté.

    Le signal sentiment est additif et borné : il ne peut pas inverser un signal
    quantitatif fort — il amplifie ou atténue légèrement la conviction.
    """

    def __init__(self, engine: Engine, config: SentimentBoostConfig | None = None) -> None:
        self.engine = engine
        self.config = config or SentimentBoostConfig()

    # ------------------------------------------------------------------
    # Chargement depuis la DB
    # ------------------------------------------------------------------

    def _load_ticker_sentiment(self, symbols: list[str], trade_date: date) -> pd.DataFrame:
        """Charge les features de sentiment ticker pour les N derniers jours."""
        if not symbols:
            return pd.DataFrame()

        cutoff = pd.Timestamp(trade_date) - pd.Timedelta(days=self.config.lookback_days)
        stmt = text(
            """
            SELECT symbol,
                   trade_date,
                   news_count_1d,
                   sentiment_net_mean_1d,
                   sentiment_confidence_mean_1d,
                   major_event_flag
            FROM ticker_daily_sentiment_features
            WHERE symbol IN :symbols
              AND trade_date >= :cutoff
              AND trade_date <= :trade_date
            ORDER BY symbol, trade_date
            """
        ).bindparams(symbols=symbols, cutoff=cutoff.date(), trade_date=trade_date)

        try:
            from sqlalchemy import bindparam
            stmt = text(
                """
                SELECT symbol,
                       trade_date,
                       news_count_1d,
                       sentiment_net_mean_1d,
                       sentiment_confidence_mean_1d,
                       major_event_flag
                FROM ticker_daily_sentiment_features
                WHERE symbol IN :symbols
                  AND trade_date >= :cutoff
                  AND trade_date <= :trade_date
                ORDER BY symbol, trade_date
                """
            ).bindparams(bindparam("symbols", expanding=True))
            with self.engine.connect() as conn:
                return pd.read_sql_query(
                    stmt, conn,
                    params={"symbols": symbols, "cutoff": cutoff.date(), "trade_date": trade_date},
                )
        except Exception:
            LOGGER.warning("ticker_daily_sentiment_features indisponible — boost sentiment desactive.")
            return pd.DataFrame()

    def _load_sector_sentiment(self, sectors: list[str], trade_date: date) -> pd.DataFrame:
        """Charge les features macro sectorielles pour les N derniers jours."""
        if not sectors:
            return pd.DataFrame()

        cutoff = pd.Timestamp(trade_date) - pd.Timedelta(days=self.config.lookback_days)
        try:
            from sqlalchemy import bindparam
            stmt = text(
                """
                SELECT sector,
                       trade_date,
                       sector_impact_score,
                       macro_event_intensity,
                       macro_event_flag
                FROM sector_daily_sentiment_features
                WHERE sector IN :sectors
                  AND trade_date >= :cutoff
                  AND trade_date <= :trade_date
                ORDER BY sector, trade_date
                """
            ).bindparams(bindparam("sectors", expanding=True))
            with self.engine.connect() as conn:
                return pd.read_sql_query(
                    stmt, conn,
                    params={"sectors": sectors, "cutoff": cutoff.date(), "trade_date": trade_date},
                )
        except Exception:
            LOGGER.warning("sector_daily_sentiment_features indisponible — boost macro desactive.")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Agrégation + normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_ticker_window(ticker_df: pd.DataFrame, min_news_count: int) -> pd.DataFrame:
        """
        Agrège les N derniers jours de sentiment par symbole.
        Pondère par news_count pour donner plus de poids aux jours avec plus d'articles.
        Retourne : [symbol, sentiment_net_agg, major_event_flag_agg, total_news]
        """
        if ticker_df.empty:
            return pd.DataFrame(columns=["symbol", "sentiment_net_agg", "major_event_flag_agg", "total_news"])

        df = ticker_df.copy()
        df["news_count_1d"] = df["news_count_1d"].fillna(0).astype(float)
        df["sentiment_net_mean_1d"] = df["sentiment_net_mean_1d"].fillna(0.0)
        df["major_event_flag"] = df["major_event_flag"].fillna(0).astype(int)

        def _weighted_avg(group: pd.DataFrame) -> pd.Series:
            total_news = group["news_count_1d"].sum()
            if total_news < min_news_count:
                return pd.Series({
                    "sentiment_net_agg": 0.0,
                    "major_event_flag_agg": 0,
                    "total_news": int(total_news),
                    "signal_active": False,
                })
            weights = group["news_count_1d"] / total_news
            weighted_net = (group["sentiment_net_mean_1d"] * weights).sum()
            return pd.Series({
                "sentiment_net_agg": float(weighted_net),
                "major_event_flag_agg": int(group["major_event_flag"].max()),
                "total_news": int(total_news),
                "signal_active": True,
            })

        return df.groupby("symbol", as_index=False).apply(_weighted_avg).reset_index(drop=True)

    @staticmethod
    def _aggregate_sector_window(sector_df: pd.DataFrame) -> pd.DataFrame:
        """
        Agrège les N derniers jours d'impact macro par secteur.
        Retourne : [sector, sector_impact_agg, macro_event_flag_agg]
        """
        if sector_df.empty:
            return pd.DataFrame(columns=["sector", "sector_impact_agg", "macro_event_flag_agg"])

        df = sector_df.copy()
        df["sector_impact_score"] = df["sector_impact_score"].fillna(0.0)
        df["macro_event_flag"] = df["macro_event_flag"].fillna(0).astype(int)

        return (
            df.groupby("sector", as_index=False)
            .agg(
                sector_impact_agg=("sector_impact_score", "mean"),
                macro_event_flag_agg=("macro_event_flag", "max"),
            )
        )

    @staticmethod
    def _normalize_to_01(series: pd.Series) -> pd.Series:
        """Normalisation min-max avec winsorisation 1%-99%."""
        numeric = pd.to_numeric(series, errors="coerce")
        non_null = numeric.dropna()
        if non_null.empty:
            return pd.Series(0.5, index=numeric.index, dtype=float)
        lo, hi = float(non_null.quantile(0.01)), float(non_null.quantile(0.99))
        clipped = numeric.clip(lo, hi)
        if np.isclose(hi, lo):
            return pd.Series(0.5, index=numeric.index, dtype=float)
        return ((clipped - lo) / (hi - lo)).clip(0.0, 1.0)

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    def merge(
        self,
        scores_df: pd.DataFrame,
        trade_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        Fusionne les scores quantitatifs avec le signal de sentiment.

        :param scores_df: DataFrame issu de AlphaScanner.run() avec au minimum
                          [symbol, final_score, sector].
        :param trade_date: Date de référence (aujourd'hui si None).
        :return: DataFrame enrichi avec les colonnes :
                 - sentiment_net_agg       : sentiment moyen pondéré sur la fenêtre
                 - sector_impact_agg       : impact macro sectoriel moyen
                 - final_score             : score quantitatif AlphaScanner (inchangé)
                 - final_score_sentiment   : score fusionné quant + sentiment (nouveau champ)
        """
        if scores_df.empty:
            return scores_df.copy()

        ref_date = trade_date or date.today()
        result = scores_df.copy()

        symbols = result["symbol"].dropna().astype(str).tolist()
        sectors = result["sector"].dropna().unique().tolist() if "sector" in result.columns else []

        # --- Chargement ---
        ticker_df = self._load_ticker_sentiment(symbols, ref_date)
        sector_df = self._load_sector_sentiment(sectors, ref_date) if sectors else pd.DataFrame()

        # --- Agrégation fenêtrée ---
        ticker_agg = self._aggregate_ticker_window(ticker_df, self.config.min_news_count)
        sector_agg = self._aggregate_sector_window(sector_df)

        LOGGER.info(
            "SentimentSignalAggregator | trade_date=%s symboles=%s ticker_signaux=%s secteurs=%s",
            ref_date,
            len(symbols),
            int(ticker_agg.get("signal_active", pd.Series(False)).sum()) if not ticker_agg.empty else 0,
            len(sector_agg),
        )

        # --- Jointure scores quantitatifs ← ticker sentiment ---
        if not ticker_agg.empty and "symbol" in ticker_agg.columns:
            result = result.merge(
                ticker_agg[["symbol", "sentiment_net_agg", "major_event_flag_agg", "total_news", "signal_active"]],
                on="symbol", how="left",
            )
        else:
            result["sentiment_net_agg"] = 0.0
            result["major_event_flag_agg"] = 0
            result["total_news"] = 0
            result["signal_active"] = False

        # --- Jointure scores quantitatifs ← impact macro sectoriel ---
        if not sector_agg.empty and "sector" in result.columns:
            result = result.merge(sector_agg, on="sector", how="left")
        else:
            result["sector_impact_agg"] = 0.0
            result["macro_event_flag_agg"] = 0

        result["sentiment_net_agg"] = result["sentiment_net_agg"].fillna(0.0)
        result["sector_impact_agg"] = result["sector_impact_agg"].fillna(0.0)
        result["signal_active"] = result["signal_active"].fillna(False)

        # --- Normalisation des signaux sentiment en [0, 1] ---
        # sentiment_net_agg ∈ [-1, 1] → normalisé → 0.5 = neutre
        result["sentiment_signal_norm"] = self._normalize_to_01(result["sentiment_net_agg"])
        result["macro_signal_norm"] = self._normalize_to_01(result["sector_impact_agg"])

        # --- Composition du final_score_sentiment (score fusionné) ---
        # final_score reste intact (score quantitatif AlphaScanner).
        # final_score_sentiment = quant_weight * final_score + sentiment_weight * sent + macro_weight * macro
        # Le signal sentiment n'est activé que si signal_active=True (min_news_count atteint)
        sent_component = np.where(
            result["signal_active"],
            self.config.sentiment_weight * result["sentiment_signal_norm"],
            self.config.sentiment_weight * 0.5,  # neutre si pas assez de news
        )
        macro_component = self.config.macro_sector_weight * result["macro_signal_norm"]
        quant_component = self.config.quant_weight * result["final_score"].fillna(0.0)

        result["final_score_sentiment"] = (quant_component + sent_component + macro_component).clip(0.0, 1.0)

        LOGGER.info(
            "Boost sentiment applique | symboles_actifs=%s delta_score_moyen=%.4f",
            int(result["signal_active"].sum()),
            float((result["final_score_sentiment"] - result["final_score"]).mean()),
        )
        return result

    # ------------------------------------------------------------------
    # Persistance en base
    # ------------------------------------------------------------------

    def save_to_db(self, enriched_df: pd.DataFrame) -> int:
        """
        Persiste les scores de sentiment fusionnés dans stock_scores.

        Met à jour uniquement les colonnes de sentiment + final_score pour
        chaque symbole présent dans enriched_df (résultat de merge()).
        Utilise INSERT … ON DUPLICATE KEY UPDATE (upsert MySQL).

        :param enriched_df: DataFrame retourné par merge().
        :return: Nombre de lignes affectées.
        """
        SENTIMENT_COLS = [
            "sentiment_net_agg",
            "sector_impact_agg",
            "sentiment_signal_norm",
            "macro_signal_norm",
            "final_score_sentiment",
            "signal_active",
            "major_event_flag_agg",
            "macro_event_flag_agg",
            "total_news",
        ]

        required = {"symbol"} | set(SENTIMENT_COLS)
        missing = required - set(enriched_df.columns)
        if missing:
            raise ValueError(
                f"save_to_db : colonnes manquantes dans enriched_df : {missing}. "
                "Appelez merge() avant save_to_db()."
            )

        if enriched_df.empty:
            return 0

        now = pd.Timestamp.utcnow().replace(tzinfo=None)

        subset = enriched_df[["symbol"] + SENTIMENT_COLS].copy()
        subset["last_updated_sentiment"] = now

        # Conversion des types booléens pour MySQL
        for bool_col in ("signal_active", "major_event_flag_agg", "macro_event_flag_agg"):
            if bool_col in subset.columns:
                subset[bool_col] = subset[bool_col].fillna(False).astype(int)

        for float_col in ("sentiment_net_agg", "sector_impact_agg",
                          "sentiment_signal_norm", "macro_signal_norm",
                          "final_score_sentiment"):
            if float_col in subset.columns:
                subset[float_col] = pd.to_numeric(subset[float_col], errors="coerce")

        subset["total_news"] = subset["total_news"].fillna(0).astype(int)

        records = subset.to_dict(orient="records")

        # Nettoyage des NaN → None pour MySQL
        clean_records = [
            {k: (None if (isinstance(v, float) and np.isnan(v)) else v)
             for k, v in row.items()}
            for row in records
        ]

        update_set = ", ".join(
            f"{col} = :{col}"
            for col in SENTIMENT_COLS + ["last_updated_sentiment"]
        )

        stmt = text(
            f"""
            UPDATE stock_scores
            SET {update_set}
            WHERE symbol = :symbol
            """
        )

        with self.engine.begin() as conn:
            conn.execute(stmt, clean_records)

        LOGGER.info(
            "save_to_db | %d lignes upsertees dans stock_scores (colonnes sentiment).",
            len(clean_records),
        )
        return len(clean_records)


# ---------------------------------------------------------------------------
# Point d'entrée standalone
# ---------------------------------------------------------------------------
# Ordre d'exécution recommandé :
#   1. stock_screener.py          → scores quantitatifs de base
#   2. alpha_scanner.py           → trend_score, vcp_score, final_score (quant only)
#   3. sentiment_pipeline.py      → news → FinBERT → ticker/sector daily features
#   4. signal_aggregator.py       → fusion quant + sentiment → final_score définitif
#
# Usage :
#   python -m event_sentiment.signal_aggregator
#   python -m event_sentiment.signal_aggregator --all-symbols --trade-date 2026-04-17
#   python -m event_sentiment.signal_aggregator --sentiment-weight 0.20 --macro-weight 0.10
# ---------------------------------------------------------------------------

def _load_scores_from_db(engine: Engine, all_symbols: bool) -> pd.DataFrame:
    """
    Charge depuis stock_scores les colonnes nécessaires à merge().
    Par défaut ne charge que les candidats (is_candidate=1).
    Si all_symbols=True, charge tous les symboles.
    """
    where = "" if all_symbols else "WHERE is_candidate = 1"
    stmt = text(
        f"""
        SELECT symbol,
               final_score,
               trend_score,
               vcp_score,
               total_score,
               sector
        FROM stock_scores
        {where}
        ORDER BY total_score DESC
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql_query(stmt, conn)
    return df


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="signal_aggregator",
        description=(
            "Fusion des scores quantitatifs (stock_scores) avec le sentiment FinBERT "
            "(ticker_daily_features, sector_daily_features) → met à jour final_score dans stock_scores."
        ),
    )
    parser.add_argument(
        "--trade-date",
        type=str,
        default=None,
        help="Date de référence ISO (YYYY-MM-DD). Défaut : aujourd'hui.",
    )
    parser.add_argument(
        "--all-symbols",
        action="store_true",
        default=False,
        help="Traite tous les symboles de stock_scores (pas seulement les candidats).",
    )
    parser.add_argument(
        "--sentiment-weight",
        type=float,
        default=0.15,
        help="Poids du signal sentiment ticker [0,1]. Défaut 0.15.",
    )
    parser.add_argument(
        "--macro-weight",
        type=float,
        default=0.10,
        help="Poids du signal macro sectoriel [0,1]. Défaut 0.10.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=5,
        help="Fenêtre glissante en jours pour agréger le sentiment. Défaut 5.",
    )
    parser.add_argument(
        "--min-news-count",
        type=int,
        default=2,
        help="Nombre minimal d'articles pour activer le boost. Défaut 2.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Niveau de log. Défaut INFO.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée principal du script standalone."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Résolution de la date de trading
    if args.trade_date:
        ref_date = date.fromisoformat(args.trade_date)
    else:
        ref_date = date.today()

    LOGGER.info(
        "=== SentimentSignalAggregator standalone | trade_date=%s all_symbols=%s ===",
        ref_date, args.all_symbols,
    )

    # Validation des poids
    quant_weight = round(1.0 - args.sentiment_weight - args.macro_weight, 6)
    if quant_weight < 0:
        LOGGER.error(
            "sentiment_weight (%.2f) + macro_weight (%.2f) > 1.0 — impossible.",
            args.sentiment_weight, args.macro_weight,
        )
        return 1

    config = SentimentBoostConfig(
        sentiment_weight=args.sentiment_weight,
        macro_sector_weight=args.macro_weight,
        quant_weight=quant_weight,
        lookback_days=args.lookback_days,
        min_news_count=args.min_news_count,
    )

    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()

    # 1. Chargement des scores quantitatifs depuis stock_scores
    LOGGER.info("Chargement des scores depuis stock_scores…")
    scores_df = _load_scores_from_db(engine, args.all_symbols)

    if scores_df.empty:
        LOGGER.warning("Aucun symbole trouve dans stock_scores — arret.")
        return 0

    LOGGER.info("Symboles charges : %d", len(scores_df))

    # 2. Fusion quant + sentiment
    aggregator = SentimentSignalAggregator(engine, config)
    enriched = aggregator.merge(scores_df, trade_date=ref_date)

    # 3. Persistance dans stock_scores
    saved = aggregator.save_to_db(enriched)
    LOGGER.info(
        "=== Termine | %d symboles mis a jour dans stock_scores ===", saved
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
