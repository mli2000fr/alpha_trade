"""Politiques de résilience pour ML et sentiment dans le backtesting."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy.engine import Engine

from backtesting.backfill_scores_history import BackfillScoresHistoryService
from backtesting.fidelity import (
    MlPreparationDiagnostics,
    PitMlStrategyUnsupportedError,
    PreparedPredictionsResult,
    PreparedScoresResult,
    SentimentPreparationDiagnostics,
    resolve_ml_pit_strategy,
)
from backtesting.walk_forward import apply_walk_forward_weights, resolve_latest_walk_forward_weights
from modelFactory.predictor import predict_batch, predict_symbol
from modelFactory.runtime_status import reset_runtime_status, snapshot_runtime_status

LOGGER = logging.getLogger(__name__)

MLMode = str
SentimentMode = str

ML_MISSING_CAUSE_PREDICTION_MISSING = "prediction_missing"
ML_MISSING_CAUSE_ARTIFACT_MISSING = "artifact_missing"
ML_MISSING_CAUSE_ARTIFACT_INVALID = "artifact_invalid"
ML_MISSING_CAUSE_REBUILD_UNAVAILABLE = "rebuild_unavailable"


def _normalize_dates(df: pd.DataFrame, date_col: str = "trade_date") -> pd.DataFrame:
    normalized = df.copy()
    if date_col in normalized.columns:
        normalized_dates = pd.to_datetime(normalized[date_col], errors="coerce")
        normalized[date_col] = pd.DatetimeIndex(normalized_dates).floor("D")
    return normalized


def _expected_symbol_dates(scores_df: pd.DataFrame) -> set[tuple[str, pd.Timestamp]]:
    if scores_df.empty:
        return set()
    normalized = _normalize_dates(scores_df)
    return {
        (str(row["symbol"]), pd.Timestamp(row["trade_date"]))
        for _, row in normalized[["symbol", "trade_date"]].dropna().drop_duplicates().iterrows()
    }


def _extract_unique_symbols(frame: pd.DataFrame, *, mask: pd.Series | None = None) -> tuple[str, ...]:
    if frame.empty or "symbol" not in frame.columns:
        return ()
    working = frame.loc[mask] if mask is not None else frame
    if working.empty:
        return ()
    values = {
        str(symbol).strip().upper()
        for symbol in working["symbol"].dropna().tolist()
        if str(symbol).strip()
    }
    return tuple(sorted(values))


def _ensure_dataframe(value: object) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, pd.Series):
        return value.to_frame().T.copy()
    if isinstance(value, (list, tuple, dict)):
        return pd.DataFrame(value)
    return pd.DataFrame([value])


def _merge_prediction_frames(existing: pd.DataFrame, rebuilt: pd.DataFrame) -> pd.DataFrame:
    merged = pd.concat([existing, rebuilt], ignore_index=True)
    merged_df = pd.DataFrame(merged)
    deduped = merged_df.drop_duplicates(subset=["symbol", "trade_date"], keep="last")
    return pd.DataFrame(deduped)


def _classify_ml_missing_cause_from_runtime_status(status: dict[str, object]) -> str:
    """Classifie la cause d'un échec de prédiction ML depuis le runtime_status.

    Retourne l'une des constantes ML_MISSING_CAUSE_* :
    - ``artifact_invalid``  : artefact présent mais corrompu / incompatible.
    - ``artifact_missing``  : artefact physiquement absent.
    - ``prediction_missing`` : runtime_status entièrement vide —  aucun artefact n'a
      été tenté (ni chargé, ni signalé).  Différent de rebuild_unavailable.
    - ``rebuild_unavailable``: rebuild tenté mais non exploitable (contexte insuffisant,
      artefact chargé mais prédiction vide pour une autre raison).
    """
    raw_reason = str(status.get("last_artifact_issue_reason") or "").strip().lower()
    if raw_reason:
        if any(token in raw_reason for token in ("invalid", "corrupted", "incompatible", "violation", "read_failed", "payload_not_object")):
            return ML_MISSING_CAUSE_ARTIFACT_INVALID
        if "missing" in raw_reason:
            return ML_MISSING_CAUSE_ARTIFACT_MISSING
    # Runtime status vide ou sans last_artifact_issue_reason : aucun artefact
    # n'a été chargé/signalé — on distingue ce cas de rebuild_unavailable.
    if not status or not any(str(value or "").strip() for value in status.values()):
        return ML_MISSING_CAUSE_PREDICTION_MISSING
    return ML_MISSING_CAUSE_REBUILD_UNAVAILABLE


def _freeze_missing_causes_by_symbol(symbol_causes: dict[str, set[str]]) -> dict[str, tuple[str, ...]]:
    return {
        symbol: tuple(sorted(causes))
        for symbol, causes in sorted(symbol_causes.items())
        if causes
    }


def _rebuild_prediction_frame(
    *,
    symbol: str,
    trade_date: date,
    artifacts_dir: Path,
    engine: Engine,
    persist: bool,
) -> pd.DataFrame:
    prediction = predict_symbol(
        symbol=symbol,
        artifacts_dir=artifacts_dir,
        engine=engine,
        prediction_date=trade_date,
        as_of_date=trade_date,
        persist=persist,
    )
    pred_df = _ensure_dataframe(prediction) if prediction is not None else pd.DataFrame()
    if not pred_df.empty and "prediction_date" in pred_df.columns:
        pred_df = pred_df.rename(columns={"prediction_date": "trade_date"})
    return pred_df


def _rebuild_prediction_batch_frame(
    *,
    symbols: list[str],
    trade_date: date,
    artifacts_dir: Path,
    engine: Engine,
    persist: bool,
) -> pd.DataFrame:
    prediction = predict_batch(
        symbols=symbols,
        artifacts_dir=artifacts_dir,
        engine=engine,
        prediction_date=trade_date,
        as_of_date=trade_date,
        persist=persist,
    )
    pred_df = _ensure_dataframe(prediction) if prediction is not None else pd.DataFrame()
    if not pred_df.empty and "prediction_date" in pred_df.columns:
        pred_df = pred_df.rename(columns={"prediction_date": "trade_date"})
    return pred_df


def _resolve_scores_history_identity(scores_df: pd.DataFrame) -> tuple[str | None, str | None]:
    capital_preset_key = None
    config_fingerprint = None
    if "capital_preset_key" in scores_df.columns:
        preset_values = [str(value).strip() for value in scores_df["capital_preset_key"].dropna().tolist() if str(value).strip()]
        if len(set(preset_values)) == 1:
            capital_preset_key = preset_values[0]
    if "config_fingerprint" in scores_df.columns:
        fingerprint_values = [str(value).strip() for value in scores_df["config_fingerprint"].dropna().tolist() if str(value).strip()]
        if len(set(fingerprint_values)) == 1:
            config_fingerprint = fingerprint_values[0]
    return capital_preset_key, config_fingerprint


def prepare_scores_for_sentiment_mode(
    engine: Engine,
    scores_df: pd.DataFrame,
    *,
    sentiment_mode: SentimentMode,
    walk_forward_artifacts_dir: Path | None = None,
    engine_mode: str = "research",
    return_diagnostics: bool = False,
) -> object:
    """Applique une politique de résilience sur `final_score_sentiment`."""
    def _build_result(frame: pd.DataFrame, diagnostics: SentimentPreparationDiagnostics) -> object:
        if return_diagnostics:
            return PreparedScoresResult(frame=frame, diagnostics=diagnostics)
        return frame

    if scores_df.empty:
        empty_diag = SentimentPreparationDiagnostics(
            requested_mode=sentiment_mode,
            engine_mode=engine_mode,
            rows_input=0,
        )
        return _build_result(scores_df.copy(), empty_diag)

    result = scores_df.copy()
    if "final_score" not in result.columns:
        no_score_diag = SentimentPreparationDiagnostics(
            requested_mode=sentiment_mode,
            engine_mode=engine_mode,
            rows_input=len(result),
            degraded_reasons=("final_score_missing",),
        )
        return _build_result(result, no_score_diag)

    if "final_score_sentiment" not in result.columns:
        result["final_score_sentiment"] = result["final_score"]

    diagnostics = SentimentPreparationDiagnostics(
        requested_mode=sentiment_mode,
        engine_mode=engine_mode,
        rows_input=len(result),
        rows_missing_before=int(result["final_score_sentiment"].isna().sum()),
        missing_symbols_before=_extract_unique_symbols(result, mask=result["final_score_sentiment"].isna()),
    )

    if sentiment_mode == "off":
        result["final_score_sentiment"] = result["final_score"]
        LOGGER.info("Sentiment mode=off — utilisation de final_score sans boost sentiment.")
        diagnostics.rows_filled_from_final_score = len(result)
        result, diagnostics.walk_forward_overlay_applied, diagnostics.walk_forward_artifact_path = _apply_walk_forward_overlay(result, walk_forward_artifacts_dir)
        diagnostics.rows_missing_after = int(result["final_score_sentiment"].isna().sum())
        diagnostics.missing_symbols_after = _extract_unique_symbols(result, mask=result["final_score_sentiment"].isna())
        return _build_result(result, diagnostics)

    missing_mask = result["final_score_sentiment"].isna()
    if sentiment_mode == "auto":
        if missing_mask.any():
            result.loc[missing_mask, "final_score_sentiment"] = result.loc[missing_mask, "final_score"]
            diagnostics.rows_filled_from_final_score = int(missing_mask.sum())
            diagnostics.degraded_reasons = ("sentiment_missing_fallback_final_score",)
            LOGGER.warning(
                "Sentiment mode=auto — %s lignes sans final_score_sentiment, fallback sur final_score.",
                int(missing_mask.sum()),
            )
        result, diagnostics.walk_forward_overlay_applied, diagnostics.walk_forward_artifact_path = _apply_walk_forward_overlay(result, walk_forward_artifacts_dir)
        diagnostics.rows_missing_after = int(result["final_score_sentiment"].isna().sum())
        diagnostics.missing_symbols_after = _extract_unique_symbols(result, mask=result["final_score_sentiment"].isna())
        return _build_result(result, diagnostics)

    if sentiment_mode != "rebuild-missing":
        raise ValueError(f"sentiment_mode invalide: {sentiment_mode}")

    parsed_missing_trade_dates = pd.to_datetime(result.loc[missing_mask, "trade_date"], errors="coerce")
    missing_dates = sorted({
        pd.Timestamp(value).date()
        for value in parsed_missing_trade_dates.dropna().tolist()
    })
    if not missing_dates:
        result, diagnostics.walk_forward_overlay_applied, diagnostics.walk_forward_artifact_path = _apply_walk_forward_overlay(result, walk_forward_artifacts_dir)
        diagnostics.rows_missing_after = int(result["final_score_sentiment"].isna().sum())
        diagnostics.missing_symbols_after = _extract_unique_symbols(result, mask=result["final_score_sentiment"].isna())
        return _build_result(result, diagnostics)

    LOGGER.warning(
        "Sentiment mode=rebuild-missing — tentative de reconstruction des snapshots sentiment pour %s séance(s).",
        len(missing_dates),
    )
    resolved_preset_key, resolved_config_fingerprint = _resolve_scores_history_identity(result)
    diagnostics.rebuilt_dates_attempted = len(missing_dates)
    diagnostics.writeback_enabled = engine_mode != "pipeline"
    service = BackfillScoresHistoryService(
        engine=engine,
        screener_max_workers=1,
        capital_preset_key=resolved_preset_key or "capital_0_2000",
        config_fingerprint=resolved_config_fingerprint,
    )
    rebuilt_dates = 0
    rebuilt_frames: list[pd.DataFrame] = []
    for snapshot_date in missing_dates:
        try:
            snapshot = service.build_snapshot_for_date(snapshot_date)
            if snapshot.empty:
                continue
            rebuilt_dates += 1
            if diagnostics.writeback_enabled:
                service.persist_snapshot(snapshot, overwrite_existing=True)
                diagnostics.writeback_performed = True
            rebuilt_frames.append(snapshot[["snapshot_date", "symbol", "final_score_sentiment"]].copy())
        except Exception:
            LOGGER.warning(
                "Échec reconstruction sentiment snapshot_date=%s — fallback sur final_score pour cette séance.",
                snapshot_date,
                exc_info=True,
            )
    diagnostics.rebuilt_dates_succeeded = rebuilt_dates

    refreshed = result.copy()
    if rebuilt_dates > 0:
        if diagnostics.writeback_enabled:
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
        else:
            refreshed_sentiment = pd.concat(rebuilt_frames, ignore_index=True) if rebuilt_frames else pd.DataFrame(columns=["snapshot_date", "symbol", "final_score_sentiment"])
            if not refreshed_sentiment.empty:
                refreshed_sentiment = refreshed_sentiment.rename(columns={"snapshot_date": "trade_date"})
                refreshed_sentiment["trade_date"] = pd.to_datetime(refreshed_sentiment["trade_date"], errors="coerce")
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
        diagnostics.rows_filled_from_final_score += int(still_missing.sum())
        LOGGER.warning(
            "Sentiment mode=rebuild-missing — %s lignes restent sans sentiment, fallback final_score.",
            int(still_missing.sum()),
        )
    degraded_reasons: list[str] = []
    if rebuilt_dates < len(missing_dates):
        degraded_reasons.append("sentiment_rebuild_partial_failure")
    if still_missing.any():
        degraded_reasons.append("sentiment_missing_fallback_final_score")
    diagnostics.degraded_reasons = tuple(degraded_reasons)
    refreshed, diagnostics.walk_forward_overlay_applied, diagnostics.walk_forward_artifact_path = _apply_walk_forward_overlay(refreshed, walk_forward_artifacts_dir)
    diagnostics.rows_missing_after = int(refreshed["final_score_sentiment"].isna().sum())
    diagnostics.missing_symbols_after = _extract_unique_symbols(refreshed, mask=refreshed["final_score_sentiment"].isna())
    return _build_result(refreshed, diagnostics)


def _apply_walk_forward_overlay(scores_df: pd.DataFrame, artifacts_dir: Path | None) -> tuple[pd.DataFrame, bool, str | None]:
    result = scores_df.copy()
    if result.empty:
        return result, False, None
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
        return result, False, None

    overlaid = apply_walk_forward_weights(result, weights)
    LOGGER.info(
        "Walk-forward overlay appliqué depuis %s (sentiment=%.4f macro=%.4f quant=%.4f).",
        weights.artifact_path,
        weights.sentiment_weight,
        weights.macro_weight,
        weights.quant_weight,
    )
    return overlaid, True, str(weights.artifact_path)


def prepare_predictions_for_ml_mode(
    engine: Engine,
    scores_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
    *,
    ml_mode: MLMode,
    artifacts_dir: Path,
    engine_mode: str = "research",
    ml_pit_strategy: str = "auto",
    return_diagnostics: bool = False,
) -> object:
    """Applique une politique de résilience sur `model_predictions`."""
    def _build_result(frame: pd.DataFrame, diagnostics: MlPreparationDiagnostics) -> object:
        if return_diagnostics:
            return PreparedPredictionsResult(frame=frame, diagnostics=diagnostics)
        return frame

    effective_strategy = resolve_ml_pit_strategy(
        engine_mode=engine_mode,
        ml_mode=ml_mode,
        requested_strategy=ml_pit_strategy,
    )

    if ml_mode == "off":
        LOGGER.info("ML mode=off — aucune prédiction ML utilisée.")
        empty_diag = MlPreparationDiagnostics(
            requested_mode=ml_mode,
            requested_strategy=ml_pit_strategy,
            effective_strategy=effective_strategy,
            engine_mode=engine_mode,
            predictions_input_rows=0,
            expected_symbol_dates=0,
            missing_prediction_keys=0,
        )
        return _build_result(pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"]), empty_diag)

    existing: pd.DataFrame = (
        _normalize_dates(predictions_df)
        if not predictions_df.empty
        else pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"])
    )

    expected_keys = _expected_symbol_dates(scores_df)
    diagnostics = MlPreparationDiagnostics(
        requested_mode=ml_mode,
        requested_strategy=ml_pit_strategy,
        effective_strategy=effective_strategy,
        engine_mode=engine_mode,
        predictions_input_rows=len(existing),
        expected_symbol_dates=len(expected_keys),
        missing_prediction_keys=0,
    )
    if not expected_keys:
        return _build_result(existing, diagnostics)

    present_keys: set[tuple[str, pd.Timestamp]] = set()
    if not existing.empty:
        present_keys_list: list[tuple[str, pd.Timestamp]] = []
        for symbol, trade_date in existing[["symbol", "trade_date"]].dropna().drop_duplicates().itertuples(index=False, name=None):
            present_keys_list.append((str(symbol), pd.Timestamp(trade_date)))
        present_keys = set(present_keys_list)

    missing_keys = sorted(expected_keys - present_keys)
    diagnostics.missing_prediction_keys = len(missing_keys)
    diagnostics.missing_symbols_before = tuple(sorted({symbol for symbol, _trade_date in missing_keys}))
    if not missing_keys:
        diagnostics.missing_prediction_keys_after = 0
        diagnostics.missing_symbols_after = ()
        return _build_result(existing, diagnostics)

    if effective_strategy == "use-persisted":
        diagnostics.degraded_reasons = ("ml_predictions_missing",)
        diagnostics.missing_prediction_keys_after = len(missing_keys)
        diagnostics.missing_symbols_after = diagnostics.missing_symbols_before
        diagnostics.missing_cause_breakdown = {
            ML_MISSING_CAUSE_PREDICTION_MISSING: len(missing_keys),
        }
        diagnostics.missing_causes_by_symbol = {
            symbol: (ML_MISSING_CAUSE_PREDICTION_MISSING,)
            for symbol in diagnostics.missing_symbols_before
        }
        LOGGER.warning(
            "ML PIT strategy=use-persisted — %s prédiction(s) manquante(s), aucun rebuild tenté.",
            len(missing_keys),
        )
        return _build_result(existing, diagnostics)

    if effective_strategy == "walk-forward-train-then-predict":
        raise PitMlStrategyUnsupportedError(
            "La stratégie ML PIT `walk-forward-train-then-predict` n'est pas encore supportée en Phase 1. "
            "Utilisez `use-persisted` ou `rebuild-missing`."
        )

    if ml_mode == "auto":
        LOGGER.warning(  # type: ignore[arg-type]
            "ML mode=auto — %s prédiction(s) manquante(s), continuation sans ML pour ces lignes.",
            len(missing_keys),
        )
        diagnostics.degraded_reasons = ("ml_predictions_missing",)
        diagnostics.missing_prediction_keys_after = len(missing_keys)
        diagnostics.missing_symbols_after = diagnostics.missing_symbols_before
        diagnostics.missing_cause_breakdown = {
            ML_MISSING_CAUSE_PREDICTION_MISSING: len(missing_keys),
        }
        diagnostics.missing_causes_by_symbol = {
            symbol: (ML_MISSING_CAUSE_PREDICTION_MISSING,)
            for symbol in diagnostics.missing_symbols_before
        }
        return _build_result(existing, diagnostics)

    if ml_mode != "rebuild-missing" and effective_strategy != "rebuild-missing":
        raise ValueError(f"ml_mode invalide: {ml_mode}")

    LOGGER.warning(
        "ML mode=rebuild-missing — tentative de reconstruction de %s prédiction(s) manquante(s).",
        len(missing_keys),
    )
    diagnostics.rebuild_attempted = True
    diagnostics.persist_enabled = engine_mode != "pipeline"
    rebuilt_frames: list[pd.DataFrame] = []
    failed = 0
    cause_breakdown: dict[str, int] = defaultdict(int)
    missing_causes_by_symbol: dict[str, set[str]] = defaultdict(set)
    missing_symbols_by_trade_date: dict[date, list[str]] = defaultdict(list)
    for symbol, trade_key in missing_keys:
        normalized_trade_date = pd.Timestamp(trade_key).date()
        missing_symbols_by_trade_date[normalized_trade_date].append(symbol)

    for normalized_trade_date, symbols_for_trade_date in sorted(missing_symbols_by_trade_date.items()):
        batch_symbols = sorted(dict.fromkeys(symbols_for_trade_date))
        try:
            reset_runtime_status({})
            pred_df = _rebuild_prediction_batch_frame(
                symbols=batch_symbols,
                trade_date=normalized_trade_date,
                artifacts_dir=artifacts_dir,
                engine=engine,
                persist=diagnostics.persist_enabled,
            )
            if not pred_df.empty:
                rebuilt_frames.append(pred_df)
            else:
                failed += len(batch_symbols)
                cause = _classify_ml_missing_cause_from_runtime_status(snapshot_runtime_status())
                cause_breakdown[cause] += len(batch_symbols)
                for symbol in batch_symbols:
                    missing_causes_by_symbol[symbol].add(cause)
        except Exception:
            failed += len(batch_symbols)
            cause = _classify_ml_missing_cause_from_runtime_status(snapshot_runtime_status())
            cause_breakdown[cause] += len(batch_symbols)
            for symbol in batch_symbols:
                missing_causes_by_symbol[symbol].add(cause)
            LOGGER.warning(
                "Échec reconstruction prediction symbols=%s date=%s — fallback sans ML.",
                ", ".join(batch_symbols),
                normalized_trade_date,
                exc_info=True,
            )

    if rebuilt_frames:
        rebuilt_df = _ensure_dataframe(pd.concat(rebuilt_frames, ignore_index=True))
        rebuilt_df = _normalize_dates(rebuilt_df)
        existing = _merge_prediction_frames(existing, rebuilt_df)
        diagnostics.rebuilt_prediction_rows = len(rebuilt_df)
        diagnostics.persist_performed = diagnostics.persist_enabled and not rebuilt_df.empty

    present_after_rebuild: set[tuple[str, pd.Timestamp]] = set()
    if not existing.empty:
        present_after_rebuild = {
            (str(symbol), pd.Timestamp(trade_date))
            for symbol, trade_date in existing[["symbol", "trade_date"]].dropna().drop_duplicates().itertuples(index=False, name=None)
        }
    remaining_missing_keys = sorted(expected_keys - present_after_rebuild)
    diagnostics.missing_prediction_keys_after = len(remaining_missing_keys)
    diagnostics.missing_symbols_after = tuple(sorted({symbol for symbol, _trade_date in remaining_missing_keys}))
    diagnostics.missing_cause_breakdown = dict(sorted(cause_breakdown.items()))
    diagnostics.missing_causes_by_symbol = _freeze_missing_causes_by_symbol(missing_causes_by_symbol)

    if failed > 0:
        LOGGER.warning(
            "ML mode=rebuild-missing — %s prédiction(s) n'ont pas pu être reconstruites, fallback sans ML.",
            failed,
        )
    degraded_reasons: list[str] = []
    if failed > 0:
        degraded_reasons.append("ml_rebuild_partial_failure")
    if remaining_missing_keys:
        degraded_reasons.append("ml_predictions_missing")
    diagnostics.degraded_reasons = tuple(dict.fromkeys(degraded_reasons))
    return _build_result(existing, diagnostics)


