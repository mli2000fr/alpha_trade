"""Accès base de données pour le module risk_management."""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.capital_presets import DEFAULT_CAPITAL_PRESET_KEY
from common.config_loader import load_config
from database.connection import get_sqlalchemy_engine
from risk_management.config import RiskConfig
from risk_management.ml_gate import resolve_ml_gate_state
from risk_management.models import AccountRiskSnapshot, CandidateScore, PredictionInfo, PriceInfo, WinRateInfo

LOGGER = logging.getLogger(__name__)

_DEFAULT_EMPIRICAL_CALIBRATION_FALLBACK_LEVELS: tuple[str, ...] = (
    "exact_segment",
    "regime_all",
    "same_regime_nearest_window",
    "regime_all_nearest_window",
    "same_regime_nearest_horizon",
    "regime_all_nearest_horizon",
    "same_regime_nearest_segment",
    "regime_all_nearest_segment",
)
_SUPPORTED_EMPIRICAL_CALIBRATION_FALLBACK_LEVELS = set(_DEFAULT_EMPIRICAL_CALIBRATION_FALLBACK_LEVELS)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _build_runtime_segment_key(
    *,
    market_regime_mode: str | None,
    horizon_days: int | None,
    lookback_months: int | None,
) -> str | None:
    normalized_regime = str(market_regime_mode or "").strip().lower() or "all"
    if horizon_days is None and lookback_months is None and not normalized_regime:
        return None
    parts = [f"regime={normalized_regime}"]
    if horizon_days is not None:
        parts.append(f"horizon={int(horizon_days)}d")
    if lookback_months is not None:
        parts.append(f"window={int(lookback_months)}m")
    return "|".join(parts)


def _load_empirical_calibration_fallback_levels() -> tuple[list[str], str]:
    try:
        cfg = load_config() or {}
    except Exception:
        LOGGER.warning(
            "Chargement config.yaml impossible pour la politique de fallback des calibrations empiriques.",
            exc_info=True,
        )
        return list(_DEFAULT_EMPIRICAL_CALIBRATION_FALLBACK_LEVELS), "defaults_on_config_error"

    risk_management_cfg = cfg.get("risk_management") if isinstance(cfg, Mapping) else None
    empirical_cfg = risk_management_cfg.get("empirical_calibration") if isinstance(risk_management_cfg, Mapping) else None
    raw_levels = empirical_cfg.get("fallback_levels") if isinstance(empirical_cfg, Mapping) else None
    if raw_levels in (None, ""):
        return list(_DEFAULT_EMPIRICAL_CALIBRATION_FALLBACK_LEVELS), "defaults"
    if not isinstance(raw_levels, Sequence) or isinstance(raw_levels, (str, bytes)):
        LOGGER.warning("risk_management.empirical_calibration.fallback_levels invalide : %r", raw_levels)
        return list(_DEFAULT_EMPIRICAL_CALIBRATION_FALLBACK_LEVELS), "defaults_invalid_config"

    normalized_levels: list[str] = []
    invalid_levels: list[str] = []
    for raw_level in raw_levels:
        level = str(raw_level or "").strip()
        if not level:
            continue
        if level not in _SUPPORTED_EMPIRICAL_CALIBRATION_FALLBACK_LEVELS:
            invalid_levels.append(level)
            continue
        if level not in normalized_levels:
            normalized_levels.append(level)
    if invalid_levels:
        LOGGER.warning(
            "Niveaux de fallback inconnus ignorés dans config.yaml : %s",
            ", ".join(sorted(invalid_levels)),
        )
    if not normalized_levels:
        LOGGER.warning(
            "Aucun niveau valide sous risk_management.empirical_calibration.fallback_levels ; défauts conservés.",
        )
        return list(_DEFAULT_EMPIRICAL_CALIBRATION_FALLBACK_LEVELS), "defaults_invalid_config"
    return normalized_levels, "config_yaml"


