"""Politiques de résilience pour ML et sentiment dans le backtesting."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy.engine import Engine

from backtesting.backfill_scores_history import BackfillScoresHistoryService
from modelFactory.predictor import predict_symbol

LOGGER = logging.getLogger(__name__)

MLMode = str
SentimentMode = str


def _normalize_dates(df: pd.DataFrame, date_col: str = "trade_date") -> pd.DataFrame:
    normalized = df.copy()
    if date_col in normalized.columns:
        normalized[date_col] = pd.to_datetime(normalized[date_col], errors="coerce").dt.normalize()
    return normalized


def _expected_symbol_dates(scores_df: pd.DataFrame) -> set[tuple[str, object]]:
    if scores_df.empty:
        return set()
    normalized = _normalize_dates(scores_df)
    return {
        (str(row["symbol"]), row["trade_date"])
        for _, row in normalized[["symbol", "trade_date"]].dropna().drop_duplicates().iterrows()
    }


def prepare_scores_for_sentiment_mode(
    engine: Engine,
    scores_df: pd.DataFrame,
    *,
    sentiment_mode: SentimentMode,
) -> pd.DataFrame:
    """Applique une politique de résilience sur `final_score_sentiment`."""
    if scores_df.empty:
        return scores_df.copy()

    result = scores_df.copy()
    if "final_score" not in result.columns:
        return result

    if "final_score_sentiment" not in result.columns:
        result["final_score_sentiment"] = result["final_score"]

    if sentiment_mode == "off":
        result["final_score_sentiment"] = result["final_score"]
        LOGGER.info("Sentiment mode=off — utilisation de final_score sans boost sentiment.")
        return result

    missing_mask = result["final_score_sentiment"].isna()
    if sentiment_mode == "auto":
        if missing_mask.any():
            result.loc[missing_mask, "final_score_sentiment"] = result.loc[missing_mask, "final_score"]
            LOGGER.warning(
                "Sentiment mode=auto — %s lignes sans final_score_sentiment, fallback sur final_score.",
                int(missing_mask.sum()),
            )
        return result

    if sentiment_mode != "rebuild-missing":
        raise ValueError(f"sentiment_mode invalide: {sentiment_mode}")

    missing_dates = sorted({
        trade_date for trade_date in pd.to_datetime(result.loc[missing_mask, "trade_date"], errors="coerce").dt.date.tolist()
        if trade_date is not None
    })
    if not missing_dates:
        return result

    LOGGER.warning(
        "Sentiment mode=rebuild-missing — tentative de reconstruction des snapshots sentiment pour %s séance(s).",
        len(missing_dates),
    )
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)
    rebuilt_dates = 0
    for snapshot_date in missing_dates:
        try:
            snapshot = service.build_snapshot_for_date(snapshot_date)
            service.persist_snapshot(snapshot, overwrite_existing=True)
            rebuilt_dates += 1
        except Exception:
            LOGGER.warning(
                "Échec reconstruction sentiment snapshot_date=%s — fallback sur final_score pour cette séance.",
                snapshot_date,
                exc_info=True,
            )

    refreshed = result.copy()
    if rebuilt_dates > 0:
        with engine.connect() as conn:
            refreshed_sentiment = pd.read_sql_query(
                """
                SELECT snapshot_date AS trade_date, symbol, final_score_sentiment, final_score
                FROM stock_scores_history
                WHERE snapshot_date BETWEEN :start_date AND :end_date
                """,
                conn,
                params={
                    "start_date": min(missing_dates),
                    "end_date": max(missing_dates),
                },
                parse_dates=["trade_date"],
            )
        refreshed_sentiment["trade_date"] = pd.to_datetime(refreshed_sentiment["trade_date"], errors="coerce")
        refreshed = refreshed.drop(columns=[col for col in ["final_score_sentiment"] if col in refreshed.columns])
        refreshed = refreshed.merge(
            refreshed_sentiment[["trade_date", "symbol", "final_score_sentiment"]],
            on=["trade_date", "symbol"],
            how="left",
        )

    still_missing = refreshed["final_score_sentiment"].isna()
    if still_missing.any():
        refreshed.loc[still_missing, "final_score_sentiment"] = refreshed.loc[still_missing, "final_score"]
        LOGGER.warning(
            "Sentiment mode=rebuild-missing — %s lignes restent sans sentiment, fallback final_score.",
            int(still_missing.sum()),
        )
    return refreshed


def prepare_predictions_for_ml_mode(
    engine: Engine,
    scores_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
    *,
    ml_mode: MLMode,
    artifacts_dir: Path,
) -> pd.DataFrame:
    """Applique une politique de résilience sur `model_predictions`."""
    if ml_mode == "off":
        LOGGER.info("ML mode=off — aucune prédiction ML utilisée.")
        return pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"])

    existing = _normalize_dates(predictions_df) if not predictions_df.empty else pd.DataFrame(
        columns=["symbol", "trade_date", "predicted_proba", "predicted_class"]
    )

    expected_keys = _expected_symbol_dates(scores_df)
    if not expected_keys:
        return existing

    present_keys = set()
    if not existing.empty:
        present_keys = {
            (str(row["symbol"]), row["trade_date"])
            for _, row in existing[["symbol", "trade_date"]].dropna().drop_duplicates().iterrows()
        }

    missing_keys = sorted(expected_keys - present_keys)
    if not missing_keys:
        return existing

    if ml_mode == "auto":
        LOGGER.warning(
            "ML mode=auto — %s prédiction(s) manquante(s), continuation sans ML pour ces lignes.",
            len(missing_keys),
        )
        return existing

    if ml_mode != "rebuild-missing":
        raise ValueError(f"ml_mode invalide: {ml_mode}")

    LOGGER.warning(
        "ML mode=rebuild-missing — tentative de reconstruction de %s prédiction(s) manquante(s).",
        len(missing_keys),
    )
    rebuilt_frames: list[pd.DataFrame] = []
    failed = 0
    for symbol, trade_date in missing_keys:
        try:
            pred = predict_symbol(
                symbol=symbol,
                artifacts_dir=artifacts_dir,
                engine=engine,
                prediction_date=trade_date,
                as_of_date=trade_date,
                persist=True,
            )
            if pred is not None and not pred.empty:
                rebuilt_frames.append(pred.rename(columns={"prediction_date": "trade_date"}))
            else:
                failed += 1
        except Exception:
            failed += 1
            LOGGER.warning(
                "Échec reconstruction prediction symbol=%s date=%s — fallback sans ML.",
                symbol,
                trade_date,
                exc_info=True,
            )

    if rebuilt_frames:
        rebuilt_df = pd.concat(rebuilt_frames, ignore_index=True)
        rebuilt_df = _normalize_dates(rebuilt_df)
        existing = pd.concat([existing, rebuilt_df], ignore_index=True).drop_duplicates(
            subset=["symbol", "trade_date"], keep="last"
        )

    if failed > 0:
        LOGGER.warning(
            "ML mode=rebuild-missing — %s prédiction(s) n'ont pas pu être reconstruites, fallback sans ML.",
            failed,
        )
    return existing


