"""
Script de diagnostic — Qualité des signaux walk-forward sentiment.

Usage :
    python scripts/diagnose_signal_quality.py

Analyse la qualité prédictive de chaque composante du score composite
(quant / sentiment / macro) et identifie les causes racines des mauvais
résultats walk-forward.
"""
from __future__ import annotations

import logging
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

# Ajouter la racine du projet au path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_sqlalchemy_engine

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Paramètres du diagnostic (alignés sur la commande walk-forward)
# ---------------------------------------------------------------------------
START_DATE = "2020-01-01"
END_DATE = "2026-06-21"
CAPITAL_PRESET_KEY = "capital_2001_5000"
HORIZONS = (5, 10, 20)
SELECTED_ONLY = True


def fetch_raw_dataset(engine, start_date: str, end_date: str, capital_preset_key: str, selected_only: bool) -> pd.DataFrame:
    """Charge les données brutes depuis stock_scores_history."""
    selection_clause = "AND h.selection_rank IS NOT NULL" if selected_only else ""

    query = text(f"""
        SELECT
            h.snapshot_date,
            h.symbol,
            h.sector,
            h.final_score,
            h.final_score_sentiment,
            h.final_score_walk_forward,
            h.sentiment_net_agg,
            h.sector_impact_agg,
            h.company_idio_score,
            h.macro_regime_score,
            h.company_idio_signal_norm,
            h.macro_regime_signal_norm,
            h.company_idio_component,
            h.macro_regime_component,
            h.quant_component,
            h.signal_active,
            h.selection_rank,
            h.capital_preset_key
        FROM stock_scores_history h
        WHERE h.snapshot_date BETWEEN :start_date AND :end_date
          AND h.capital_preset_key = :capital_preset_key
          {selection_clause}
        ORDER BY h.snapshot_date, h.symbol
    """)

    with engine.connect() as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params={
                "start_date": start_date,
                "end_date": end_date,
                "capital_preset_key": capital_preset_key,
            },
        )
    return df


