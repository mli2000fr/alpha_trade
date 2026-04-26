"""Politiques de résilience pour ML et sentiment dans le backtesting."""
from __future__ import annotations

from datetime import date
import logging
from pathlib import Path
from typing import Any
import pandas as pd
from sqlalchemy.engine import Engine

from backtesting.backfill_scores_history import BackfillScoresHistoryService
from backtesting.walk_forward import apply_walk_forward_weights, resolve_latest_walk_forward_weights
from modelFactory.predictor import predict_symbol

LOGGER = logging.getLogger(__name__)

MLMode = str
SentimentMode = str


def _normalize_dates(df: pd.DataFrame, date_col: str = "trade_date") -> pd.DataFrame:
    normalized = df.copy()
    if date_col in normalized.columns:
        normalized_dates = pd.to_datetime(normalized[date_col], errors="coerce")
        normalized[date_col] = normalized_dates.dt.floor("D")
    return normalized


def _expected_symbol_dates(scores_df: pd.DataFrame) -> set[tuple[str, pd.Timestamp]]:
    if scores_df.empty:
        return set()
    normalized = _normalize_dates(scores_df)
    return {
        (str(row["symbol"]), pd.Timestamp(row["trade_date"]))
        for _, row in normalized[["symbol", "trade_date"]].dropna().drop_duplicates().iterrows()
    }


def _ensure_dataframe(value: object) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, pd.Series):
        return value.to_frame().T.copy()
    return pd.DataFrame(value)


def _merge_prediction_frames(existing: pd.DataFrame, rebuilt: pd.DataFrame) -> pd.DataFrame:
    merged = pd.concat([existing, rebuilt], ignore_index=True)
    merged_df = pd.DataFrame(merged)
    deduped = merged_df.drop_duplicates(subset=["symbol", "trade_date"], keep="last")
    return pd.DataFrame(deduped)


def _rebuild_prediction_frame(
    *,
    symbol: str,
    trade_date: date,
    artifacts_dir: Path,
    engine: Engine,
) -> pd.DataFrame:
    prediction = predict_symbol(
        symbol=symbol,
        artifacts_dir=artifacts_dir,
        engine=engine,
        prediction_date=trade_date,
        as_of_date=trade_date,
        persist=True,
    )
    pred_df = _ensure_dataframe(prediction) if prediction is not None else pd.DataFrame()
    if not pred_df.empty and "prediction_date" in pred_df.columns:
        pred_df = pred_df.rename(columns={"prediction_date": "trade_date"})
    return pred_df


def prepare_scores_for_sentiment_mode(
    engine: Engine,
    scores_df: pd.DataFrame,
    *,
    sentiment_mode: SentimentMode,
    walk_forward_artifacts_dir: Path | None = None,
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
        return _apply_walk_forward_overlay(result, walk_forward_artifacts_dir)

    missing_mask = result["final_score_sentiment"].isna()
    if sentiment_mode == "auto":
        if missing_mask.any():
            result.loc[missing_mask, "final_score_sentiment"] = result.loc[missing_mask, "final_score"]
            LOGGER.warning(
                "Sentiment mode=auto — %s lignes sans final_score_sentiment, fallback sur final_score.",
                int(missing_mask.sum()),
            )
        return _apply_walk_forward_overlay(result, walk_forward_artifacts_dir)

    if sentiment_mode != "rebuild-missing":
        raise ValueError(f"sentiment_mode invalide: {sentiment_mode}")

    parsed_missing_trade_dates = pd.to_datetime(result.loc[missing_mask, "trade_date"], errors="coerce")
    missing_dates = sorted({
        pd.Timestamp(value).date()
        for value in parsed_missing_trade_dates.dropna().tolist()
    })
    if not missing_dates:
        return _apply_walk_forward_overlay(result, walk_forward_artifacts_dir)

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
    return _apply_walk_forward_overlay(refreshed, walk_forward_artifacts_dir)


def _apply_walk_forward_overlay(scores_df: pd.DataFrame, artifacts_dir: Path | None) -> pd.DataFrame:
    result = scores_df.copy()
    if result.empty:
        return result
    if "score_source" not in result.columns:
        result["score_source"] = pd.NA
    weights = resolve_latest_walk_forward_weights([artifacts_dir] if artifacts_dir is not None else None)
    if weights is None:
        if "final_score_walk_forward" in result.columns:
            wf_mask = result["final_score_walk_forward"].notna()
            result.loc[wf_mask, "score_source"] = "final_score_walk_forward"
        sentiment_mask = result.get("final_score_sentiment", pd.Series(index=result.index, dtype=float)).notna()
        result.loc[result["score_source"].isna() & sentiment_mask, "score_source"] = "final_score_sentiment"
        final_mask = result.get("final_score", pd.Series(index=result.index, dtype=float)).notna()
        result.loc[result["score_source"].isna() & final_mask, "score_source"] = "final_score"
        return result

    overlaid = apply_walk_forward_weights(result, weights)
    LOGGER.info(
        "Walk-forward overlay appliqué depuis %s (sentiment=%.4f macro=%.4f quant=%.4f).",
        weights.artifact_path,
        weights.sentiment_weight,
        weights.macro_weight,
        weights.quant_weight,
    )
    return overlaid


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

    existing: pd.DataFrame = (
        _normalize_dates(predictions_df)
        if not predictions_df.empty
        else pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"])
    )

    expected_keys = _expected_symbol_dates(scores_df)
    if not expected_keys:
        return existing

    present_keys: set[tuple[str, pd.Timestamp]] = set()
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
    for symbol, trade_key in missing_keys:
        normalized_trade_date = pd.Timestamp(trade_key).date()
        try:
            pred_df = _rebuild_prediction_frame(
                symbol=symbol,
                trade_date=normalized_trade_date,
                artifacts_dir=artifacts_dir,
                engine=engine,
            )
            if not pred_df.empty:
                rebuilt_frames.append(pred_df)
            else:
                failed += 1
        except Exception:
            failed += 1
            LOGGER.warning(
                "Échec reconstruction prediction symbol=%s date=%s — fallback sans ML.",
                symbol,
                normalized_trade_date,
                exc_info=True,
            )

    if rebuilt_frames:
        rebuilt_df = _ensure_dataframe(pd.concat(rebuilt_frames, ignore_index=True))
        rebuilt_df = _normalize_dates(rebuilt_df)
        existing = _merge_prediction_frames(existing, rebuilt_df)

    if failed > 0:
        LOGGER.warning(
            "ML mode=rebuild-missing — %s prédiction(s) n'ont pas pu être reconstruites, fallback sans ML.",
            failed,
        )
    return existing


