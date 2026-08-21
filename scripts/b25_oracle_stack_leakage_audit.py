"""Audit stacking leakage : provenance du global_rank_20 dans le dataset Oracle.

Question (retour utilisateur 2026-08-20) : le modèle Oracle Extreme (O1) utilise
`global_rank_20` (B25) comme feature. Chaque `global_rank(D)` doit être une
prédiction OOF/walk-forward produite par un B25 qui n'a jamais vu D ni son futur,
sinon c'est du stacking / in-sample prediction leakage.

Faits établis par audit du code + DB :
- Batch B25 = model-factory-20260811223551-ef2cd0, entraîné UNE FOIS sur
  2016-01-01 → 2025-12-31 (model_training_batch.training_end_date).
- Le ranking B25 a 2 sources possibles dans global_rank_history :
  (a) `global_rank_cache.parquet` = prédictions OOS du walk-forward
      (train_global_ranking_wf, prédit sur les folds de validation). Couvre
      SEULEMENT 2019-01-02 → 2024-06-28 (259 239 lignes, 5 horizons).
  (b) `predict_global_rank_history()` = modèle FINAL (champion, entraîné
      jusqu'à 2025-12-31) appliqué rétroactivement aux dates hors parquet
      (2018-10→2018-12 et 2024-07→2026-07).
- Le dataset Oracle (oracle-wf-*/oos_predictions.parquet) contient global_rank_20
  par (date, symbol, fold_start).

Classification par ligne Oracle :
  OOF_VALID       = (date,symbol) présent dans le parquet WF OOS
                    (le rank B25 provient du walk-forward → jamais vu D)
  IN_SAMPLE_LEAKED= rank B25 produit par le MODÈLE FINAL (entraîné ≤ 2025-12-31)
                    appliqué à une date D ≤ 2025-12-31  →  le modèle a vu D
  OOS_FINAL       = rank B25 produit par le modèle final mais pour D > 2025-12-31
                    (modèle entraîné strictement avant D → vraiment OOS)
  UNKNOWN         = ni dans le parquet WF, ni après 2025-12-31 (ex: 2018)

Usage :
    python -m scripts.b25_oracle_stack_leakage_audit
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

BATCH_ID = "model-factory-20260811223551-ef2cd0"
BATCH_TRAIN_END = pd.Timestamp("2025-12-31")
ARTIFACTS = Path("artifacts")

# Le dataset Oracle à auditer (OOS predictions walk-forward Oracle)
ORACLE_OOS = ARTIFACTS / "models" / "oracle" / "oracle-wf-20260819034014" / "oos_predictions.parquet"
# Le parquet WF OOS du ranking B25 (source OOF de référence)
RANK_WF_PARQUET = ARTIFACTS / "models" / BATCH_ID / "global_rank_cache.parquet"


def load_db_ranks() -> pd.DataFrame:
    engine = get_sqlalchemy_engine()
    with engine.connect() as c:
        df = pd.read_sql(
            text(
                "SELECT symbol, `date`, global_rank_20 FROM global_rank_history "
                "WHERE batch_id = :b AND global_rank_20 IS NOT NULL"
            ),
            c,
            params={"b": BATCH_ID},
        )
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def main() -> None:
    oracle = pd.read_parquet(ORACLE_OOS)
    oracle["date"] = pd.to_datetime(oracle["date"]).dt.normalize()
    oracle["year"] = oracle["date"].dt.year

    wf = pd.read_parquet(RANK_WF_PARQUET)
    wf["date"] = pd.to_datetime(wf["date"]).dt.normalize()
    wf_keys = set(zip(wf["symbol"].astype(str), wf["date"]))

    # Provenance du rank B25 de chaque ligne Oracle
    def classify(row) -> str:
        key = (str(row["symbol"]), row["date"])
        if key in wf_keys:
            return "OOF_WF"
        if row["date"] <= BATCH_TRAIN_END:
            return "IN_SAMPLE_LEAKED"
        return "OOS_FINAL"

    oracle["rank_source"] = oracle.apply(classify, axis=1)

    # Tableau principal par année (lignes Oracle OOS du WF Oracle)
    print("=== Oracle OOS dataset rows by year: rank_source ===")
    pivot = oracle.pivot_table(index="year", columns="rank_source", values="symbol", aggfunc="count", fill_value=0)
    pivot["TOTAL"] = pivot.sum(axis=1)
    pivot["PCT_LEAKED"] = (100 * pivot.get("IN_SAMPLE_LEAKED", 0) / pivot["TOTAL"]).round(1)
    print(pivot.to_string())

    # Par fold du WF Oracle
    print("\n=== Par fold Oracle (fold_start) ===")
    fp = oracle.pivot_table(index="fold_start", columns="rank_source", values="symbol", aggfunc="count", fill_value=0)
    fp["TOTAL"] = fp.sum(axis=1)
    fp["PCT_LEAKED"] = (100 * fp.get("IN_SAMPLE_LEAKED", 0) / fp["TOTAL"]).round(1)
    print(fp.to_string())

    # Détail mensuel de la zone contaminée (2024-07 → 2025-12)
    print("\n=== Détail mensuel 2024-06 → 2026-06 ===")
    zone = oracle[oracle["date"].between("2024-06-01", "2026-06-30")].copy()
    zone["month"] = zone["date"].dt.to_period("M").astype(str)
    zp = zone.pivot_table(index="month", columns="rank_source", values="symbol", aggfunc="count", fill_value=0)
    zp["TOTAL"] = zp.sum(axis=1)
    zp["PCT_LEAKED"] = (100 * zp.get("IN_SAMPLE_LEAKED", 0) / zp["TOTAL"]).round(1)
    print(zp.to_string())

    # Vérification : le global_rank_20 du dataset Oracle correspond-il au parquet WF sur la zone OOF ?
    print("\n=== Contrôle : global_rank_20 Oracle vs parquet WF (zone OOF) ===")
    oof = oracle[oracle["rank_source"] == "OOF_WF"].copy()
    m = oof.merge(
        wf[["symbol", "date", "global_rank_20"]].rename(columns={"global_rank_20": "gr_wf"}),
        on=["symbol", "date"], how="left",
    )
    if len(m):
        d = (m["global_rank_20"] - m["gr_wf"]).abs()
        print(f"  lignes OOF_WF auditées: {len(m)} | max|diff|={d.max():.6f} | exact={(d < 1e-9).mean()*100:.2f}%")
        if d.max() > 1e-6:
            bad = m[d > 1e-6]
            print("  ⚠️ divergences par rapport au parquet WF — dates:", sorted(set(bad["date"].dt.strftime('%Y-%m')))[:10])

    # Résumé global
    total = len(oracle)
    leaked = int((oracle["rank_source"] == "IN_SAMPLE_LEAKED").sum())
    oof_wf = int((oracle["rank_source"] == "OOF_WF").sum())
    oos_final = int((oracle["rank_source"] == "OOS_FINAL").sum())
    print("\n=== RÉSUMÉ ===")
    print(f"  total lignes Oracle OOS        : {total}")
    print(f"  OOF_WF  (rank walk-forward OOS) : {oof_wf} ({100*oof_wf/total:.1f}%)")
    print(f"  OOS_FINAL (>2025-12-31, final)  : {oos_final} ({100*oos_final/total:.1f}%)")
    print(f"  IN_SAMPLE_LEAKED (final ≤2025)  : {leaked} ({100*leaked/total:.1f}%)  <-- CONTAMINATION")
    print("\n  → Les expériences Oracle O1 (avec global_rank_20) sur les folds")
    print("    contenant 2024H2/2025 sont contaminées par stacking leakage.")
    print("  → Les folds 2022/2023/2024H1 (source WF OOS) et 2026 (final OOS) sont propres.")


if __name__ == "__main__":
    main()
