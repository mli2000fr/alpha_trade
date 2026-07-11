#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validate_score_predictiveness.py — Vérification automatique de la prédictivité des scores.

Ce script répond à la question : « Le score trie-t-il correctement les gagnants
des perdants ? »

Deux sources de scores sont supportées :

  --source screener  →  final_score depuis stock_scores_history (score technique :
                        trend + VCP + RSI). C'est le score utilisé par le selector
                        pour classer les candidats. Validation possible SANS avoir
                        entraîné de modèle ML.

  --source ml        →  predicted_proba depuis model_predictions (prédiction du
                        modèle LSTM / CatBoost / LightGBM / GlobalModel). Validation
                        possible APRÈS avoir entraîné un modèle ET généré les
                        prédictions (inférence).

Méthode :
  1. Charge les scores depuis la source choisie (période configurable).
  2. Calcule le forward return à J+horizon depuis ``stock_bars_daily``.
  3. Merge scores ↔ forward returns par (symbol, date).
  4. Appelle ``bucket_analysis()`` (modelFactory/evaluation.py) pour découper
     les scores en N buckets et mesurer le hit_rate par bucket.
  5. Vérifie la monotonicité : le hit_rate doit CROÎTRE avec le score.
  6. Affiche un résumé + analyses annuelles/mensuelles + verdict PASS / FAIL.

Usage :
  # Valider le score technique du screener (pas besoin d'entraînement ML)
  python validate_score_predictiveness.py --source screener

  # Valider les prédictions ML (après entraînement + prédiction)
  python validate_score_predictiveness.py --source ml

  # Période personnalisée
  python validate_score_predictiveness.py --source ml --start 2024-01-01 --end 2025-12-31

  # Colonne spécifique (pour --source screener)
  python validate_score_predictiveness.py --source screener --score-col final_score_sentiment

  # Horizon 10 jours au lieu de 5
  python validate_score_predictiveness.py --source ml --horizon 10

    # Inclure tous les scores (pas seulement les sélections classées)
    python validate_score_predictiveness.py --source screener --all-scores

Critères de succès :
  - monotonic_hit_rate      = True   (le WR monte avec le score)
  - top_minus_bottom_hit_rate > 10%  (écart significatif entre meilleur et pire bucket)
  - top_bucket_hit_rate     > 50%   (le meilleur bucket bat le hasard)
  - dispersion P10-P90      > 0.15  (le score discrimine vraiment)
  - avg_future_return croissant avec les buckets

Explications :
  - Un bon modèle a des scores qui TRIENT les opportunités : bucket 1 (scores bas)
    a un hit_rate faible, bucket 5 (scores hauts) a un hit_rate élevé.
  - Si le hit_rate est PLAT ou INVERSE (haut score = bas hit_rate), le score
    n'est pas prédictif → soit les features sont mauvaises, soit le modèle
    est mal calibré, soit le marché a changé de régime.
  - Le forward return moyen doit aussi croître : non seulement on gagne plus
    souvent, mais on gagne PLUS quand on gagne.

Auteur : Généré automatiquement — session 2026-07-11
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine
from modelFactory.evaluation import bucket_analysis


# ---------------------------------------------------------------------------
# Configuration par défaut
# ---------------------------------------------------------------------------
DEFAULT_START = "2024-01-01"
DEFAULT_END = "2025-12-31"
DEFAULT_HORIZON_DAYS = 5
DEFAULT_SCORE_COL = "final_score"
DEFAULT_SOURCE = "screener"  # screener | ml
DEFAULT_N_BUCKETS = 5
DEFAULT_MIN_OBS = 200  # minimum d'observations pour considérer l'analyse valide