class RiskRepository:
    """Lecture/écriture SQL pour le module risk_management."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_sqlalchemy_engine()

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def load_candidates(self, config: RiskConfig, trade_date: date | None = None) -> list[CandidateScore]:
        """Compatibilité API : charge les candidats PIT à la date demandée."""
        return self.load_candidates_asof(trade_date or date.today())

    def load_candidates_asof(self, trade_date: date) -> list[CandidateScore]:
        """Charge les candidats depuis stock_scores_history avec sémantique PIT.

        On cherche d'abord les candidats du `trade_date` exact ; si la date n'a
        pas encore été archivée (cas fréquent quand `risk_management` tourne en
        amont de `archive_scores_snapshot` du jour ou que le screener n'a pas
        publié de nouveau snapshot), on retombe sur le dernier `snapshot_date`
        <= `trade_date` qui contient au moins un candidat exploitable.
        """
        stock_score_columns = self._get_table_columns("stock_scores_history")
        if not stock_score_columns:
            raise RuntimeError("La table stock_scores_history est requise pour les runs PIT risk_management.")
        has_walk_forward = "final_score_walk_forward" in stock_score_columns
        has_capital_preset_key = "capital_preset_key" in stock_score_columns
        preset_filter_sql = ""
        preset_params: dict[str, Any] = {}
        if has_capital_preset_key:
            preset_filter_sql = " AND capital_preset_key = :capital_preset_key"
            preset_params["capital_preset_key"] = DEFAULT_CAPITAL_PRESET_KEY
        score_expr = (
            "COALESCE(s.final_score_walk_forward, s.final_score_sentiment, s.final_score)"
            if has_walk_forward
            else "COALESCE(s.final_score_sentiment, s.final_score)"
        )
        # Variante du score_expr sans alias `s.` pour le sous-SELECT de fallback.
        score_expr_unaliased = score_expr.replace("s.", "")
        score_source_expr = (
            """
            CASE
                WHEN s.final_score_walk_forward IS NOT NULL THEN 'final_score_walk_forward'
                WHEN s.final_score_sentiment IS NOT NULL THEN 'final_score_sentiment'
                ELSE 'final_score'
            END
            """
            if has_walk_forward
            else """
            CASE
                WHEN s.final_score_sentiment IS NOT NULL THEN 'final_score_sentiment'
                ELSE 'final_score'
            END
            """
        )
        optional_float_columns = [
            "company_idio_score",
            "macro_regime_score",
            "company_idio_signal_norm",
            "macro_regime_signal_norm",
            "company_idio_component",
            "macro_regime_component",
            "quant_component",
            "walk_forward_sentiment_weight",
            "walk_forward_macro_weight",
            "walk_forward_quant_weight",
        ]
        optional_int_columns = ["candidate_rank", "earnings_blackout"]
        optional_text_columns = [
            "calibration_run_id",
            "calibration_source",
            "selector_signal_mode",
            "selection_explanation",
        ]
        optional_selects = [
            f"s.{column}" if column in stock_score_columns else f"NULL AS {column}"
            for column in [*optional_float_columns, *optional_int_columns, *optional_text_columns]
        ]
        query = text(f"""
            SELECT
                s.snapshot_date,
                s.symbol,
                COALESCE(s.sector, 'UNKNOWN') AS sector,
                {score_expr}                  AS score_used,
                {score_source_expr}           AS score_source,
                {", ".join(optional_selects)}
            FROM stock_scores_history s
            WHERE s.snapshot_date = :snapshot_date
              {preset_filter_sql}
              AND s.is_candidate = 1
              AND {score_expr} IS NOT NULL
            ORDER BY score_used DESC, s.symbol ASC
        """)
        resolve_snapshot_query = text(f"""
            SELECT MAX(snapshot_date) AS snapshot_date
            FROM stock_scores_history
            WHERE snapshot_date <= :trade_date
              {preset_filter_sql}
              AND is_candidate = 1
              AND {score_expr_unaliased} IS NOT NULL
        """)
        with self.engine.connect() as conn:
            resolved_row = conn.execute(resolve_snapshot_query, {"trade_date": trade_date, **preset_params}).mappings().first()
            resolved_snapshot_date = self._coerce_date(resolved_row["snapshot_date"]) if resolved_row else None
            if resolved_snapshot_date is None:
                LOGGER.warning(
                    "load_candidates_asof | aucun snapshot stock_scores_history avec is_candidate=1 trouve pour trade_date<=%s.",
                    trade_date,
                )
                return []
            if resolved_snapshot_date != trade_date:
                LOGGER.info(
                    "load_candidates_asof | snapshot_date=%s utilise (PIT as-of) pour trade_date=%s. "
                    "Comportement attendu : sémantique point-in-time, le snapshot le plus récent <= trade_date est sélectionné.",
                    resolved_snapshot_date,
                    trade_date,
                )
            else:
                LOGGER.info(
                    "load_candidates_asof | snapshot_date=%s exact pour trade_date=%s.",
                    resolved_snapshot_date,
                    trade_date,
                )
            rows = conn.execute(query, {"snapshot_date": resolved_snapshot_date, **preset_params}).mappings().all()
        return [
            CandidateScore(
                symbol=str(r["symbol"]).strip().upper(),
                sector=str(r["sector"]),
                score_used=float(r["score_used"]),
                score_source=str(r.get("score_source") or "final_score_sentiment"),
                company_idio_score=float(r["company_idio_score"]) if r.get("company_idio_score") is not None else None,
                macro_regime_score=float(r["macro_regime_score"]) if r.get("macro_regime_score") is not None else None,
                company_idio_signal_norm=float(r["company_idio_signal_norm"]) if r.get("company_idio_signal_norm") is not None else None,
                macro_regime_signal_norm=float(r["macro_regime_signal_norm"]) if r.get("macro_regime_signal_norm") is not None else None,
                company_idio_component=float(r["company_idio_component"]) if r.get("company_idio_component") is not None else None,
                macro_regime_component=float(r["macro_regime_component"]) if r.get("macro_regime_component") is not None else None,
                quant_component=float(r["quant_component"]) if r.get("quant_component") is not None else None,
                walk_forward_sentiment_weight=float(r["walk_forward_sentiment_weight"]) if r.get("walk_forward_sentiment_weight") is not None else None,
                walk_forward_macro_weight=float(r["walk_forward_macro_weight"]) if r.get("walk_forward_macro_weight") is not None else None,
                walk_forward_quant_weight=float(r["walk_forward_quant_weight"]) if r.get("walk_forward_quant_weight") is not None else None,
                calibration_run_id=str(r["calibration_run_id"]) if r.get("calibration_run_id") is not None else None,
                calibration_source=str(r["calibration_source"]) if r.get("calibration_source") is not None else None,
                snapshot_date=self._coerce_date(r.get("snapshot_date")),
                candidate_rank=_optional_int(r.get("candidate_rank")),
                selector_signal_mode=_optional_text(r.get("selector_signal_mode")),
                selection_explanation=_optional_text(r.get("selection_explanation")),
                selector_earnings_blackout=_optional_int(r.get("earnings_blackout")),
            )
            for r in rows
        ]

    def _get_table_columns(self, table_name: str) -> set[str]:
        try:
            inspector = self.engine.dialect.inspector(self.engine)  # type: ignore[attr-defined]
            return {str(column["name"]) for column in inspector.get_columns(table_name)}
        except Exception:
            try:
                from sqlalchemy import inspect

                return {str(column["name"]) for column in inspect(self.engine).get_columns(table_name)}
            except Exception:
                LOGGER.debug("Impossible d'inspecter les colonnes de %s.", table_name, exc_info=True)
                return set()

    @staticmethod
    def _coerce_date(value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except Exception:
            return None

    def _load_latest_broker_account_snapshot_row(
        self,
        account_id: str,
        trade_date: date,
        *,
        require_positive_equity: bool,
    ) -> tuple[dict[str, Any] | None, set[str]]:
        broker_columns = self._get_table_columns("broker_account_snapshots")
        if not broker_columns:
            return None, broker_columns

        select_columns = [
            column
            for column in ("account_id", "cash", "settled_cash", "equity", "buying_power", "created_at")
            if column in broker_columns
        ]
        where_clauses = ["account_id = :account_id", "DATE(created_at) <= :trade_date"]
        params: dict[str, Any] = {"account_id": account_id, "trade_date": trade_date}
        if "snapshot_kind" in broker_columns:
            where_clauses.append("snapshot_kind = :snapshot_kind")
            params["snapshot_kind"] = "preflight"
        if require_positive_equity and "equity" in broker_columns:
            where_clauses.append("equity IS NOT NULL AND equity > 0")
        order_by = "created_at DESC"
        if "id" in broker_columns:
            order_by += ", id DESC"
        stmt = text(
            f"""
            SELECT {", ".join(select_columns)}
            FROM broker_account_snapshots
            WHERE {' AND '.join(where_clauses)}
            ORDER BY {order_by}
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            row = conn.execute(stmt, params).mappings().first()
        return (dict(row) if row is not None else None), broker_columns

    def load_prices(self, symbols: list[str], atr_window: int = 20, trade_date: date | None = None) -> dict[str, PriceInfo]:
        """Compatibilité API : charge les prix PIT à la date demandée."""
        return self.load_prices_asof(symbols, trade_date or date.today(), atr_window=atr_window)

    def load_prices_asof(self, symbols: list[str], trade_date: date, atr_window: int = 20) -> dict[str, PriceInfo]:
        """Charge le dernier close, l'ATR et l'ADV 20j depuis stock_bars_daily à la date de trade."""
        if not symbols:
            return {}
        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["trade_date"] = trade_date
        params["row_limit"] = atr_window + 1
        query = text(f"""
            WITH ranked AS (
                SELECT
                    symbol,
                    `date` AS trade_day,
                    `close` AS close_price,
                    `high` AS high_price,
                    `low` AS low_price,
                    `volume` AS volume,
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY `date` DESC) AS rn
                FROM stock_bars_daily
                WHERE symbol IN ({placeholders})
                  AND `date` <= :trade_date
            )
            SELECT symbol, trade_day, close_price, high_price, low_price, volume
            FROM ranked
            WHERE rn <= :row_limit
            ORDER BY symbol ASC, trade_day ASC
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()

        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            sym = str(row["symbol"]).strip().upper()
            grouped.setdefault(sym, []).append(dict(row))

        result: dict[str, PriceInfo] = {}
        adv_window = atr_window  # 20j par défaut, cohérent avec ATR
        for sym, sym_rows in grouped.items():
            if not sym_rows:
                continue
            last_row = sym_rows[-1]
            last_close = float(last_row["close_price"])
            price_asof_date = self._coerce_date(last_row.get("trade_day"))

            tr_values: list[float] = []
            dollar_volumes: list[float] = []
            for idx in range(1, len(sym_rows)):
                prev_close = float(sym_rows[idx - 1]["close_price"])
                high_price = float(sym_rows[idx]["high_price"])
                low_price = float(sym_rows[idx]["low_price"])
                true_range = max(high_price - low_price, abs(high_price - prev_close), abs(low_price - prev_close))
                tr_values.append(true_range)
                # ADV : close × volume (en dollars)
                vol = float(sym_rows[idx].get("volume", 0) or 0)
                dollar_volumes.append(float(sym_rows[idx]["close_price"]) * vol)

            atr_val = None
            atr_asof_date = None
            if len(tr_values) >= atr_window:
                atr_window_values = tr_values[-atr_window:]
                atr_val = sum(atr_window_values) / atr_window
                atr_asof_date = price_asof_date

            # ADV 20j = moyenne des dollar_volumes sur la fenêtre
            adv_usd = None
            if len(dollar_volumes) >= adv_window:
                adv_usd = sum(dollar_volumes[-adv_window:]) / adv_window

            result[sym] = PriceInfo(
                symbol=sym,
                last_close=last_close,
                atr_20=atr_val,
                price_asof_date=price_asof_date,
                atr_asof_date=atr_asof_date,
                adv_usd=adv_usd,
            )
        return result

    def load_predictions(
        self, symbols: list[str], trade_date: date,
    ) -> dict[str, PredictionInfo]:
        """Compatibilité API : charge la dernière prédiction ML PIT."""
        return self.load_predictions_asof(symbols, trade_date)

    def load_predictions_asof(
        self, symbols: list[str], trade_date: date,
    ) -> dict[str, PredictionInfo]:
        """Charge la dernière prédiction ML par symbole à la date de trade.

        Sprint S8 — kill-switch ML : si :func:`risk_management.ml_gate.resolve_ml_gate_state`
        renvoie ``enabled=False`` (drift policy ALERT ou flag CLI ``--disable-ml``),
        on retourne ``{}`` sans même interroger ``model_predictions``. Le risk
        sizer retombe ainsi sur le score quantitatif pur.
        """
        if not symbols:
            return {}
        gate = resolve_ml_gate_state(self.engine)
        if not gate.enabled:
            LOGGER.warning(
                "[ml_gate] consommation model_predictions désactivée (raison=%s decision=%s) → score quant pur",
                gate.reason,
                gate.decision_id,
            )
            return {}
        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["trade_date"] = trade_date
        query = text(f"""
            SELECT symbol, predicted_proba, predicted_class, run_id, prediction_date
            FROM (
                SELECT symbol, predicted_proba, predicted_class, run_id, prediction_date,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol
                           ORDER BY prediction_date DESC, created_at DESC, run_id DESC
                       ) AS rn
                FROM model_predictions
                WHERE symbol IN ({placeholders})
                  AND prediction_date <= :trade_date
                  AND predicted_proba IS NOT NULL
            ) ranked
            WHERE rn = 1
        """)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception:
            LOGGER.warning("Impossible de charger model_predictions — table absente ?")
            return {}
        return {
            str(r["symbol"]).strip().upper(): PredictionInfo(
                symbol=str(r["symbol"]).strip().upper(),
                predicted_proba=float(r["predicted_proba"]),
                predicted_class=int(r["predicted_class"]),
                run_id=str(r["run_id"]),
                prediction_date=self._coerce_date(r.get("prediction_date")),
            )
            for r in rows
        }

    def load_win_rates(self, symbols: list[str], trade_date: date | None = None) -> dict[str, WinRateInfo]:
        """Compatibilité API : charge les métriques ML PIT."""
        return self.load_win_rates_asof(symbols, trade_date or date.today())

    def load_win_rates_asof(self, symbols: list[str], trade_date: date) -> dict[str, WinRateInfo]:
        """Charge le win rate historique par symbole via model_metrics + model_training_run."""
        if not symbols:
            return {}
        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["trade_date"] = trade_date
        query = text(f"""
            SELECT symbol, directional_accuracy, split_name, run_id, finished_at
            FROM (
                SELECT m.symbol, m.directional_accuracy, m.split_name, m.run_id, t.finished_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY m.symbol
                           ORDER BY CASE m.split_name WHEN 'test' THEN 0 WHEN 'val' THEN 1 ELSE 2 END,
                                    t.finished_at DESC,
                                    m.run_id DESC
                       ) AS rn
                FROM model_metrics m
                JOIN model_training_run t ON m.run_id = t.run_id
                WHERE t.status = 'completed'
                  AND m.symbol IN ({placeholders})
                  AND m.directional_accuracy IS NOT NULL
                  AND DATE(t.finished_at) <= :trade_date
            ) ranked
            WHERE rn = 1
        """)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception:
            LOGGER.warning("Impossible de charger model_metrics — table absente ?")
            return {}
        return {
            str(r["symbol"]).strip().upper(): WinRateInfo(
                symbol=str(r["symbol"]).strip().upper(),
                directional_accuracy=float(r["directional_accuracy"]),
                split_name=str(r["split_name"]),
                run_id=str(r["run_id"]),
                asof_date=self._coerce_date(r.get("finished_at")),
            )
            for r in rows
        }

    def load_factor_columns_asof(
        self, symbols: list[str], trade_date: date,
    ) -> pd.DataFrame:
        """Charge les colonnes factorielles (beta_126, market_cap, trend_score)
        depuis stock_scores_history pour le modèle de risque factoriel (Priorité 3).

        Parameters
        ----------
        symbols : list[str]
            Symboles à charger.
        trade_date : date
            Date de trading (PIT : snapshot le plus récent <= trade_date).

        Returns
        -------
        pd.DataFrame
            DataFrame avec colonnes : symbol, beta_126, market_cap, trend_score.
        """
        if not symbols:
            return pd.DataFrame()

        import pandas as pd

        stock_score_columns = self._get_table_columns("stock_scores_history")
        if not stock_score_columns:
            LOGGER.warning("load_factor_columns_asof: stock_scores_history indisponible")
            return pd.DataFrame()

        # Vérifier quelles colonnes factorielles sont disponibles
        factor_cols_available = [
            col for col in ["beta_126", "market_cap", "trend_score"]
            if col in stock_score_columns
        ]
        if not factor_cols_available:
            LOGGER.warning("load_factor_columns_asof: aucune colonne factorielle trouvée")
            return pd.DataFrame()

        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["trade_date"] = trade_date

        select_cols = ["s.symbol"] + [f"s.{col}" for col in factor_cols_available]

        # Résoudre le snapshot_date le plus récent
        resolve_query = text(f"""
            SELECT MAX(snapshot_date) AS snapshot_date
            FROM stock_scores_history
            WHERE snapshot_date <= :trade_date
              AND symbol IN ({placeholders})
              AND is_candidate = 1
        """)
        query = text(f"""
            SELECT {', '.join(select_cols)}
            FROM stock_scores_history s
            WHERE s.snapshot_date = :snapshot_date
              AND s.symbol IN ({placeholders})
              AND s.is_candidate = 1
        """)

        try:
            with self.engine.connect() as conn:
                resolved = conn.execute(resolve_query, params).mappings().first()
                if resolved is None:
                    return pd.DataFrame()
                snapshot_date = self._coerce_date(resolved["snapshot_date"])
                if snapshot_date is None:
                    return pd.DataFrame()
                params["snapshot_date"] = snapshot_date
                rows = conn.execute(query, params).mappings().all()
        except Exception:
            LOGGER.warning(
                "load_factor_columns_asof: échec chargement colonnes factorielles",
                exc_info=True,
            )
            return pd.DataFrame()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
        return df

    def load_return_matrix(
        self, symbols: list[str], lookback_days: int, trade_date: date | None = None,
    ) -> pd.DataFrame:
        """Compatibilité API : charge la matrice de rendements PIT."""
        return self.load_return_matrix_asof(symbols, trade_date or date.today(), lookback_days)

    def load_return_matrix_asof(
        self, symbols: list[str], trade_date: date, lookback_days: int,
    ) -> pd.DataFrame:
        """Charge les rendements close-to-close récents en matrice pivotée à date."""
        if not symbols:
            return pd.DataFrame()
        placeholders = ", ".join(f":s{i}" for i in range(len(symbols)))
        params: dict[str, Any] = {f"s{i}": s for i, s in enumerate(symbols)}
        params["trade_date"] = trade_date
        params["row_limit"] = lookback_days + 1
        query = text(f"""
            SELECT symbol, trade_day AS `date`, close_price
            FROM (
                SELECT symbol, `date` AS trade_day, `close` AS close_price,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY `date` DESC) AS rn
                FROM stock_bars_daily
                WHERE symbol IN ({placeholders})
                  AND `date` <= :trade_date
            ) ranked
            WHERE rn <= :row_limit
        """)
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception:
            LOGGER.warning("Impossible de charger stock_bars_daily pour la matrice de correlation.", exc_info=True)
            return pd.DataFrame()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        pivot = df.pivot_table(index="date", columns="symbol", values="close_price")
        returns = pivot.sort_index().pct_change(fill_method=None).iloc[1:]
        return returns.tail(lookback_days)

    def load_account_risk_snapshot(self, account_id: str | None, trade_date: date) -> AccountRiskSnapshot | None:
        """Charge le dernier snapshot compte disponible <= trade_date."""
        resolved_account_id = account_id or "default"
        if self._get_table_columns("account_risk_snapshots"):
            query = text("""
                SELECT account_id, trade_date, cash, equity, buying_power,
                       high_watermark, daily_realized_pnl, daily_unrealized_pnl,
                       daily_total_pnl, created_at
                FROM account_risk_snapshots
                WHERE account_id = :account_id
                  AND trade_date <= :trade_date
                ORDER BY trade_date DESC, created_at DESC
                LIMIT 1
            """)
            with self.engine.connect() as conn:
                row = conn.execute(query, {"account_id": resolved_account_id, "trade_date": trade_date}).mappings().first()
            if row is not None:
                return AccountRiskSnapshot(
                    account_id=str(row["account_id"]),
                    trade_date=self._coerce_date(row["trade_date"]) or trade_date,
                    cash=float(row["cash"]),
                    equity=float(row["equity"]),
                    buying_power=float(row["buying_power"]),
                    high_watermark=float(row["high_watermark"]) if row.get("high_watermark") is not None else None,
                    daily_realized_pnl=float(row["daily_realized_pnl"]) if row.get("daily_realized_pnl") is not None else None,
                    daily_unrealized_pnl=float(row["daily_unrealized_pnl"]) if row.get("daily_unrealized_pnl") is not None else None,
                    daily_total_pnl=float(row["daily_total_pnl"]) if row.get("daily_total_pnl") is not None else None,
                    source="account_risk_snapshots",
                )
        return self._load_broker_snapshot_as_account_risk_snapshot(resolved_account_id, trade_date)

    def _load_broker_snapshot_as_account_risk_snapshot(
        self,
        account_id: str,
        trade_date: date,
    ) -> AccountRiskSnapshot | None:
        row, broker_columns = self._load_latest_broker_account_snapshot_row(
            account_id,
            trade_date,
            require_positive_equity=True,
        )
        if not broker_columns:
            return None

        where_clauses = ["account_id = :account_id", "DATE(created_at) <= :trade_date"]
        params: dict[str, Any] = {"account_id": account_id, "trade_date": trade_date}
        if "snapshot_kind" in broker_columns:
            where_clauses.append("snapshot_kind = :snapshot_kind")
            params["snapshot_kind"] = "preflight"
        # Hardening live : ignorer les snapshots dont l'equity est manquante ou ≤ 0
        # (cf. execution_engine.db_io.snapshot_broker_account & InvalidBrokerSnapshotError).
        where_clauses.append("equity IS NOT NULL AND equity > 0")

        high_watermark_stmt = text(
            f"""
            SELECT MAX(equity) AS high_watermark
            FROM broker_account_snapshots
            WHERE {' AND '.join(where_clauses)}
            """
        )
        with self.engine.connect() as conn:
            if row is None:
                LOGGER.warning(
                    "Aucun broker_account_snapshot exploitable (equity > 0) | account=%s trade_date=%s",
                    account_id,
                    trade_date,
                )
                return None
            high_watermark_row = conn.execute(high_watermark_stmt, params).mappings().first()

        equity = float(row["equity"])
        high_watermark = (
            float(high_watermark_row["high_watermark"])
            if high_watermark_row and high_watermark_row.get("high_watermark") is not None
            else equity
        )
        LOGGER.info(
            "Fallback account_risk_snapshot via broker_account_snapshots | account=%s trade_date=%s",
            account_id,
            trade_date,
        )
        return AccountRiskSnapshot(
            account_id=str(row["account_id"]),
            trade_date=self._coerce_date(row.get("created_at")) or trade_date,
            cash=float(row["cash"]),
            equity=equity,
            buying_power=float(row["buying_power"]),
            high_watermark=high_watermark,
            daily_realized_pnl=None,
            daily_unrealized_pnl=None,
            daily_total_pnl=None,
            source="broker_account_snapshots",
        )

    def load_equity_history(
        self,
        account_id: str | None,
        trade_date: date,
        lookback_days: int = 25,
    ) -> list[tuple[date, float]]:
        """Charge l'historique d'equity pour le rotation factor.

        Retourne une liste de ``(date, equity)`` triée par date ascendante
        sur les ``lookback_days`` jours calendaires précédant ``trade_date``.

        Sources essayées dans l'ordre :
        1. ``account_risk_snapshots``
        2. ``broker_account_snapshots`` (fallback)

        Parameters
        ----------
        account_id : str or None
            Identifiant du compte.
        trade_date : date
            Date de référence.
        lookback_days : int
            Nombre de jours calendaires de recul (défaut 25 ≈ 5 semaines).

        Returns
        -------
        list[tuple[date, float]]
            Liste de paires (date, equity), peut être vide.
        """
        resolved_account_id = account_id or "default"
        rows: list[tuple[date, float]] = []

        # Source 1 : account_risk_snapshots
        if self._get_table_columns("account_risk_snapshots"):
            query = text("""
                SELECT trade_date, equity
                FROM account_risk_snapshots
                WHERE account_id = :account_id
                  AND trade_date <= :trade_date
                  AND equity IS NOT NULL
                  AND equity > 0
                ORDER BY trade_date ASC
            """)
            with self.engine.connect() as conn:
                result = conn.execute(
                    query,
                    {"account_id": resolved_account_id, "trade_date": trade_date},
                ).mappings().all()
            for row in result:
                dt = self._coerce_date(row["trade_date"])
                if dt is not None:
                    rows.append((dt, float(row["equity"])))
            if rows:
                return rows

        # Source 2 : broker_account_snapshots (fallback)
        if self._get_table_columns("broker_account_snapshots"):
            query = text("""
                SELECT DATE(created_at) AS trade_date, equity
                FROM broker_account_snapshots
                WHERE account_id = :account_id
                  AND DATE(created_at) <= :trade_date
                  AND equity IS NOT NULL
                  AND equity > 0
                ORDER BY DATE(created_at) ASC
            """)
            with self.engine.connect() as conn:
                result = conn.execute(
                    query,
                    {"account_id": resolved_account_id, "trade_date": trade_date},
                ).mappings().all()
            for row in result:
                dt = self._coerce_date(row["trade_date"])
                if dt is not None:
                    rows.append((dt, float(row["equity"])))
            if rows:
                return rows

        LOGGER.warning(
            "load_equity_history: aucun snapshot equity trouvé pour account=%s date=%s",
            resolved_account_id,
            trade_date,
        )
        return rows

    def load_account_equity_breakdown(
        self,
        account_id: str | None,
        trade_date: date,
    ) -> dict[str, Any]:
        """Phase 5.1.a — Décompose l'equity du compte (cash / positions / dividendes).

        Sources :
          - ``broker_account_snapshots`` (snapshot le plus récent ≤ trade_date) → ``cash``,

            ``settled_cash``, ``equity``.
          - ``broker_positions_snapshots`` (snapshot le plus récent ≤ trade_date) →
            agrégat ``market_value`` long/short.
          - ``portfolio_cash_ledger`` → cumul ``dividend_credit`` filtré par ``account_id``.

        Retour : dict toujours peuplé. ``source="missing"`` si aucune table dispo.
        Best-effort : aucune exception ne remonte au CLI.
        """
        resolved_account_id = account_id or "default"
        breakdown: dict[str, Any] = {
            "account_id": resolved_account_id,
            "trade_date": trade_date.isoformat(),
            "cash": None,
            "settled_cash": None,
            "long_positions_value": None,
            "short_positions_value": None,
            "dividends_ledger": None,
            "total": None,
            "source": "missing",
            "snapshot_at": None,
        }

        # 1) account snapshot
        try:
            row, broker_columns = self._load_latest_broker_account_snapshot_row(
                resolved_account_id,
                trade_date,
                require_positive_equity=True,
            )
            if broker_columns and row is not None:
                breakdown["cash"] = float(row["cash"]) if row.get("cash") is not None else None
                breakdown["settled_cash"] = (
                    float(row["settled_cash"]) if row.get("settled_cash") is not None else None
                )
                if row.get("created_at") is not None:
                    breakdown["snapshot_at"] = str(row["created_at"])
                breakdown["source"] = "broker_account_snapshots"
        except Exception:
            LOGGER.warning("load_account_equity_breakdown: account snapshot fail", exc_info=True)

        # 2) positions snapshot (split long/short)
        try:
            pos_columns = self._get_table_columns("broker_positions_snapshots")
            if pos_columns:
                has_account_id = "account_id" in pos_columns
                where_clause = "DATE(created_at) <= :trade_date"
                params: dict[str, Any] = {"trade_date": trade_date}
                if has_account_id:
                    where_clause += " AND account_id = :account_id"
                    params["account_id"] = resolved_account_id
                stmt = text(
                    f"""
                    SELECT
                        SUM(CASE WHEN qty >= 0 THEN COALESCE(market_value, 0) ELSE 0 END) AS long_value,
                        SUM(CASE WHEN qty <  0 THEN COALESCE(market_value, 0) ELSE 0 END) AS short_value
                    FROM broker_positions_snapshots
                    WHERE {where_clause}
                      AND created_at = (
                          SELECT MAX(created_at) FROM broker_positions_snapshots
                          WHERE {where_clause}
                      )
                    """
                )
                with self.engine.connect() as conn:
                    row = conn.execute(stmt, params).mappings().first()
                if row is not None:
                    breakdown["long_positions_value"] = (
                        float(row["long_value"]) if row.get("long_value") is not None else 0.0
                    )
                    breakdown["short_positions_value"] = (
                        float(row["short_value"]) if row.get("short_value") is not None else 0.0
                    )
        except Exception:
            LOGGER.warning("load_account_equity_breakdown: positions fail", exc_info=True)

        # 3) dividends ledger
        try:
            ledger_columns = self._get_table_columns("portfolio_cash_ledger")
            if ledger_columns:
                has_account_id = "account_id" in ledger_columns
                has_created_at = "created_at" in ledger_columns
                where_clause = "entry_type = 'dividend_credit'"
                params: dict[str, Any] = {}
                if has_account_id:
                    where_clause += " AND (account_id = :account_id OR account_id IS NULL)"
                    params["account_id"] = resolved_account_id
                if has_created_at:
                    where_clause += " AND DATE(created_at) <= :trade_date"
                    params["trade_date"] = trade_date
                stmt = text(f"SELECT COALESCE(SUM(amount), 0) AS total FROM portfolio_cash_ledger WHERE {where_clause}")
                with self.engine.connect() as conn:
                    row = conn.execute(stmt, params).mappings().first()
                if row is not None:
                    breakdown["dividends_ledger"] = float(row["total"])
        except Exception:
            LOGGER.warning("load_account_equity_breakdown: ledger fail", exc_info=True)

        # 4) total = cash + long - |short| (dividends already credited to cash)
        cash = breakdown["cash"] or 0.0
        long_v = breakdown["long_positions_value"] or 0.0
        short_v = breakdown["short_positions_value"] or 0.0
        if breakdown["cash"] is not None or breakdown["long_positions_value"] is not None:
            breakdown["total"] = round(cash + long_v + short_v, 2)
        return breakdown

    def load_latest_empirical_risk_calibration(
        self,
        trade_date: date,
        *,
        run_id: str | None = None,
        market_regime_mode: str | None = None,
        horizon_days: int | None = None,
        lookback_months: int | None = None,
    ) -> dict[str, Any] | None:
        """Charge le dernier run de calibration empirique risk applicable.

        Best-effort : retourne ``None`` si la table n'existe pas, si aucun run ne
        matche, ou si le JSON des poids est illisible.
        """
        table_columns = self._get_table_columns("weights_calibration_runs")
        if not table_columns:
            return None
        requested_market_regime_mode = str(market_regime_mode or "").strip().lower() or "all"
        requested_horizon_days = int(horizon_days) if horizon_days is not None else None
        requested_lookback_months = int(lookback_months) if lookback_months is not None else None
        params: dict[str, Any] = {"scope": "risk"}
        where_clauses = ["scope = :scope"]
        select_columns = [
            "run_id",
            "calibrated_at",
            "window_start",
            "window_end",
            "metric_name",
            "metric_value",
            "best_weights",
            "schema_version",
        ]
        has_market_regime_mode = "market_regime_mode" in table_columns
        optional_columns = [
            "market_regime_mode",
            "calibration_batch_id",
            "segment_key",
            "horizon_days",
            "lookback_months",
            "distinct_snapshot_days",
            "distinct_symbols",
            "eligible_for_live",
            "eligibility_reason",
        ]
        select_columns.extend(column for column in optional_columns if column in table_columns)
        if run_id is not None:
            where_clauses.append("run_id = :run_id")
            params["run_id"] = run_id
        else:
            where_clauses.append("window_end <= :trade_date")
            params["trade_date"] = trade_date
        query = text(
            f"""
            SELECT {', '.join(select_columns)}
            FROM weights_calibration_runs
            WHERE {' AND '.join(where_clauses)}
            ORDER BY window_end DESC, calibrated_at DESC, run_id DESC
            LIMIT 100
            """
        )
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception:
            LOGGER.warning("Impossible de charger weights_calibration_runs pour trade_date=%s", trade_date, exc_info=True)
            return None
        if not rows:
            return None
        has_eligible_for_live = "eligible_for_live" in table_columns
        requested_segment_key = None
        if requested_horizon_days is not None and requested_lookback_months is not None:
            requested_segment_key = (
                f"regime={requested_market_regime_mode}"
                f"|horizon={requested_horizon_days}d"
                f"|window={requested_lookback_months}m"
            )

        def _parse_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
            raw_best_weights = row.get("best_weights")
            if isinstance(raw_best_weights, Mapping):
                best_weights = dict(raw_best_weights)
            elif isinstance(raw_best_weights, str):
                try:
                    parsed = json.loads(raw_best_weights)
                except json.JSONDecodeError:
                    LOGGER.warning("best_weights illisible pour weights_calibration_runs.run_id=%s", row.get("run_id"))
                    return None
                if not isinstance(parsed, dict):
                    return None
                best_weights = parsed
            else:
                best_weights = {}
            resolved_market_regime_mode = (
                str(row.get("market_regime_mode") or "").strip().lower() or "all"
                if has_market_regime_mode
                else "all"
            )
            return {
                "run_id": str(row.get("run_id") or "").strip() or None,
                "calibrated_at": str(row.get("calibrated_at") or "").strip() or None,
                "window_start": self._coerce_date(row.get("window_start")),
                "window_end": self._coerce_date(row.get("window_end")),
                "metric_name": str(row.get("metric_name") or "").strip() or None,
                "metric_value": float(row["metric_value"]) if row.get("metric_value") is not None else None,
                "schema_version": int(row["schema_version"]) if row.get("schema_version") is not None else None,
                "market_regime_mode": resolved_market_regime_mode,
                "calibration_batch_id": str(row.get("calibration_batch_id") or "").strip() or None,
                "segment_key": str(row.get("segment_key") or "").strip() or None,
                "horizon_days": int(row["horizon_days"]) if row.get("horizon_days") is not None else None,
                "lookback_months": int(row["lookback_months"]) if row.get("lookback_months") is not None else None,
                "distinct_snapshot_days": int(row["distinct_snapshot_days"]) if row.get("distinct_snapshot_days") is not None else None,
                "distinct_symbols": int(row["distinct_symbols"]) if row.get("distinct_symbols") is not None else None,
                "eligible_for_live": (
                    bool(row.get("eligible_for_live")) if has_eligible_for_live else True
                ),
                "eligibility_reason": str(row.get("eligibility_reason") or "").strip() or None,
                "best_weights": best_weights,
                "source": "weights_calibration_runs",
            }

        parsed_rows = [parsed for row in rows if (parsed := _parse_row(row)) is not None]
        if not parsed_rows:
            return None
        for index, row in enumerate(parsed_rows):
            row["_order_index"] = index
        if run_id is not None:
            selected = parsed_rows[0]
            resolved_segment_key = _build_runtime_segment_key(
                market_regime_mode=str(selected.get("market_regime_mode") or "all"),
                horizon_days=_optional_int(selected.get("horizon_days")),
                lookback_months=_optional_int(selected.get("lookback_months")),
            )
            status = "selected" if selected.get("eligible_for_live", True) else "blocked_by_governance"
            selected["requested_market_regime_mode"] = requested_market_regime_mode
            selected["requested_horizon_days"] = requested_horizon_days
            selected["requested_lookback_months"] = requested_lookback_months
            selected["requested_segment_key"] = requested_segment_key
            selected["market_regime_fallback_used"] = False
            selected["fallback_level"] = "exact_run_id"
            selected["status"] = status
            selected["fallback_policy_source"] = "explicit_run_id"
            selected["fallback_reason"] = (
                f"niveau=exact_run_id; status={status}; requested_run_id={run_id}; resolved={resolved_segment_key or selected.get('run_id')}"
            )
            selected["fallback_journal"] = [
                {
                    "rank": 1,
                    "level": "exact_run_id",
                    "eligible_candidates": 1 if selected.get("eligible_for_live", True) else 0,
                    "blocked_candidates": 0 if selected.get("eligible_for_live", True) else 1,
                    "outcome": "selected" if selected.get("eligible_for_live", True) else "blocked_candidate_available",
                    "selected": True,
                    "selected_status": status,
                    "selected_run_id": selected.get("run_id"),
                    "selected_segment_key": resolved_segment_key,
                }
            ]
            return selected

        def _matches_regime(row: Mapping[str, Any], regime_mode: str) -> bool:
            return str(row.get("market_regime_mode") or "all").strip().lower() == regime_mode

        def _matches_exact_horizon(row: Mapping[str, Any]) -> bool:
            return requested_horizon_days is None or _optional_int(row.get("horizon_days")) == requested_horizon_days

        def _matches_exact_lookback(row: Mapping[str, Any]) -> bool:
            return requested_lookback_months is None or _optional_int(row.get("lookback_months")) == requested_lookback_months

        def _horizon_distance(row: Mapping[str, Any]) -> int:
            value = _optional_int(row.get("horizon_days"))
            if requested_horizon_days is None:
                return 0
            if value is None:
                return 10_000
            return abs(value - requested_horizon_days)

        def _lookback_distance(row: Mapping[str, Any]) -> int:
            value = _optional_int(row.get("lookback_months"))
            if requested_lookback_months is None:
                return 0
            if value is None:
                return 10_000
            return abs(value - requested_lookback_months)

        def _sorted_rows(
            candidates: list[dict[str, Any]],
            *,
            sort_by_horizon: bool = False,
            sort_by_lookback: bool = False,
        ) -> list[dict[str, Any]]:
            return sorted(
                candidates,
                key=lambda row: (
                    _horizon_distance(row) if sort_by_horizon else 0,
                    _lookback_distance(row) if sort_by_lookback else 0,
                    int(row.get("_order_index") or 0),
                ),
            )

        def _level_candidates(
            rows_subset: list[dict[str, Any]],
            *,
            regime_mode: str,
            exact_horizon: bool | None = None,
            exact_lookback: bool | None = None,
            sort_by_horizon: bool = False,
            sort_by_lookback: bool = False,
        ) -> list[dict[str, Any]]:
            filtered_subset = [row for row in rows_subset if _matches_regime(row, regime_mode)]
            if exact_horizon is not None:
                filtered_subset = [row for row in filtered_subset if _matches_exact_horizon(row) is exact_horizon]
            if exact_lookback is not None:
                filtered_subset = [row for row in filtered_subset if _matches_exact_lookback(row) is exact_lookback]
            return _sorted_rows(
                filtered_subset,
                sort_by_horizon=sort_by_horizon,
                sort_by_lookback=sort_by_lookback,
            )

        def _rows_for_level(rows_subset: list[dict[str, Any]], level_name: str) -> list[dict[str, Any]]:
            if level_name == "exact_segment":
                return _level_candidates(
                    rows_subset,
                    regime_mode=requested_market_regime_mode,
                    exact_horizon=True,
                    exact_lookback=True,
                )
            if level_name == "regime_all":
                return _level_candidates(
                    rows_subset,
                    regime_mode="all",
                    exact_horizon=True,
                    exact_lookback=True,
                )
            if level_name == "same_regime_nearest_window":
                return _level_candidates(
                    rows_subset,
                    regime_mode=requested_market_regime_mode,
                    exact_horizon=True,
                    exact_lookback=False,
                    sort_by_lookback=True,
                )
            if level_name == "regime_all_nearest_window":
                return _level_candidates(
                    rows_subset,
                    regime_mode="all",
                    exact_horizon=True,
                    exact_lookback=False,
                    sort_by_lookback=True,
                )
            if level_name == "same_regime_nearest_horizon":
                return _level_candidates(
                    rows_subset,
                    regime_mode=requested_market_regime_mode,
                    exact_horizon=False,
                    exact_lookback=True,
                    sort_by_horizon=True,
                )
            if level_name == "regime_all_nearest_horizon":
                return _level_candidates(
                    rows_subset,
                    regime_mode="all",
                    exact_horizon=False,
                    exact_lookback=True,
                    sort_by_horizon=True,
                )
            if level_name == "same_regime_nearest_segment":
                return _level_candidates(
                    rows_subset,
                    regime_mode=requested_market_regime_mode,
                    exact_horizon=False,
                    exact_lookback=False,
                    sort_by_horizon=True,
                    sort_by_lookback=True,
                )
            if level_name == "regime_all_nearest_segment":
                return _level_candidates(
                    rows_subset,
                    regime_mode="all",
                    exact_horizon=False,
                    exact_lookback=False,
                    sort_by_horizon=True,
                    sort_by_lookback=True,
                )
            return []

        def _resolved_segment_key(row: Mapping[str, Any]) -> str | None:
            return str(row.get("segment_key") or "").strip() or _build_runtime_segment_key(
                market_regime_mode=str(row.get("market_regime_mode") or "all"),
                horizon_days=_optional_int(row.get("horizon_days")),
                lookback_months=_optional_int(row.get("lookback_months")),
            )

        eligible_rows = [row for row in parsed_rows if row.get("eligible_for_live", True)]
        blocked_rows = [row for row in parsed_rows if not row.get("eligible_for_live", True)]
        fallback_levels, fallback_policy_source = _load_empirical_calibration_fallback_levels()
        fallback_journal: list[dict[str, Any]] = []
        blocked_candidate = None
        blocked_level = None
        blocked_rank = None
        selected = None
        fallback_level = "static_weights"
        status = "missing"

        for rank, level_name in enumerate(fallback_levels, start=1):
            eligible_candidates = _rows_for_level(eligible_rows, level_name)
            blocked_candidates = _rows_for_level(blocked_rows, level_name)
            outcome = "selected"
            if not eligible_candidates and blocked_candidates:
                outcome = "blocked_candidate_available"
            elif not eligible_candidates:
                outcome = "no_candidate"
            journal_entry: dict[str, Any] = {
                "rank": rank,
                "level": level_name,
                "eligible_candidates": len(eligible_candidates),
                "blocked_candidates": len(blocked_candidates),
                "outcome": outcome,
                "selected": False,
            }
            if eligible_candidates:
                selected = eligible_candidates[0]
                fallback_level = level_name
                status = "selected"
                journal_entry.update(
                    {
                        "selected": True,
                        "selected_status": status,
                        "selected_run_id": selected.get("run_id"),
                        "selected_segment_key": _resolved_segment_key(selected),
                    }
                )
                fallback_journal.append(journal_entry)
                break
            if blocked_candidates and blocked_candidate is None:
                blocked_candidate = blocked_candidates[0]
                blocked_level = level_name
                blocked_rank = rank
            fallback_journal.append(journal_entry)

        if selected is None and blocked_candidate is not None:
            selected = blocked_candidate
            fallback_level = f"blocked_governance_{blocked_level}"
            status = "blocked_by_governance"
            if blocked_rank is not None and 0 < blocked_rank <= len(fallback_journal):
                fallback_journal[blocked_rank - 1].update(
                    {
                        "selected": True,
                        "selected_status": status,
                        "selected_run_id": selected.get("run_id"),
                        "selected_segment_key": _resolved_segment_key(selected),
                    }
                )
        if selected is None:
            return None
        resolved_segment_key = _resolved_segment_key(selected)
        selected["requested_market_regime_mode"] = requested_market_regime_mode
        selected["requested_horizon_days"] = requested_horizon_days
        selected["requested_lookback_months"] = requested_lookback_months
        selected["requested_segment_key"] = requested_segment_key
        selected["market_regime_fallback_used"] = fallback_level not in {"exact_segment", "exact_run_id"}
        selected["fallback_level"] = fallback_level
        selected["status"] = status
        selected["fallback_policy_source"] = fallback_policy_source
        selected["fallback_journal"] = fallback_journal
        selected["fallback_reason"] = (
            f"niveau={fallback_level}; status={status}; requested={requested_segment_key or requested_market_regime_mode}; "
            f"resolved={resolved_segment_key or selected.get('run_id')}; policy={fallback_policy_source}"
        )
        return selected

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    def load_risk_decisions_for_date(
        self,
        trade_date: date,
        *,
        account_id: str | None = None,
    ) -> pd.DataFrame:
        """Sprint S9 — Charge les décisions risk live d'un jour J.

        Sélectionne le DERNIER ``run_id`` du jour pour le compte demandé
        (ou tous comptes si ``account_id`` est ``None``). Retourne un
        DataFrame normalisé pour la comparaison de parité (cf.
        :mod:`backtesting.parity`).
        """
        params: dict[str, Any] = {"trade_date": trade_date}
        account_clause = ""
        if account_id is not None:
            account_clause = " AND account_id = :account_id"
            params["account_id"] = account_id
        query = text(
            f"""
            SELECT run_id, trade_date, symbol, decision, approved_shares,
                   target_weight, conviction_score, predicted_proba,
                   score_used, score_source, sector, account_id
            FROM risk_decisions
            WHERE trade_date = :trade_date{account_clause}
              AND run_id = (
                  SELECT run_id FROM risk_decisions
                  WHERE trade_date = :trade_date{account_clause}
                  ORDER BY created_at DESC LIMIT 1
              )
            """
        )
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception as exc:  # pragma: no cover - best effort lecture
            LOGGER.warning("[parity] lecture risk_decisions impossible: %s", exc)
            return pd.DataFrame()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])

    def load_risk_decisions_for_run_id(
        self,
        run_id: str,
        *,
        account_id: str | None = None,
    ) -> pd.DataFrame:
        """Charge les décisions ``risk_decisions`` d'un ``run_id`` donné."""
        params: dict[str, Any] = {"run_id": run_id}
        account_clause = ""
        if account_id is not None:
            account_clause = " AND account_id = :account_id"
            params["account_id"] = account_id
        query = text(
            f"""
            SELECT run_id, trade_date, symbol, decision, approved_shares,
                   target_weight, conviction_score, predicted_proba,
                   score_used, score_source, sector, account_id, entry_price
            FROM risk_decisions
            WHERE run_id = :run_id{account_clause}
            ORDER BY COALESCE(candidate_rank, 999999), created_at DESC, symbol ASC
            """
        )
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(query, params).mappings().all()
        except Exception as exc:  # pragma: no cover - best effort lecture
            LOGGER.warning("[shadow_compare] lecture risk_decisions impossible pour run_id=%s: %s", run_id, exc)
            return pd.DataFrame()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(row) for row in rows])

    def write_risk_decisions(self, records: list[dict[str, Any]], account_id: str | None = None) -> int:
        """Insère dans risk_decisions via le schéma canonique Sprint 1."""
        if not records:
            return 0
        canonical_columns = [
            "run_id", "trade_date", "symbol", "decision", "reason", "reason_code", "score_used",
            "score_source", "entry_price", "atr_20", "proposed_shares", "approved_shares",
            "target_weight", "sector", "side", "conviction_score", "predicted_proba",
            "historical_win_rate", "effective_probability", "kelly_fraction",
            "sizing_method", "correlation_blocker", "correlation_value",
            "company_idio_score", "macro_regime_score",
            "company_idio_signal_norm", "macro_regime_signal_norm",
            "company_idio_component", "macro_regime_component", "quant_component",
            "walk_forward_sentiment_weight", "walk_forward_macro_weight", "walk_forward_quant_weight",
            "calibration_run_id", "calibration_source", "account_id", "candidate_rank",
            "selector_signal_mode", "selection_explanation", "selector_earnings_blackout",
            "decision_rank", "target_notional", "stop_price_initial", "risk_per_share",
            "risk_budget_dollars", "initial_risk_dollars", "score_snapshot_date",
            "price_asof_date", "atr_asof_date", "prediction_asof_date", "ml_metrics_asof_date",
        ]
        available_columns = self._get_table_columns("risk_decisions")
        insert_columns = [column for column in canonical_columns if not available_columns or column in available_columns]
        normalized_records = []
        for record in records:
            payload = {column: record.get(column) for column in insert_columns}
            if "account_id" in insert_columns:
                payload["account_id"] = record.get("account_id") or account_id or "default"
            normalized_records.append(payload)
        stmt = text(
            "INSERT INTO risk_decisions ("
            + ", ".join(insert_columns)
            + ") VALUES ("
            + ", ".join(f":{column}" for column in insert_columns)
            + ")"
        )
        with self.engine.begin() as conn:
            conn.execute(stmt, normalized_records)
        return len(records)

    def write_portfolio_targets(self, records: list[dict[str, Any]], account_id: str | None = None) -> int:
        """Insère dans portfolio_targets via le schéma canonique Sprint 1."""
        if not records:
            return 0
        canonical_columns = [
            "run_id", "trade_date", "symbol", "shares", "entry_price", "atr_20", "target_weight",
            "sector", "side", "score_used", "score_source", "reason_code", "conviction_score", "sizing_method",
            "kelly_fraction", "company_idio_score", "macro_regime_score",
            "company_idio_signal_norm", "macro_regime_signal_norm",
            "company_idio_component", "macro_regime_component", "quant_component",
            "walk_forward_sentiment_weight", "walk_forward_macro_weight", "walk_forward_quant_weight",
            "calibration_run_id", "calibration_source", "account_id", "candidate_rank",
            "selector_signal_mode", "selection_explanation", "selector_earnings_blackout", "decision_rank",
            "target_notional", "stop_price_initial", "risk_per_share", "risk_budget_dollars",
            "initial_risk_dollars", "price_asof_date", "atr_asof_date",
        ]
        available_columns = self._get_table_columns("portfolio_targets")
        insert_columns = [column for column in canonical_columns if not available_columns or column in available_columns]
        normalized_records = []
        for record in records:
            payload = {column: record.get(column) for column in insert_columns}
            if "account_id" in insert_columns:
                payload["account_id"] = record.get("account_id") or account_id or "default"
            normalized_records.append(payload)
        stmt = text(
            "INSERT INTO portfolio_targets ("
            + ", ".join(insert_columns)
            + ") VALUES ("
            + ", ".join(f":{column}" for column in insert_columns)
            + ")"
        )
        with self.engine.begin() as conn:
            conn.execute(stmt, normalized_records)
        return len(records)
