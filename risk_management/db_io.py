"""Accès base de données pour le module risk_management."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from common.capital_presets import DEFAULT_CAPITAL_PRESET_KEY
from database.connection import get_sqlalchemy_engine
from risk_management.config import RiskConfig
from risk_management.ml_gate import resolve_ml_gate_state
from risk_management.models import AccountRiskSnapshot, CandidateScore, PredictionInfo, PriceInfo, WinRateInfo

LOGGER = logging.getLogger(__name__)


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
        optional_text_columns = ["calibration_run_id", "calibration_source"]
        optional_selects = [
            f"s.{column}" if column in stock_score_columns else f"NULL AS {column}"
            for column in [*optional_float_columns, *optional_text_columns]
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

    def load_prices(self, symbols: list[str], atr_window: int = 20, trade_date: date | None = None) -> dict[str, PriceInfo]:
        """Compatibilité API : charge les prix PIT à la date demandée."""
        return self.load_prices_asof(symbols, trade_date or date.today(), atr_window=atr_window)

    def load_prices_asof(self, symbols: list[str], trade_date: date, atr_window: int = 20) -> dict[str, PriceInfo]:
        """Charge le dernier close et l'ATR depuis stock_bars_daily à la date de trade."""
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
                    ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY `date` DESC) AS rn
                FROM stock_bars_daily
                WHERE symbol IN ({placeholders})
                  AND `date` <= :trade_date
            )
            SELECT symbol, trade_day, close_price, high_price, low_price
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
        for sym, sym_rows in grouped.items():
            if not sym_rows:
                continue
            last_row = sym_rows[-1]
            last_close = float(last_row["close_price"])
            price_asof_date = self._coerce_date(last_row.get("trade_day"))

            tr_values: list[float] = []
            for idx in range(1, len(sym_rows)):
                prev_close = float(sym_rows[idx - 1]["close_price"])
                high_price = float(sym_rows[idx]["high_price"])
                low_price = float(sym_rows[idx]["low_price"])
                true_range = max(high_price - low_price, abs(high_price - prev_close), abs(low_price - prev_close))
                tr_values.append(true_range)

            atr_val = None
            atr_asof_date = None
            if len(tr_values) >= atr_window:
                atr_window_values = tr_values[-atr_window:]
                atr_val = sum(atr_window_values) / atr_window
                atr_asof_date = price_asof_date

            result[sym] = PriceInfo(
                symbol=sym,
                last_close=last_close,
                atr_20=atr_val,
                price_asof_date=price_asof_date,
                atr_asof_date=atr_asof_date,
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
                )
        return self._load_broker_snapshot_as_account_risk_snapshot(resolved_account_id, trade_date)

    def _load_broker_snapshot_as_account_risk_snapshot(
        self,
        account_id: str,
        trade_date: date,
    ) -> AccountRiskSnapshot | None:
        broker_columns = self._get_table_columns("broker_account_snapshots")
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
        order_by = "created_at DESC"
        if "id" in broker_columns:
            order_by += ", id DESC"

        latest_stmt = text(
            f"""
            SELECT account_id, cash, equity, buying_power, created_at
            FROM broker_account_snapshots
            WHERE {' AND '.join(where_clauses)}
            ORDER BY {order_by}
            LIMIT 1
            """
        )
        high_watermark_stmt = text(
            f"""
            SELECT MAX(equity) AS high_watermark
            FROM broker_account_snapshots
            WHERE {' AND '.join(where_clauses)}
            """
        )
        with self.engine.connect() as conn:
            row = conn.execute(latest_stmt, params).mappings().first()
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
        )

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
            if self._get_table_columns("broker_account_snapshots"):
                stmt = text(
                    """
                    SELECT equity, cash, settled_cash, created_at
                    FROM broker_account_snapshots
                    WHERE account_id = :account_id
                      AND DATE(created_at) <= :trade_date
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """
                )
                with self.engine.connect() as conn:
                    row = conn.execute(
                        stmt,
                        {"account_id": resolved_account_id, "trade_date": trade_date},
                    ).mappings().first()
                if row is not None:
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
                where_clause = "entry_type = 'dividend_credit'"
                params = {}
                if has_account_id:
                    where_clause += " AND (account_id = :account_id OR account_id IS NULL)"
                    params["account_id"] = resolved_account_id
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

    def write_risk_decisions(self, records: list[dict[str, Any]], account_id: str | None = None) -> int:
        """Insère dans risk_decisions via le schéma canonique Sprint 1."""
        if not records:
            return 0
        canonical_columns = [
            "run_id", "trade_date", "symbol", "decision", "reason", "score_used",
            "score_source", "entry_price", "atr_20", "proposed_shares", "approved_shares",
            "target_weight", "sector", "conviction_score", "predicted_proba",
            "historical_win_rate", "effective_probability", "kelly_fraction",
            "sizing_method", "correlation_blocker", "correlation_value",
            "company_idio_score", "macro_regime_score",
            "company_idio_signal_norm", "macro_regime_signal_norm",
            "company_idio_component", "macro_regime_component", "quant_component",
            "walk_forward_sentiment_weight", "walk_forward_macro_weight", "walk_forward_quant_weight",
            "calibration_run_id", "calibration_source", "account_id", "candidate_rank",
            "decision_rank", "target_notional", "stop_price_initial", "risk_per_share",
            "risk_budget_dollars", "initial_risk_dollars", "score_snapshot_date",
            "price_asof_date", "atr_asof_date", "prediction_asof_date", "ml_metrics_asof_date",
        ]
        normalized_records = [
            {column: record.get(column) for column in canonical_columns} | {"account_id": record.get("account_id") or account_id or "default"}
            for record in records
        ]
        stmt = text("""
            INSERT INTO risk_decisions
                (run_id, trade_date, symbol, decision, reason, score_used,
                 score_source, entry_price, atr_20, proposed_shares, approved_shares,
                 target_weight, sector, conviction_score, predicted_proba,
                 historical_win_rate, effective_probability, kelly_fraction,
                 sizing_method, correlation_blocker, correlation_value,
                 company_idio_score, macro_regime_score,
                 company_idio_signal_norm, macro_regime_signal_norm,
                 company_idio_component, macro_regime_component, quant_component,
                 walk_forward_sentiment_weight, walk_forward_macro_weight, walk_forward_quant_weight,
                 calibration_run_id, calibration_source, account_id, candidate_rank,
                 decision_rank, target_notional, stop_price_initial, risk_per_share,
                 risk_budget_dollars, initial_risk_dollars, score_snapshot_date,
                 price_asof_date, atr_asof_date, prediction_asof_date, ml_metrics_asof_date)
            VALUES
                (:run_id, :trade_date, :symbol, :decision, :reason, :score_used,
                 :score_source, :entry_price, :atr_20, :proposed_shares, :approved_shares,
                 :target_weight, :sector, :conviction_score, :predicted_proba,
                 :historical_win_rate, :effective_probability, :kelly_fraction,
                 :sizing_method, :correlation_blocker, :correlation_value,
                 :company_idio_score, :macro_regime_score,
                 :company_idio_signal_norm, :macro_regime_signal_norm,
                 :company_idio_component, :macro_regime_component, :quant_component,
                 :walk_forward_sentiment_weight, :walk_forward_macro_weight, :walk_forward_quant_weight,
                 :calibration_run_id, :calibration_source, :account_id, :candidate_rank,
                 :decision_rank, :target_notional, :stop_price_initial, :risk_per_share,
                 :risk_budget_dollars, :initial_risk_dollars, :score_snapshot_date,
                 :price_asof_date, :atr_asof_date, :prediction_asof_date, :ml_metrics_asof_date)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, normalized_records)
        return len(records)

    def write_portfolio_targets(self, records: list[dict[str, Any]], account_id: str | None = None) -> int:
        """Insère dans portfolio_targets via le schéma canonique Sprint 1."""
        if not records:
            return 0
        canonical_columns = [
            "run_id", "trade_date", "symbol", "shares", "entry_price", "atr_20", "target_weight",
            "sector", "score_used", "score_source", "conviction_score", "sizing_method",
            "kelly_fraction", "company_idio_score", "macro_regime_score",
            "company_idio_signal_norm", "macro_regime_signal_norm",
            "company_idio_component", "macro_regime_component", "quant_component",
            "walk_forward_sentiment_weight", "walk_forward_macro_weight", "walk_forward_quant_weight",
            "calibration_run_id", "calibration_source", "account_id", "decision_rank",
            "target_notional", "stop_price_initial", "risk_per_share", "risk_budget_dollars",
            "initial_risk_dollars", "price_asof_date", "atr_asof_date",
        ]
        normalized_records = [
            {column: record.get(column) for column in canonical_columns} | {"account_id": record.get("account_id") or account_id or "default"}
            for record in records
        ]
        stmt = text("""
            INSERT INTO portfolio_targets
                (run_id, trade_date, symbol, shares, entry_price, atr_20, target_weight,
                 sector, score_used, score_source, conviction_score, sizing_method,
                 kelly_fraction, company_idio_score, macro_regime_score,
                 company_idio_signal_norm, macro_regime_signal_norm,
                 company_idio_component, macro_regime_component, quant_component,
                 walk_forward_sentiment_weight, walk_forward_macro_weight, walk_forward_quant_weight,
                 calibration_run_id, calibration_source, account_id, decision_rank,
                 target_notional, stop_price_initial, risk_per_share, risk_budget_dollars,
                 initial_risk_dollars, price_asof_date, atr_asof_date)
            VALUES
                (:run_id, :trade_date, :symbol, :shares, :entry_price, :atr_20, :target_weight,
                 :sector, :score_used, :score_source, :conviction_score, :sizing_method,
                 :kelly_fraction, :company_idio_score, :macro_regime_score,
                 :company_idio_signal_norm, :macro_regime_signal_norm,
                 :company_idio_component, :macro_regime_component, :quant_component,
                 :walk_forward_sentiment_weight, :walk_forward_macro_weight, :walk_forward_quant_weight,
                 :calibration_run_id, :calibration_source, :account_id, :decision_rank,
                 :target_notional, :stop_price_initial, :risk_per_share, :risk_budget_dollars,
                 :initial_risk_dollars, :price_asof_date, :atr_asof_date)
        """)
        with self.engine.begin() as conn:
            conn.execute(stmt, normalized_records)
        return len(records)