def compute_forward_returns(df: pd.DataFrame, engine, horizons: tuple[int, ...]) -> pd.DataFrame:
    """Ajoute les colonnes forward_return_{h}d en joignant sur stock_bars_daily.

    Utilise la même stratégie de range-JOIN SQL que le code de production
    (SentimentWeightCalibrator._load_dataset_batch_sql) pour éviter le O(n²)
    en Python.
    """
    if df.empty:
        return df

    end_date_plus_buffer = pd.Timestamp(df["snapshot_date"].max()) + pd.Timedelta(days=max(horizons) * 3)
    symbols = sorted(df["symbol"].unique())
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])

    # Même approche que _load_dataset_batch_sql : range-JOIN SQL
    batch_size = 200
    all_frames: list[pd.DataFrame] = []

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        escaped = ", ".join([f"'{sym}'" for sym in batch])

        query = text(f"""
            SELECT
                h.snapshot_date,
                h.symbol,
                b.date AS bar_date,
                COALESCE(b.adj_close, b.close) AS close_price
            FROM stock_scores_history h
            JOIN stock_bars_daily b
              ON b.symbol = h.symbol
             AND b.date >= h.snapshot_date
             AND b.date <= :end_date_plus_buffer
            WHERE h.symbol IN ({escaped})
              AND h.snapshot_date BETWEEN :start_date AND :end_date
              AND h.capital_preset_key = :capital_preset_key
            ORDER BY h.snapshot_date, h.symbol, b.date
        """)

        with engine.connect() as conn:
            batch_df = pd.read_sql_query(
                query,
                conn,
                params={
                    "start_date": str(df["snapshot_date"].min().date()),
                    "end_date": str(df["snapshot_date"].max().date()),
                    "end_date_plus_buffer": str(end_date_plus_buffer.date()),
                    "capital_preset_key": CAPITAL_PRESET_KEY,
                },
            )

        if batch_df.empty:
            continue

        batch_df["snapshot_date"] = pd.to_datetime(batch_df["snapshot_date"])
        batch_df["bar_date"] = pd.to_datetime(batch_df["bar_date"])
        batch_df = batch_df.sort_values(["snapshot_date", "symbol", "bar_date"]).reset_index(drop=True)

        # Pour chaque (snapshot_date, symbol), prendre les horizons
        for h in horizons:
            col_name = f"forward_return_{h}d"

            def _compute_horizon(grp: pd.DataFrame) -> float:
                if len(grp) <= h:
                    return np.nan
                entry_price = float(grp.iloc[0]["close_price"])
                exit_price = float(grp.iloc[h]["close_price"])
                if entry_price <= 0:
                    return np.nan
                return (exit_price / entry_price) - 1.0

            fwd = batch_df.groupby(["snapshot_date", "symbol"], sort=False).apply(
                _compute_horizon, include_groups=False
            )
            if col_name not in batch_df.columns:
                batch_df[col_name] = np.nan
            # Fusionner les forward returns dans le batch
            fwd_df = fwd.reset_index()
            fwd_df.columns = ["snapshot_date", "symbol", col_name]
            batch_df = batch_df.drop(columns=[col_name], errors="ignore")
            batch_df = batch_df.merge(fwd_df, on=["snapshot_date", "symbol"], how="left")

        # Garder seulement les colonnes nécessaires
        keep_cols = ["snapshot_date", "symbol"] + [f"forward_return_{h}d" for h in horizons]
        batch_df = batch_df[keep_cols].drop_duplicates(subset=["snapshot_date", "symbol"])
        all_frames.append(batch_df)

        if (i // batch_size + 1) % 5 == 0:
            LOGGER.info("Forward returns : %d/%d symboles traités...", min(i + batch_size, len(symbols)), len(symbols))

    if not all_frames:
        LOGGER.warning("Aucune donnée de prix forward trouvée.")
        for h in horizons:
            df[f"forward_return_{h}d"] = np.nan
        return df

    fwd_all = pd.concat(all_frames, ignore_index=True)
    # Fusionner avec le DataFrame original
    df = df.merge(fwd_all, on=["snapshot_date", "symbol"], how="left")
    return df


def analyze_distribution(series: pd.Series, name: str) -> dict:
    """Analyse statistique d'une colonne."""
    valid = series.dropna()
    if len(valid) == 0:
        return {"name": name, "count": len(series), "valid": 0, "pct_nan": 100.0, "error": "all_nan"}

    # Compter les valeurs exactes à 0.0 et 0.5 (valeurs sentinelles/default)
    n_default_zero = int((valid == 0.0).sum())
    n_default_half = int((np.abs(valid - 0.5) < 1e-9).sum())
    n_unique = valid.nunique()

    return {
        "name": name,
        "count": int(len(series)),
        "valid": int(len(valid)),
        "pct_nan": round(100.0 * (len(series) - len(valid)) / max(len(series), 1), 2),
        "mean": round(float(valid.mean()), 6),
        "std": round(float(valid.std()), 6),
        "min": round(float(valid.min()), 6),
        "p05": round(float(valid.quantile(0.05)), 6),
        "p25": round(float(valid.quantile(0.25)), 6),
        "p50": round(float(valid.quantile(0.50)), 6),
        "p75": round(float(valid.quantile(0.75)), 6),
        "p95": round(float(valid.quantile(0.95)), 6),
        "max": round(float(valid.max()), 6),
        "n_unique": n_unique,
        "pct_zero": round(100.0 * n_default_zero / max(len(valid), 1), 2),
        "pct_half": round(100.0 * n_default_half / max(len(valid), 1), 2),
        "pct_nonzero_unique": round(100.0 * max(n_unique - (1 if n_default_zero > 0 else 0), 0) / max(len(valid), 1), 2),
    }


def compute_daily_rank_ic(df: pd.DataFrame, score_col: str, return_col: str) -> dict:
    """Calcule le Rank IC quotidien (Spearman) entre un score et un forward return."""
    ic_values = []
    for _, daily in df.groupby("snapshot_date"):
        valid = daily[[score_col, return_col]].dropna()
        if len(valid) < 5:
            continue
        # Utiliser la corrélation de rang (Spearman)
        score_rank = valid[score_col].rank(method="average")
        return_rank = valid[return_col].rank(method="average")
        if score_rank.nunique() <= 1 or return_rank.nunique() <= 1:
            continue
        ic = score_rank.corr(return_rank)
        if pd.notna(ic):
            ic_values.append(float(ic))

    if not ic_values:
        return {"mean_ic": 0.0, "std_ic": 0.0, "n_days": 0, "pct_positive": 0.0, "t_stat": 0.0}

    arr = np.array(ic_values)
    return {
        "mean_ic": round(float(np.mean(arr)), 6),
        "std_ic": round(float(np.std(arr, ddof=1)), 6),
        "n_days": len(ic_values),
        "pct_positive": round(100.0 * float((arr > 0).mean()), 2),
        "t_stat": round(float(np.mean(arr) / (np.std(arr, ddof=1) / np.sqrt(len(arr)))) if np.std(arr, ddof=1) > 0 else 0.0, 4),
    }


def compute_top_spread(df: pd.DataFrame, score_col: str, return_col: str, top_n: int = 50) -> dict:
    """Calcule le spread de rendement entre le top-N et l'univers."""
    spreads = []
    for _, daily in df.groupby("snapshot_date"):
        valid = daily[[score_col, return_col]].dropna()
        if len(valid) < top_n + 1:
            continue
        n = min(top_n, len(valid))
        top = valid.nlargest(n, score_col)
        universe_mean = float(valid[return_col].mean())
        top_mean = float(top[return_col].mean())
        spreads.append(top_mean - universe_mean)

    if not spreads:
        return {"mean_spread": 0.0, "n_days": 0, "pct_positive": 0.0}

    arr = np.array(spreads)
    return {
        "mean_spread": round(float(np.mean(arr)), 6),
        "std_spread": round(float(np.std(arr, ddof=1)), 6),
        "n_days": len(spreads),
        "pct_positive": round(100.0 * float((arr > 0).mean()), 2),
        "annualized_spread_bps": round(float(np.mean(arr)) * 252 * 10000, 1),
    }


def normalize_like_production(series: pd.Series) -> pd.Series:
    """Réplique _normalize_signed_signal de SentimentSignalAggregator."""
    numeric = pd.to_numeric(series, errors="coerce").astype(float)
    numeric = numeric.where(np.isfinite(numeric), np.nan)
    clipped = numeric.clip(-1.0, 1.0).fillna(0.0)
    return ((clipped + 1.0) / 2.0).astype(float)


def main() -> None:
    configure_logging()
    engine = get_sqlalchemy_engine()

    print("=" * 80)
    print("🔬 DIAGNOSTIC QUALITÉ DES SIGNAUX — Walk-Forward Sentiment")
    print("=" * 80)
    print(f"Période         : {START_DATE} → {END_DATE}")
    print(f"Capital preset  : {CAPITAL_PRESET_KEY}")
    print(f"Horizons        : {HORIZONS}")
    print(f"Sélections only : {SELECTED_ONLY}")
    print()

    # -----------------------------------------------------------------------
    # 1. Chargement des données
    # -----------------------------------------------------------------------
    print("📥 [1/6] Chargement des données brutes depuis stock_scores_history...")
    raw = fetch_raw_dataset(engine, START_DATE, END_DATE, CAPITAL_PRESET_KEY, SELECTED_ONLY)

    if raw.empty:
        print("❌ Aucune donnée trouvée. Vérifiez les paramètres.")
        return

    n_rows = len(raw)
    n_dates = raw["snapshot_date"].nunique()
    n_symbols = raw["symbol"].nunique()
    raw["snapshot_date"] = pd.to_datetime(raw["snapshot_date"])
    min_date = raw["snapshot_date"].min()
    max_date = raw["snapshot_date"].max()
    print(f"   → {n_rows:,} lignes, {n_dates} dates uniques, {n_symbols} symboles uniques")
    print(f"   → Période effective : {min_date.date()} → {max_date.date()}")
    print()

    # -----------------------------------------------------------------------
    # 2. Analyse des distributions des composantes brutes
    # -----------------------------------------------------------------------
    print("📊 [2/6] Distribution des composantes BRUTES (avant normalisation)")
    print("-" * 80)

    raw_columns = [
        ("final_score", "Score quant (final_score)"),
        ("sentiment_net_agg", "Sentiment brut (sentiment_net_agg)"),
        ("sector_impact_agg", "Macro brut (sector_impact_agg)"),
        ("company_idio_score", "Company idio score"),
        ("macro_regime_score", "Macro regime score"),
        ("final_score_sentiment", "Score final fusionné (final_score_sentiment)"),
        ("signal_active", "Signal actif (signal_active)"),
    ]

    for col, label in raw_columns:
        if col not in raw.columns:
            print(f"  ⚠️  Colonne '{col}' ABSENTE de la table")
            continue
        stats = analyze_distribution(raw[col], col)
        print(f"  📌 {label}")
        print(f"     N={stats['count']:,}  NaN={stats['pct_nan']}%  unique={stats['n_unique']}  "
              f"zéro={stats['pct_zero']}%  moitié={stats['pct_half']}%")
        print(f"     mean={stats['mean']:.4f}  std={stats['std']:.4f}  "
              f"p50={stats['p50']:.4f}  [p05={stats['p05']:.4f}, p95={stats['p95']:.4f}]")
        if stats.get("pct_nonzero_unique", 0) < 5:
            print(f"     ⚠️  SEULEMENT {stats['pct_nonzero_unique']}% de valeurs non-zéro distinctes → signal quasi-inexistant !")
        print()

    # -----------------------------------------------------------------------
    # 3. Analyse après normalisation (comme en production)
    # -----------------------------------------------------------------------
    print("📊 [3/6] Distribution après normalisation (_normalize_signed_signal → [0,1])")
    print("-" * 80)

    raw["sentiment_norm"] = normalize_like_production(raw["sentiment_net_agg"])
    raw["macro_norm"] = normalize_like_production(raw["sector_impact_agg"])

    for col, label in [
        ("sentiment_norm", "Sentiment normalisé → [0,1]"),
        ("macro_norm", "Macro normalisé → [0,1]"),
    ]:
        stats = analyze_distribution(raw[col], col)
        print(f"  📌 {label}")
        print(f"     mean={stats['mean']:.4f}  std={stats['std']:.4f}  "
              f"p50={stats['p50']:.4f}  [p05={stats['p05']:.4f}, p95={stats['p95']:.4f}]")
        if stats["std"] < 0.05:
            print(f"     ⚠️  Écart-type < 0.05 → signal APLATI, quasi inutilisable !")
        print()

    # -----------------------------------------------------------------------
    # 4. Forward returns
    # -----------------------------------------------------------------------
    print("📥 [4/6] Calcul des forward returns (jointure stock_bars_daily)...")
    raw_with_fwd = compute_forward_returns(raw, engine, HORIZONS)

    for h in HORIZONS:
        col = f"forward_return_{h}d"
        if col in raw_with_fwd.columns:
            valid = raw_with_fwd[col].dropna()
            if len(valid) > 0:
                print(f"   forward_return_{h}d : {len(valid):,} valides, "
                      f"mean={valid.mean():.6f}, std={valid.std():.6f}, "
                      f"médiane={valid.median():.6f}")
            else:
                print(f"   forward_return_{h}d : AUCUNE valeur valide !")
    print()

    # -----------------------------------------------------------------------
    # 5. Rank IC par composante
    # -----------------------------------------------------------------------
    print("📈 [5/6] Rank IC (Spearman) quotidien par composante vs forward returns")
    print("-" * 80)

    # Scores à tester
    test_scores = {
        "quant (final_score)": "final_score",
        "sentiment normalisé": "sentiment_norm",
        "macro normalisé": "macro_norm",
    }

    # Ajouter les scores composites avec les poids du scénario gagnant
    # sent_0.25_macro_0.15_quant_0.60
    w_quant, w_sent, w_macro = 0.60, 0.25, 0.15
    raw["composite_winner"] = (
        w_quant * raw["final_score"].fillna(0.0).clip(0.0, 1.0)
        + w_sent * raw["sentiment_norm"]
        + w_macro * raw["macro_norm"]
    ).clip(0.0, 1.0)
    test_scores["composite gagnant (0.60/0.25/0.15)"] = "composite_winner"

    # Ajouter final_score_sentiment si disponible
    if "final_score_sentiment" in raw.columns:
        test_scores["final_score_sentiment (prod)"] = "final_score_sentiment"

    for h in HORIZONS:
        return_col = f"forward_return_{h}d"
        if return_col not in raw_with_fwd.columns:
            continue

        print(f"  🎯 Horizon {h}j :")
        print(f"     {'Composante':<40s} {'mean_IC':>10s} {'t-stat':>8s} {'IC>0%':>8s} {'spread_bps/an':>14s}")
        print(f"     {'-'*40} {'-'*10} {'-'*8} {'-'*8} {'-'*14}")

        for label, score_col in test_scores.items():
            if score_col not in raw_with_fwd.columns:
                continue

            ic_stats = compute_daily_rank_ic(raw_with_fwd, score_col, return_col)
            spread_stats = compute_top_spread(raw_with_fwd, score_col, return_col, top_n=50)

            print(f"     {label:<40s} {ic_stats['mean_ic']:>10.4f} {ic_stats['t_stat']:>8.2f} "
                  f"{ic_stats['pct_positive']:>7.1f}% {spread_stats['annualized_spread_bps']:>13.1f}")

        print()

    # -----------------------------------------------------------------------
    # 6. Diagnostic des scénarios de calibration
    # -----------------------------------------------------------------------
    print("📊 [6/6] Simulation des scénarios de calibration (overall_score)")
    print("-" * 80)

    # Recréer les scénarios comme dans default_scenarios()
    scenarios = []
    for sw in (0.05, 0.10, 0.15, 0.20, 0.25):
        for mw in (0.00, 0.05, 0.10, 0.15):
            qw = round(1.0 - sw - mw, 6)
            if qw < 0.50:
                continue
            scenarios.append((sw, mw, qw))

    # Préparer les colonnes de base
    raw_with_fwd["quant_clipped"] = raw_with_fwd["final_score"].fillna(0.0).clip(0.0, 1.0)

    results = []
    for sw, mw, qw in scenarios:
        sent_col = raw_with_fwd["sentiment_norm"]
        macro_col = raw_with_fwd["macro_norm"]
        quant_col = raw_with_fwd["quant_clipped"]

        composite = (qw * quant_col + sw * sent_col + mw * macro_col).clip(0.0, 1.0)
        raw_with_fwd["_tmp_composite"] = composite

        per_horizon_scores = []
        for h in HORIZONS:
            return_col = f"forward_return_{h}d"
            if return_col not in raw_with_fwd.columns:
                continue
            ic_stats = compute_daily_rank_ic(raw_with_fwd, "_tmp_composite", return_col)
            spread_stats = compute_top_spread(raw_with_fwd, "_tmp_composite", return_col, top_n=50)
            horizon_score = 0.65 * ic_stats["mean_ic"] + 0.35 * spread_stats["mean_spread"]
            per_horizon_scores.append(horizon_score)

        overall = sum(per_horizon_scores) / len(per_horizon_scores) if per_horizon_scores else 0.0
        scenario_name = f"sent_{sw:.2f}_macro_{mw:.2f}_quant_{qw:.2f}"
        results.append({
            "scenario": scenario_name,
            "sent_w": sw,
            "macro_w": mw,
            "quant_w": qw,
            "overall_score": round(overall, 6),
        })

    results_df = pd.DataFrame(results).sort_values("overall_score", ascending=False)

    print(f"  {'Scénario':<40s} {'sent_w':>8s} {'macro_w':>8s} {'quant_w':>8s} {'overall_score':>14s}")
    print(f"  {'-'*40} {'-'*8} {'-'*8} {'-'*8} {'-'*14}")
    for _, row in results_df.head(10).iterrows():
        marker = " ← GAGNANT" if row["scenario"] == "sent_0.25_macro_0.15_quant_0.60" else ""
        print(f"  {row['scenario']:<40s} {row['sent_w']:>8.2f} {row['macro_w']:>8.2f} "
              f"{row['quant_w']:>8.2f} {row['overall_score']:>14.6f}{marker}")

    print()
    score_range = results_df["overall_score"].max() - results_df["overall_score"].min()
    if score_range < 0.001:
        print("  ⚠️  L'ÉCART entre le meilleur et le pire scénario est < 0.001")
        print("  → Le paysage d'optimisation est PLAT : tous les scénarios sont équivalents.")
        print("  → Le walk-forward sélectionne du BRUIT, pas un vrai optimum.")
    else:
        print(f"  ✅ Écart meilleur-pire = {score_range:.6f} (acceptable)")

    print()
    print("=" * 80)
    print("🏁 SYNTHÈSE DU DIAGNOSTIC")
    print("=" * 80)

    # Résumé automatique
    issues = []

    # Vérifier la qualité du score quant
    quant_ic = compute_daily_rank_ic(raw_with_fwd, "final_score", f"forward_return_{HORIZONS[1]}d")
    if abs(quant_ic["mean_ic"]) < 0.01:
        issues.append(f"❌ Score quant (final_score) : Rank IC = {quant_ic['mean_ic']:.4f} → AUCUN pouvoir prédictif")
    elif abs(quant_ic["mean_ic"]) < 0.03:
        issues.append(f"⚠️  Score quant (final_score) : Rank IC = {quant_ic['mean_ic']:.4f} → très faible")

    # Vérifier le sentiment
    sent_stats = analyze_distribution(raw["sentiment_norm"], "sentiment_norm")
    if sent_stats.get("std", 0) < 0.05:
        issues.append(f"❌ Sentiment normalisé : std={sent_stats['std']:.4f} → signal APLATI (quasi constant)")
    if sent_stats.get("pct_zero", 0) > 50:
        issues.append(f"⚠️  Sentiment brut : {sent_stats['pct_zero']}% de valeurs à 0.0 (valeur par défaut)")

    # Vérifier le macro
    macro_stats = analyze_distribution(raw["macro_norm"], "macro_norm")
    if macro_stats.get("std", 0) < 0.05:
        issues.append(f"❌ Macro normalisé : std={macro_stats['std']:.4f} → signal APLATI")
    if macro_stats.get("pct_zero", 0) > 50:
        issues.append(f"⚠️  Macro brut : {macro_stats['pct_zero']}% de valeurs à 0.0 (valeur par défaut)")

    # Vérifier final_score_sentiment
    if "final_score_sentiment" in raw.columns:
        fss_stats = analyze_distribution(raw["final_score_sentiment"], "final_score_sentiment")
        fss_pct_nan = fss_stats.get("pct_nan", 100)
        if fss_pct_nan > 80:
            issues.append(f"⚠️  final_score_sentiment : {fss_pct_nan}% de NaN → la fusion ternary n'est PAS exécutée en production")

    # Vérifier signal_active
    if "signal_active" in raw.columns:
        active_pct = 100.0 * raw["signal_active"].fillna(0).astype(float).mean()
        if active_pct < 10:
            issues.append(f"⚠️  signal_active : seulement {active_pct:.1f}% des lignes ont signal_active=1")

    if issues:
        print()
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n  ✅ Aucun problème majeur détecté automatiquement.")

    print()
    print("📋 Recommandations :")
    print("  1. Si les IC sont < 0.01 → le système de scoring quant doit être revu")
    print("  2. Si sentiment/macro sont aplatis → vérifier le pipeline sentiment en production")
    print("  3. Si final_score_sentiment est NaN à >80% → la fusion n'est pas active,")
    print("     le walk-forward optimise des poids sur des signaux qui n'existent pas en réel")
    print("  4. Si le paysage est plat → supprimer la contrainte quant>=0.50 ne changera rien,")
    print("     il faut d'abord réparer les signaux sous-jacents")
    print()

    # Sauvegarde CSV pour analyse complémentaire
    output_dir = Path("artifacts/signal_diagnostics")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Sauvegarder les stats
    results_df.to_csv(output_dir / f"scenario_scores_{timestamp}.csv", index=False)
    print(f"📁 Scores des scénarios sauvegardés : {output_dir / f'scenario_scores_{timestamp}.csv'}")


if __name__ == "__main__":
    main()