# ---------------------------------------------------------------------------
# Couleurs terminal (Windows ≥10 compatibles)
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_scores(
    engine,
    start_date: str,
    end_date: str,
    score_col: str,
    selected_only: bool = True,
) -> pd.DataFrame:
    """Charge les scores PIT depuis ``stock_scores_history``.

    Args:
        engine: Connexion SQLAlchemy.
        start_date: Date début (YYYY-MM-DD).
        end_date: Date fin (YYYY-MM-DD).
        score_col: Colonne de score à analyser.
            Valeurs possibles : final_score, final_score_sentiment,
            final_score_walk_forward, raw_final_score.
        selected_only: Si True, ne garde que les lignes dont le rang de
            sélection est disponible.

    Returns:
        DataFrame avec colonnes [snapshot_date, symbol, score].
    """
    valid_cols = {
        "final_score", "final_score_sentiment",
        "final_score_walk_forward", "raw_final_score",
    }
    if score_col not in valid_cols:
        print(
            f"{YELLOW}⚠ Colonne '{score_col}' non standard. "
            f"Colonnes connues : {sorted(valid_cols)}{RESET}"
        )

    selection_clause = "AND selection_rank IS NOT NULL" if selected_only else ""
    query = text(
        f"""
        SELECT snapshot_date, symbol, {score_col} AS score
        FROM stock_scores_history
        WHERE snapshot_date BETWEEN :start_date AND :end_date
          {selection_clause}
          AND {score_col} IS NOT NULL
        ORDER BY snapshot_date ASC, symbol ASC
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql_query(
            query, conn,
            params={"start_date": start_date, "end_date": end_date},
        )
    if df.empty:
        return df

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df = df.dropna(subset=["symbol", "snapshot_date", "score"])
    df = df.drop_duplicates(subset=["symbol", "snapshot_date"])
    df = df.sort_values(["symbol", "snapshot_date"]).reset_index(drop=True)
    return df


def load_ml_predictions(
    engine,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Charge les prédictions ML depuis ``model_predictions``.

    La table model_predictions contient les prédictions générées après
    l'entraînement d'un modèle (LSTM, CatBoost, LightGBM, GlobalModel).
    On utilise ``predicted_proba`` comme score (probabilité que le forward
    return à horizon soit positif).

    Pour le mode ternaire (long/flat/short), on utilise aussi ``proba_long``
    et ``proba_short`` si disponibles, en créant un score composite :
        score = proba_long - proba_short  (score directionnel)

    Args:
        engine: Connexion SQLAlchemy.
        start_date: Date début (YYYY-MM-DD).
        end_date: Date fin (YYYY-MM-DD).

    Returns:
        DataFrame avec colonnes [snapshot_date, symbol, score, selected_model].
    """
    # Détecte si les colonnes ternaires existent
    with engine.connect() as conn:
        cols = pd.read_sql_query(
            "SELECT * FROM model_predictions LIMIT 0", conn
        ).columns.tolist()

    has_ternary = "proba_long" in cols and "proba_short" in cols

    if has_ternary:
        score_expr = """
            CASE
                WHEN proba_long IS NOT NULL AND proba_short IS NOT NULL
                THEN proba_long - proba_short
                ELSE predicted_proba
            END AS score
        """
    else:
        score_expr = "predicted_proba AS score"

    query = text(
        f"""
        SELECT prediction_date AS snapshot_date, symbol,
               {score_expr},
               COALESCE(selected_model, 'unknown') AS selected_model
        FROM model_predictions
        WHERE prediction_date BETWEEN :start_date AND :end_date
          AND predicted_proba IS NOT NULL
        ORDER BY prediction_date ASC, symbol ASC
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql_query(
            query, conn,
            params={"start_date": start_date, "end_date": end_date},
        )
    if df.empty:
        return df

    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df = df.dropna(subset=["symbol", "snapshot_date", "score"])
    df = df.drop_duplicates(subset=["symbol", "snapshot_date"])
    df = df.sort_values(["symbol", "snapshot_date"]).reset_index(drop=True)
    return df


def load_forward_returns(
    engine,
    start_date: str,
    end_date: str,
    horizon_days: int = 5,
) -> pd.DataFrame:
    """Calcule les forward returns à J+horizon depuis ``stock_bars_daily``.

    Le forward return est défini comme :
        forward_return = (close_{t+horizon} / close_t) - 1

    Args:
        engine: Connexion SQLAlchemy.
        start_date: Date début.
        end_date: Date fin.
        horizon_days: Jours de projection (défaut 5 = 1 semaine).

    Returns:
        DataFrame avec colonnes [symbol, bar_date, forward_return].
    """
    # On étend la période pour avoir les prix futurs
    end_date_plus = (
        pd.Timestamp(end_date) + pd.Timedelta(days=max(horizon_days * 4, 30))
    ).strftime("%Y-%m-%d")

    query = text(
        """
        SELECT symbol, date AS bar_date, close AS close_price
        FROM stock_bars_daily
        WHERE date BETWEEN :start_date AND :end_date_plus
        ORDER BY symbol ASC, date ASC
        """
    )
    with engine.connect() as conn:
        bars = pd.read_sql_query(
            query, conn,
            params={
                "start_date": start_date,
                "end_date_plus": end_date_plus,
            },
        )

    if bars.empty:
        return bars

    bars["bar_date"] = pd.to_datetime(bars["bar_date"])
    bars = bars.sort_values(["symbol", "bar_date"]).reset_index(drop=True)

    # Forward return par symbole
    bars["future_close"] = bars.groupby("symbol")["close_price"].shift(
        -int(horizon_days)
    )
    bars["forward_return"] = (
        bars["future_close"] / bars["close_price"]
    ) - 1.0

    bars = bars[["symbol", "bar_date", "forward_return"]].dropna(
        subset=["forward_return"]
    )
    bars = bars[bars["forward_return"].apply(np.isfinite)]
    return bars


def merge_scores_with_returns(
    scores_df: pd.DataFrame,
    returns_df: pd.DataFrame,
) -> pd.DataFrame:
    """Fusionne les scores avec les forward returns par (symbol, date).

    Utilise merge_asof pour associer chaque score au forward return
    calculé à la même date (tolérance : même jour).
    """
    if scores_df.empty or returns_df.empty:
        return pd.DataFrame()

    # merge_asof nécessite que les deux soient triés par la clé de merge
    scores_df = scores_df.sort_values("snapshot_date").reset_index(drop=True)
    returns_df = returns_df.sort_values("bar_date").reset_index(drop=True)

    # pandas 2.3.3 + Python 3.14 : merge_asof(by=) peut être cassé.
    # Contournement : boucle par symbole.
    parts: list[pd.DataFrame] = []
    for sym, grp in scores_df.groupby("symbol", sort=False):
        grp = grp.sort_values("snapshot_date")
        ret_sym = returns_df[returns_df["symbol"] == sym]
        if ret_sym.empty:
            continue
        ret_sym = ret_sym.sort_values("bar_date")
        merged = pd.merge_asof(
            grp.rename(columns={"snapshot_date": "date"}),
            ret_sym.rename(columns={"bar_date": "date"}),
            on="date",
            direction="nearest",
            tolerance=pd.Timedelta(days=2),
        )
        parts.append(merged)

    if not parts:
        return pd.DataFrame()

    result = pd.concat(parts, ignore_index=True)
    result = result.dropna(subset=["score", "forward_return"])
    return result


def analyze_by_year(df: pd.DataFrame) -> None:
    """Analyse annuelle : hit_rate par bucket pour chaque année."""
    if df.empty:
        return

    df["year"] = pd.to_datetime(df["date"]).dt.year
    print(f"\n{BOLD}📅 Analyse par année{RESET}")
    print(f"   {'Année':<6} {'Obs':>6} {'Hit Rate':>9} {'Score moy':>10} {'Ret moy':>9}")
    print(f"   {'-'*6} {'-'*6} {'-'*9} {'-'*10} {'-'*9}")

    for year in sorted(df["year"].dropna().unique()):
        year_df = df[df["year"] == year]
        n = len(year_df)
        if n < DEFAULT_MIN_OBS:
            print(f"   {int(year):<6} {n:>6}  (trop peu d'observations, min {DEFAULT_MIN_OBS})")
            continue
        labels = (year_df["forward_return"] > 0).astype(int).values
        hits = labels.sum()
        hr = (hits / n) * 100
        avg_score = year_df["score"].mean()
        avg_ret = year_df["forward_return"].mean() * 100
        print(
            f"   {int(year):<6} {n:>6} {hr:>8.1f}% "
            f"{avg_score:>10.4f} {avg_ret:>8.2f}%"
        )


def analyze_by_month(df: pd.DataFrame) -> None:
    """Analyse mensuelle rapide."""
    if df.empty:
        return

    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    monthly = (
        df.groupby("month")
        .agg(
            obs=("forward_return", "count"),
            hit_rate=("forward_return", lambda x: (x > 0).mean() * 100),
            avg_score=("score", "mean"),
            avg_ret=("forward_return", lambda x: x.mean() * 100),
        )
        .reset_index()
    )

    # Affiche les 5 pires et 5 meilleurs mois
    print(f"\n{BOLD}📆 Top 5 / Flop 5 mois (hit_rate){RESET}")
    monthly_sorted = monthly.sort_values("hit_rate")
    print(f"   -- Pires mois --")
    for _, row in monthly_sorted.head(5).iterrows():
        print(
            f"   {str(row['month']):<9} {int(row['obs']):>5} obs  "
            f"HR={row['hit_rate']:5.1f}%  score={row['avg_score']:.4f}  "
            f"ret={row['avg_ret']:+.2f}%"
        )
    print(f"   -- Meilleurs mois --")
    for _, row in monthly_sorted.tail(5).iterrows():
        print(
            f"   {str(row['month']):<9} {int(row['obs']):>5} obs  "
            f"HR={row['hit_rate']:5.1f}%  score={row['avg_score']:.4f}  "
            f"ret={row['avg_ret']:+.2f}%"
        )


def score_distribution_analysis(df: pd.DataFrame) -> None:
    """Analyse la distribution des scores : est-ce que le modèle discrimine ?"""
    if df.empty:
        return

    print(f"\n{BOLD}📊 Distribution des scores{RESET}")
    scores = df["score"].dropna()
    print(f"   Mean   : {scores.mean():.4f}")
    print(f"   Median : {scores.median():.4f}")
    print(f"   Std    : {scores.std():.4f}")
    print(f"   Min    : {scores.min():.4f}")
    print(f"   Max    : {scores.max():.4f}")

    # Vérifie si les scores sont tous concentrés dans une bande étroite
    p10 = scores.quantile(0.10)
    p90 = scores.quantile(0.90)
    spread = p90 - p10
    print(f"   P10-P90: {spread:.4f}", end="")
    if spread < 0.15:
        print(
            f"  {RED}⚠ TRÈS FAIBLE — le modèle ne discrimine pas, "
            f"tous les scores sont similaires{RESET}"
        )
    elif spread < 0.30:
        print(
            f"  {YELLOW}⚠ Faible — le modèle discrimine peu{RESET}"
        )
    else:
        print(f"  {GREEN}✅ Bonne discrimination{RESET}")


def print_verdict(result: dict, df: pd.DataFrame, *, source: str = "screener") -> int:
    """Affiche le verdict final et retourne le code de sortie (0 = OK, 1 = FAIL).

    Les messages sont adaptés selon la source :
    - screener → le score technique du selector n'est pas prédictif
    - ml → le modèle ML n'est pas prédictif
    """
    checks = []

    # Check 1 : monotonicité
    if result["monotonic_hit_rate"]:
        checks.append((True, "Monotonicité du hit_rate", "✅"))
    else:
        checks.append((False, "Monotonicité du hit_rate", "❌"))

    # Check 2 : top vs bottom bucket
    spread = result.get("top_minus_bottom_bucket_hit_rate")
    if spread is not None and spread > 0.10:
        checks.append((True, f"Écart top/bottom hit_rate ({spread:.1%})", "✅"))
    elif spread is not None:
        checks.append((False, f"Écart top/bottom hit_rate ({spread:.1%} < 10%)", "❌"))
    else:
        checks.append((False, "Écart top/bottom hit_rate (N/A)", "❌"))

    # Check 3 : top bucket HR > 50%
    top_hr = result.get("top_bucket_hit_rate")
    if top_hr is not None and top_hr > 0.50:
        checks.append((True, f"Hit_rate bucket max ({top_hr:.1%})", "✅"))
    elif top_hr is not None:
        checks.append((False, f"Hit_rate bucket max ({top_hr:.1%} ≤ 50%)", "❌"))
    else:
        checks.append((False, "Hit_rate bucket max (N/A)", "❌"))

    # Check 4 : observations suffisantes
    n_obs = len(df)
    if n_obs >= DEFAULT_MIN_OBS:
        checks.append((True, f"Observations ({n_obs})", "✅"))
    else:
        checks.append(
            (False, f"Observations ({n_obs} < {DEFAULT_MIN_OBS})", "❌")
        )

    # Check 5 : dispersion des scores
    scores = df["score"].dropna()
    spread_score = scores.quantile(0.90) - scores.quantile(0.10)
    if spread_score >= 0.15:
        checks.append((True, f"Dispersion P10-P90 ({spread_score:.3f})", "✅"))
    else:
        checks.append(
            (False, f"Dispersion P10-P90 ({spread_score:.3f} < 0.15)", "❌")
        )

    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  VERDICT — {'Score screener' if source == 'screener' else 'Prédictions ML'}{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    all_pass = True
    for passed, label, icon in checks:
        color = GREEN if passed else RED
        print(f"  {color}{icon}{RESET} {label}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print(
            f"  {GREEN}{BOLD}✅ PASS — Le score est prédictif. "
            f"Tu peux l'utiliser en confiance.{RESET}"
        )
        return 0
    else:
        n_fail = sum(1 for p, _, _ in checks if not p)
        print(
            f"  {RED}{BOLD}❌ FAIL ({n_fail}/{len(checks)} checks) — "
            f"Le score n'est pas suffisamment prédictif.{RESET}"
        )
        print()
        if source == "ml":
            print(f"  {YELLOW}👉 Causes possibles (ML) :{RESET}")
            print(f"     1. Le modèle a été entraîné sur une période trop différente du test")
            print(f"     2. Les features utilisées ne capturent pas le régime de marché actuel")
            print(f"     3. La calibration Platt est mal réglée ou absente")
            print(f"     4. Les prédictions n'ont pas été générées pour la bonne période")
            print()
            print(f"  {YELLOW}👉 Actions recommandées :{RESET}")
            print(f"     - Réentraîner avec des données plus récentes (ex: 2015-2023)")
            print(f"     - Activer plus de features (macro VIX, sentiment, selector context)")
            print(f"     - Activer la calibration Platt (calibration.method = 'platt')")
            print(f"     - Activer le Global Model + features cross-sectionnelles")
        else:
            print(f"  {YELLOW}👉 Causes possibles (score screener) :{RESET}")
            print(f"     1. Les composantes du score (trend, VCP, RSI) ne sont pas pondérées optimalement")
            print(f"     2. Le marché 2024-2025 est trop différent du design du score")
            print(f"     3. Le score est conçu pour classer des candidats, pas prédire le retour")
            print(f"     4. La période de test est trop courte ou contient un choc")
            print()
            print(f"  {YELLOW}👉 Actions recommandées :{RESET}")
            print(f"     - Tester le score walk-forward (--score-col final_score_walk_forward)")
            print(f"     - Tester le score sentiment (--score-col final_score_sentiment)")
            print(f"     - Calibrer les poids trend/VCP/RSI (backtesting/weights_calibration.py)")
            print(f"     - Passer au score ML avec un modèle entraîné (--source ml)")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie la prédictivité des scores (screener ou ML)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Score technique du screener (pas besoin d'entraînement ML)
  python validate_score_predictiveness.py --source screener

  # Prédictions ML (après entraînement + inférence)
  python validate_score_predictiveness.py --source ml

  # Comparer les deux sources
  python validate_score_predictiveness.py --source screener --start 2021-01-01 --end 2023-12-31
  python validate_score_predictiveness.py --source ml --start 2021-01-01 --end 2023-12-31
        """,
    )
    parser.add_argument(
        "--source", type=str, default=DEFAULT_SOURCE,
        choices=["screener", "ml"],
        help=(
            "Source des scores à valider : "
            "'screener' = stock_scores_history (score technique, pas besoin d'entraînement ML), "
            "'ml' = model_predictions (prédictions du modèle, nécessite entraînement + inférence). "
            f"(défaut: {DEFAULT_SOURCE})"
        ),
    )
    parser.add_argument(
        "--start", type=str, default=DEFAULT_START,
        help=f"Date début (défaut: {DEFAULT_START})",
    )
    parser.add_argument(
        "--end", type=str, default=DEFAULT_END,
        help=f"Date fin (défaut: {DEFAULT_END})",
    )
    parser.add_argument(
        "--score-col", type=str, default=DEFAULT_SCORE_COL,
        help=(
            f"Colonne score à analyser (défaut: {DEFAULT_SCORE_COL}). "
            "Utilisé uniquement avec --source screener. "
            "Valeurs : final_score, final_score_sentiment, final_score_walk_forward, raw_final_score."
        ),
    )
    parser.add_argument(
        "--horizon", type=int, default=DEFAULT_HORIZON_DAYS,
        help=f"Horizon forward return en jours (défaut: {DEFAULT_HORIZON_DAYS})",
    )
    parser.add_argument(
        "--n-buckets", type=int, default=DEFAULT_N_BUCKETS,
        help=f"Nombre de buckets (défaut: {DEFAULT_N_BUCKETS})",
    )
    parser.add_argument(
        "--all-scores", action="store_true",
        help="Inclut TOUS les scores (pas seulement les sélections classées). Utilisé uniquement avec --source screener.",
    )
    parser.add_argument(
        "--no-annual", action="store_true",
        help="Désactive l'analyse par année",
    )
    parser.add_argument(
        "--no-monthly", action="store_true",
        help="Désactive l'analyse par mois",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Connexion DB
    # ------------------------------------------------------------------
    print(f"{BOLD}{CYAN}🔌 Connexion à la base de données...{RESET}")
    try:
        engine = get_sqlalchemy_engine()
    except Exception as exc:
        print(f"{RED}❌ Erreur de connexion : {exc}{RESET}")
        return 2

    # ------------------------------------------------------------------
    # 2. Chargement des scores (source = screener ou ml)
    # ------------------------------------------------------------------
    source_label = "Screener (stock_scores_history)" if args.source == "screener" else "ML (model_predictions)"
    print(
        f"{BOLD}{CYAN}📥 Chargement des scores — {source_label}{RESET}"
    )
    print(f"   Période : {args.start} → {args.end}")

    if args.source == "screener":
        scores_df = load_scores(
            engine,
            start_date=args.start,
            end_date=args.end,
            score_col=args.score_col,
            selected_only=not args.all_scores,
        )
        if scores_df.empty:
            print(
                f"{RED}❌ Aucun score trouvé dans stock_scores_history "
                f"pour {args.start} → {args.end}.{RESET}"
            )
            return 1
    else:
        scores_df = load_ml_predictions(
            engine,
            start_date=args.start,
            end_date=args.end,
        )
        if scores_df.empty:
            print(
                f"{RED}❌ Aucune prédiction trouvée dans model_predictions "
                f"pour {args.start} → {args.end}.{RESET}"
            )
            print(
                f"   {YELLOW}👉 Vérifie que le modèle a été entraîné ET que les "
                f"prédictions (inférence) ont été générées.{RESET}"
            )
            return 1

        # Affiche la répartition par type de modèle
        if "selected_model" in scores_df.columns:
            model_counts = scores_df["selected_model"].value_counts()
            print(f"   Modèles utilisés :")
            for model, count in model_counts.items():
                print(f"     {model}: {count:,} prédictions")

    print(f"   {len(scores_df):,} scores chargés ({scores_df['symbol'].nunique()} symboles)")

    # ------------------------------------------------------------------
    # 3. Forward returns
    # ------------------------------------------------------------------
    print(
        f"{BOLD}{CYAN}📥 Calcul des forward returns (horizon={args.horizon}j)...{RESET}"
    )
    returns_df = load_forward_returns(
        engine,
        start_date=args.start,
        end_date=args.end,
        horizon_days=args.horizon,
    )
    if returns_df.empty:
        print(f"{RED}❌ Aucun forward return calculé.{RESET}")
        return 1

    print(f"   {len(returns_df):,} forward returns calculés")

    # ------------------------------------------------------------------
    # 4. Merge
    # ------------------------------------------------------------------
    print(f"{BOLD}{CYAN}🔗 Fusion scores ↔ forward returns...{RESET}")
    merged = merge_scores_with_returns(scores_df, returns_df)
    if merged.empty:
        print(f"{RED}❌ Aucune correspondance score ↔ forward return.{RESET}")
        print(f"   Vérifie que les dates coïncident entre les deux sources.")
        return 1

    print(f"   {len(merged):,} observations fusionnées")
    print(f"   Score moyen : {merged['score'].mean():.4f}")
    print(f"   Hit rate global : {(merged['forward_return'] > 0).mean() * 100:.1f}%")
    print(f"   Forward return moyen : {merged['forward_return'].mean() * 100:+.2f}%")

    # ------------------------------------------------------------------
    # 5. Bucket analysis
    # ------------------------------------------------------------------
    print(
        f"\n{BOLD}{CYAN}🔬 Analyse par bucket ({args.n_buckets} buckets)...{RESET}"
    )
    result = bucket_analysis(
        probabilities=merged["score"].values,
        labels=(merged["forward_return"] > 0).astype(int).values,
        future_returns=merged["forward_return"].values,
        n_buckets=args.n_buckets,
    )

    base_rate = result.get("base_rate")
    if base_rate is not None:
        print(f"   Hit rate global (base rate) : {base_rate:.1%}")

    print(f"\n   {'Bucket':<8} {'Count':>6} {'Score min':>10} {'Score max':>10} {'Hit Rate':>10} {'Lift':>8} {'Ret moy':>9}")
    print(f"   {'-'*8} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*9}")
    for b in result.get("buckets", []):
        lift_str = f"{b.get('lift_vs_base_rate', 0):.2f}x" if b.get("lift_vs_base_rate") is not None else "N/A"
        ret_str = f"{b.get('avg_future_return', 0) * 100:+.2f}%" if b.get("avg_future_return") is not None else "N/A"
        print(
            f"   {b['bucket']:<8} {b['count']:>6} "
            f"{b['proba_min']:>10.4f} {b['proba_max']:>10.4f} "
            f"{b['hit_rate']:>9.1%} {lift_str:>8} {ret_str:>9}"
        )

    # ------------------------------------------------------------------
    # 6. Analyses complémentaires
    # ------------------------------------------------------------------
    score_distribution_analysis(merged)

    if not args.no_annual:
        analyze_by_year(merged)

    if not args.no_monthly:
        analyze_by_month(merged)

    # ------------------------------------------------------------------
    # 7. Verdict
    # ------------------------------------------------------------------
    return print_verdict(result, merged, source=args.source)


if __name__ == "__main__":
    sys.exit(main())
