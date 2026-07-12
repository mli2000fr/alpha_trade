"""CLI standalone pour le module risk_management."""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timezone
from enum import StrEnum
from pathlib import Path

import pandas as pd

from common.quantity_utils import format_share_quantity, normalize_share_quantity
from common.capital_presets import (
    build_risk_config_kwargs_from_preset,
    resolve_capital_preset_for_equity,
)
from common.config_loader import load_config
from common.utils import configure_root_logging
from core.run_summary import attach_live_progress, attach_schema_version
from database.macro_indicators import persist_market_macro_snapshot_daily
from database.run_business_summaries import emit_run_summary, persist_run_business_summary
from risk_management.audit import (
    build_run_id,
    persist_decision_audit_log,
    persist_decisions,
    persist_portfolio_targets,
)
from risk_management.circuit_breaker import CircuitBreaker, PnLSnapshot
from risk_management.config import RiskConfig
from risk_management.db_io import RiskRepository
from risk_management.live_pipeline_guards import (
    MlCoverageGateDecision,
    VolTargetDecision,
    apply_vol_target_to_risk_config,
    evaluate_ml_coverage_gate,
    evaluate_vol_target,
)
from risk_management.models import SelectionScore, PortfolioEntry
from risk_management.portfolio_builder import PortfolioBuilder

LOGGER = logging.getLogger(__name__)

_VOL_TARGET_BENCHMARK_SYMBOL = "SPY"


class RiskRunMode(StrEnum):
    """Mode d'exécution du calcul de risque avant remise à l'executor."""

    SHADOW = "shadow"
    PAPER = "paper"
    LIVE = "live"


def _emit_live_progress(
    summary: dict[str, object],
    *,
    current: int,
    total: int,
    label: str,
    phase: str,
    item: str | None = None,
    unit: str = "étapes",
) -> None:
    emit_run_summary(
        attach_live_progress(
            summary,
            current=current,
            total=total,
            label=label,
            phase=phase,
            unit=unit,
            item=item,
        )
    )


def _resolve_market_regime_snapshot(
    trade_date: date,
    effective_equity: float,
    repo: RiskRepository,
) -> object | None:
    """Construit le snapshot de régime live si la couche est activée."""
    try:
        from service.market import (
            DbSentimentScoreProvider,
            build_default_macro_provider,
            build_snapshot,
            load_regime_state,
            parse_market_regimes,
            save_regime_state,
        )
    except Exception:
        LOGGER.warning("Couche service.market indisponible pour risk_management.", exc_info=True)
        return None

    try:
        yaml_cfg = load_config()
        market_regimes_cfg = parse_market_regimes((yaml_cfg or {}).get("market_regimes"))
        if not market_regimes_cfg.enabled:
            return None
        macro_provider = build_default_macro_provider(yaml_cfg)
        sentiment_provider = DbSentimentScoreProvider(trade_date, engine=getattr(repo, "engine", None))
        previous_state = load_regime_state()
        snapshot = build_snapshot(
            trade_date,
            config=market_regimes_cfg,
            equity=float(effective_equity),
            execution_context="live",
            macro_provider=macro_provider,
            sentiment_score_provider=sentiment_provider,
            previous_state=previous_state,
        )
        save_regime_state(getattr(snapshot, "next_state", None))
        return snapshot
    except Exception:
        LOGGER.warning("Construction du snapshot de régime impossible côté risk_management.", exc_info=True)
        return None


def _serialize_market_regime_snapshot(snapshot: object | None) -> dict[str, object] | None:
    """Sérialise un snapshot de régime pour le run_summary."""
    if snapshot is None:
        return None
    payload: object | None = None
    if hasattr(snapshot, "to_summary_dict"):
        payload = snapshot.to_summary_dict()
    elif hasattr(snapshot, "to_dict"):
        payload = snapshot.to_dict()
    elif isinstance(snapshot, dict):
        payload = snapshot
    return dict(payload) if isinstance(payload, dict) else None


def _evaluate_regime_transition(snapshot: object | None) -> object | None:
    """Évalue la policy risque à partir du snapshot de régime déjà PIT."""
    if snapshot is None:
        return None
    try:
        from risk_management.regime_state_machine import RegimeState, RegimeStateMachine

        previous_mode = str(
            getattr(snapshot, "previous_mode", None)
            or getattr(snapshot, "mode", "normal")
            or "normal"
        )
        previous_state = RegimeState.from_regime_mode(previous_mode)
        return RegimeStateMachine().evaluate_from_snapshot(previous_state, snapshot)
    except Exception:
        LOGGER.warning("Évaluation de transition régime impossible côté risk_management.", exc_info=True)
        return None


def _load_live_spread_snapshots(
    symbols: list[str],
    *,
    account_id: str,
) -> dict[str, object]:
    """Charge les quotes Alpaca et les normalise pour le gate de liquidité."""
    from risk_management.liquidity import SpreadSnapshot
    from service.alpaca.clientAlpaca import fetch_latest_quotes

    try:
        raw_quotes = fetch_latest_quotes(symbols, account_id=account_id)
    except Exception:
        LOGGER.warning("Quotes live indisponibles: les entrées seront bloquées par le gate de liquidité.", exc_info=True)
        return {}

    snapshots: dict[str, SpreadSnapshot] = {}
    for symbol, quote in raw_quotes.items():
        if not isinstance(quote, dict):
            continue
        quote_time = _parse_quote_time(quote.get("t"))
        snapshots[str(symbol).strip().upper()] = SpreadSnapshot(
            symbol=str(symbol).strip().upper(),
            bid=_optional_quote_float(quote.get("bp")),
            ask=_optional_quote_float(quote.get("ap")),
            quote_time=quote_time,
            source="alpaca",
        )
    return snapshots


# ── Section 17 Point 9 : provider borrow PIT ────────────────────────────────

def _load_live_borrow_snapshots(
    symbols: list[str],
    *,
    account_id: str,
    trade_date: date,
) -> dict[str, object]:
    """Charge les statuts de borrow (ETB/HTB/NOT_SHORTABLE) pour le gate de liquidité.

    Point 9 — Interroge l'API Alpaca ``GET /v2/assets/{symbol}`` pour les champs
    ``shortable`` et ``easy_to_borrow``, puis les mappe vers les statuts
    ``BorrowStatus`` (ETB/HTB/NOT_SHORTABLE). En cas d'indisponibilité de l'API,
    un fallback local ``EASY_TO_BORROW`` est appliqué (conservateur, documenté).
    """
    from datetime import datetime as _dt, timezone as _tz

    from risk_management.liquidity import BorrowSnapshot, BorrowStatus

    as_of = _dt.now(_tz.utc)
    snapshots: dict[str, BorrowSnapshot] = {}

    # ── Essayer l'API Alpaca asset par symbole ──────────────────────
    try:
        from service.alpaca.clientAlpaca import fetch_asset_by_symbol

        for symbol in symbols:
            sym = str(symbol).strip().upper()
            if not sym:
                continue
            try:
                asset = fetch_asset_by_symbol(sym, account_id=account_id)
            except Exception:
                LOGGER.debug(
                    "fetch_asset_by_symbol échoué pour %s, fallback ETB.", sym,
                    exc_info=True,
                )
                # Fallback ETB individuel pour ce symbole
                snapshots[sym] = BorrowSnapshot(
                    symbol=sym,
                    status=BorrowStatus.EASY_TO_BORROW,
                    fee_annual=0.003,
                    quantity_available=None,
                    locate_required=False,
                    as_of=as_of,
                    source="alpaca_asset_fallback_etb",
                )
                continue

            shortable = bool(asset.get("shortable", True))
            easy_to_borrow = bool(asset.get("easy_to_borrow", True))

            if not shortable:
                status = BorrowStatus.NOT_SHORTABLE
                fee = float("inf")
                locate_required = False
            elif not easy_to_borrow:
                status = BorrowStatus.HARD_TO_BORROW
                fee = 0.05   # 5%/an — frais HTB standards
                locate_required = True
            else:
                status = BorrowStatus.EASY_TO_BORROW
                fee = 0.003  # 0.3%/an — frais ETB standards
                locate_required = False

            snapshots[sym] = BorrowSnapshot(
                symbol=sym,
                status=status,
                fee_annual=fee,
                quantity_available=None,
                locate_required=locate_required,
                as_of=as_of,
                source="alpaca_asset_api",
            )

        if snapshots:
            etb_count = sum(
                1 for s in snapshots.values()
                if s.status == BorrowStatus.EASY_TO_BORROW
            )
            htb_count = sum(
                1 for s in snapshots.values()
                if s.status == BorrowStatus.HARD_TO_BORROW
            )
            not_shortable_count = sum(
                1 for s in snapshots.values()
                if s.status == BorrowStatus.NOT_SHORTABLE
            )
            LOGGER.info(
                "Borrow snapshots chargés via API Alpaca: %d symboles "
                "(%d ETB, %d HTB, %d NOT_SHORTABLE)",
                len(snapshots), etb_count, htb_count, not_shortable_count,
            )
            return snapshots
    except Exception:
        LOGGER.debug(
            "API Alpaca borrow globalement indisponible, fallback local.",
            exc_info=True,
        )

    # ── Fallback local : ETB pour tous les symboles ─────────────────
    for symbol in symbols:
        sym = str(symbol).strip().upper()
        if not sym:
            continue
        snapshots[sym] = BorrowSnapshot(
            symbol=sym,
            status=BorrowStatus.EASY_TO_BORROW,
            fee_annual=0.003,
            quantity_available=None,
            locate_required=False,
            as_of=as_of,
            source="local_fallback_etb",
        )
    LOGGER.info(
        "Borrow snapshots chargés (fallback local ETB): %d symboles | "
        "ATTENTION: aucun endpoint broker réel n'est disponible pour le borrow. "
        "Les shorts seront acceptés sous réserve de liquidité.",
        len(snapshots),
    )
    return snapshots


def _parse_quote_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


# ── Section 17 Point 9 : covariance PIT ─────────────────────────────────────

def _wire_covariance_to_optimizer(
    builder: object,
    *,
    factor_cov_live: object | None,
    operational_snapshot: object | None,
    directional_win_rates: dict[str | tuple[str, str], object],
    config: object,
) -> None:
    """Transmet la covariance PIT au ``PortfolioOptimizer`` (Point 9).

    La covariance est versionnée (``estimation_date``) et datée. Elle est
    transmise au ``PortfolioBuilder`` via ``set_portfolio_optimization()``
    avec les holdings du snapshot opérationnel et les edges directionnels.

    Si la covariance ou les données nécessaires sont absentes, l'optimiseur
    reste inactif et le contrôleur incrémental continue de fonctionner
    (fallback nominal).
    """
    if factor_cov_live is None:
        return
    set_opt = getattr(builder, "set_portfolio_optimization", None)
    if not callable(set_opt):
        return

    try:
        import numpy as np
        from risk_management.portfolio_optimizer import PortfolioOptimizer

        # Extraire la matrice de covariance factorielle
        factor_cov_matrix: np.ndarray | None = None
        if hasattr(factor_cov_live, "factor_cov"):
            factor_cov_matrix = getattr(factor_cov_live, "factor_cov")
            if isinstance(factor_cov_matrix, np.ndarray) and factor_cov_matrix.ndim == 2:
                pass
            else:
                factor_cov_matrix = None

        # Holdings depuis le snapshot opérationnel
        holdings: tuple = ()
        if operational_snapshot is not None and hasattr(operational_snapshot, "holdings"):
            holdings = tuple(getattr(operational_snapshot, "holdings", ()))

        # Edges par symbole depuis les statistiques directionnelles
        edge_by_symbol: dict[str, float] = {}
        for key, dwr in directional_win_rates.items():
            sym = key[0] if isinstance(key, tuple) else key
            hit_rate = float(getattr(dwr, "hit_rate", 0) or 0)
            payoff = float(getattr(dwr, "payoff", 0) or 0)
            if hit_rate > 0 and payoff > 0:
                edge_by_symbol[str(sym)] = hit_rate * payoff - (1.0 - hit_rate)

        # Construire l'optimiseur
        max_positions = int(getattr(config, "effective_max_positions", 20) or 20)
        optimizer = PortfolioOptimizer(
            max_positions=max_positions,
            max_gross_exposure=float(getattr(config, "max_gross_exposure", 1.0) or 1.0),
            max_net_exposure=float(getattr(config, "max_net_exposure", 0.30) or 0.30),
            max_position_weight=float(getattr(config, "max_position_weight", 0.10) or 0.10),
        )

        set_opt(
            optimizer,
            holdings=holdings,
            covariance=factor_cov_matrix,
            edge_by_symbol=edge_by_symbol,
        )
        LOGGER.info(
            "Covariance PIT transmise à l'optimiseur | factors=%d holdings=%d edges=%d",
            factor_cov_matrix.shape[0] if factor_cov_matrix is not None else 0,
            len(holdings),
            len(edge_by_symbol),
        )
    except Exception:
        LOGGER.debug("Transmission covariance à l'optimiseur ignorée.", exc_info=True)


def _optional_quote_float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _build_reconciliation_summary(
    *,
    trade_date: date,
    operational_snapshot: object | None,
    target_entries: list[object],
) -> dict[str, object]:
    """Construit un résumé de réconciliation entre snapshot opérationnel et cibles.

    Point 15 — La réconciliation complète (ordres, fills, PnL, cash) est
    exécutée par ``execution_engine.reconcile_statement`` après l'exécution.
    Cette fonction fournit une pré-réconciliation basée sur les positions
    attendues vs. existantes.
    """
    if operational_snapshot is None:
        return {"status": "skipped", "reason": "no_operational_snapshot"}

    try:
        from risk_management.daily_reconciliation import DailyReconciliation, ReconStatus

        existing_positions = getattr(operational_snapshot, "positions", ())
        existing_symbols = {p.symbol for p in existing_positions}
        target_symbols = {str(getattr(e, "symbol", "")) for e in target_entries}

        # Positions chevauchantes : le builder devrait en tenir compte
        overlapping = existing_symbols & target_symbols
        new_only = target_symbols - existing_symbols
        closed_only = existing_symbols - target_symbols

        recon = DailyReconciliation()
        target_positions_raw: list[dict[str, object]] = [
            {
                "symbol": str(getattr(e, "symbol", "")),
                "side": str(getattr(e, "side", "")),
                "quantity": float(getattr(e, "approved_shares", 0) or 0),
                "entry_price": float(getattr(e, "entry_price", 0) or 0),
            }
            for e in target_entries
        ]
        actual_positions_raw: list[dict[str, object]] = [
            {
                "symbol": p.symbol,
                "side": p.side,
                "quantity": float(getattr(p, "quantity", 0) or 0),
                "avg_entry_price": float(getattr(p, "avg_entry_price", 0) or 0),
            }
            for p in existing_positions
        ]

        report = recon.reconcile(
            trade_date=trade_date,
            target_positions=target_positions_raw,
            actual_positions=actual_positions_raw,
        )

        return {
            "status": report.overall_status.value,
            "is_clean": report.is_clean,
            "match_rate": round(report.match_rate, 4),
            "total_items": report.total_items,
            "matched_items": report.matched_items,
            "mismatched_items": report.mismatched_items,
            "overlapping_positions": len(overlapping),
            "new_positions": len(new_only),
            "closed_positions": len(closed_only),
            "requires_operator_action": report.requires_operator_action,
            "summary": report.summary,
        }
    except Exception:
        LOGGER.debug("Pré-réconciliation ignorée.", exc_info=True)
        return {"status": "error", "reason": "reconciliation_failed"}


# ── Point 10 : persistance du plan de transition ─────────────────────────────

def _persist_transition_plan_artifact(
    transition_plan: object,
    *,
    trade_date: date,
    risk_run_id: str,
) -> str | None:
    """Persiste le ``PositionTransitionPlan`` en JSON pour l'executor.

    L'executor doit exécuter les annulations/liquidations AVANT les nouvelles entrées.
    """
    import json as _json
    from pathlib import Path as _Path

    try:
        target_dir = _Path("artifacts/transition_plans")
        target_dir.mkdir(parents=True, exist_ok=True)
        filepath = target_dir / f"{trade_date.isoformat()}_{risk_run_id}.json"
        payload = transition_plan.to_dict() if hasattr(transition_plan, "to_dict") else {}
        payload["_meta"] = {
            "trade_date": trade_date.isoformat(),
            "risk_run_id": risk_run_id,
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }
        filepath.write_text(
            _json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        LOGGER.info("Plan de transition persisté → %s", filepath)
        return str(filepath)
    except Exception:
        LOGGER.warning("Persistance du plan de transition échouée.", exc_info=True)
        return None


def _build_preflight_data_quality(
    *,
    trade_date: date,
    account_snapshot: object | None,
    effective_equity: float,
    requested_equity: float,
    equity_breakdown: dict[str, object],
    selections: list[object],
    prices: dict[str, object] | None,
    return_matrix: object | None,
    regime_allow_new_entries: bool,
) -> dict[str, object]:
    checks: dict[str, dict[str, object]] = {}
    warnings: list[str] = []

    snapshot_trade_date = getattr(account_snapshot, "trade_date", None)
    snapshot_source = str(getattr(account_snapshot, "source", "") or "").strip() or None
    snapshot_freshness_days = (
        max((trade_date - snapshot_trade_date).days, 0)
        if snapshot_trade_date is not None
        else None
    )
    equity_source = snapshot_source or "cli_account_equity_fallback"
    equity_fallback_used = account_snapshot is None
    equity_status = "ok"
    if equity_fallback_used:
        equity_status = "fallback"
        warnings.append("Equity broker indisponible : fallback sur --account-equity.")
    elif snapshot_freshness_days and snapshot_freshness_days > 0:
        equity_status = "stale"
        warnings.append(f"Snapshot equity daté de J-{snapshot_freshness_days}.")
    checks["equity_snapshot"] = {
        "status": equity_status,
        "source": equity_source,
        "fallback_used": equity_fallback_used,
        "snapshot_trade_date": snapshot_trade_date.isoformat() if snapshot_trade_date is not None else None,
        "freshness_days": snapshot_freshness_days,
        "effective_equity": round(float(effective_equity), 2),
        "requested_equity": round(float(requested_equity), 2),
        "breakdown_source": equity_breakdown.get("source"),
    }

    selection_dates = sorted(
        {
            snapshot_date
            for selection in selections
            if (snapshot_date := getattr(selection, "snapshot_date", None)) is not None
        }
    )
    selection_snapshot_date = selection_dates[-1] if selection_dates else None
    selection_freshness_days = (
        max((trade_date - selection_snapshot_date).days, 0)
        if selection_snapshot_date is not None
        else None
    )
    selection_status = "ok"
    if not selections:
        selection_status = "empty"
    elif selection_snapshot_date is None:
        selection_status = "missing"
        warnings.append("Fraîcheur PIT des sélections indisponible.")
    elif selection_freshness_days and selection_freshness_days > 0:
        selection_status = "stale"
        warnings.append(f"Snapshot sélections daté de J-{selection_freshness_days}.")
    checks["selection_snapshot"] = {
        "status": selection_status,
        "loaded_selections": len(selections),
        "snapshot_date": selection_snapshot_date.isoformat() if selection_snapshot_date is not None else None,
        "freshness_days": selection_freshness_days,
        "distinct_snapshot_dates": [item.isoformat() for item in selection_dates],
    }

    if not regime_allow_new_entries:
        atr_status = "skipped_by_regime"
        atr_available = 0
        atr_coverage_pct = None
    else:
        resolved_prices = prices or {}
        atr_available = sum(
            1
            for price_info in resolved_prices.values()
            if getattr(price_info, "atr_20", None) is not None and float(getattr(price_info, "atr_20", 0) or 0) > 0
        )
        atr_coverage_pct = (atr_available / len(selections)) if selections else None
        atr_status = "ok"
        if not selections:
            atr_status = "empty"
        elif atr_coverage_pct == 0:
            atr_status = "missing"
            warnings.append("Couverture ATR nulle sur les candidats chargés.")
        elif atr_coverage_pct is not None and atr_coverage_pct < 0.8:
            atr_status = "partial"
            warnings.append(f"Couverture ATR partielle ({atr_coverage_pct:.0%}).")
    checks["atr_coverage"] = {
        "status": atr_status,
        "available_symbols": atr_available,
        "coverage_pct": round(float(atr_coverage_pct), 4) if atr_coverage_pct is not None else None,
    }

    if not regime_allow_new_entries:
        corr_status = "skipped_by_regime"
        corr_rows = 0
        corr_columns = 0
        corr_coverage_pct = None
        matched_symbols = 0
    else:
        matrix = return_matrix
        matrix_empty = bool(getattr(matrix, "empty", True))
        matrix_columns = set(getattr(matrix, "columns", [])) if not matrix_empty else set()
        candidate_symbols = [str(getattr(candidate, "symbol", "")).strip().upper() for candidate in selections]
        matched_symbols = sum(1 for symbol in candidate_symbols if symbol in matrix_columns)
        corr_rows = int(getattr(matrix, "shape", (0, 0))[0]) if not matrix_empty else 0
        corr_columns = int(getattr(matrix, "shape", (0, 0))[1]) if not matrix_empty else 0
        corr_coverage_pct = (matched_symbols / len(candidate_symbols)) if candidate_symbols else None
        corr_status = "ok"
        if len(candidate_symbols) <= 1:
            corr_status = "not_applicable"
        elif matrix_empty:
            corr_status = "missing"
            warnings.append("Matrice de corrélation vide.")
        elif corr_coverage_pct is not None and corr_coverage_pct < 0.8:
            corr_status = "partial"
            warnings.append(f"Couverture symboles matrice de corrélation partielle ({corr_coverage_pct:.0%}).")
    checks["correlation_matrix"] = {
        "status": corr_status,
        "rows": corr_rows,
        "columns": corr_columns,
        "matched_symbols": matched_symbols,
        "coverage_pct": round(float(corr_coverage_pct), 4) if corr_coverage_pct is not None else None,
    }

    overall_status = "warning" if any(check["status"] in {"fallback", "stale", "missing", "partial"} for check in checks.values()) else "ok"
    return {
        "status": overall_status,
        "checks": checks,
        "warnings": warnings,
    }


def _entries_to_shadow_compare_frame(entries: list[PortfolioEntry]) -> pd.DataFrame:
    rows = [
        {
            "symbol": entry.symbol,
            "qty": float(entry.approved_shares),
            "price": float(entry.entry_price),
            "conviction": float(entry.conviction_score or 0.0),
        }
        for entry in entries
        if float(entry.approved_shares or 0.0) > 0.0
    ]
    return pd.DataFrame(rows, columns=["symbol", "qty", "price", "conviction"])


def _risk_decisions_to_shadow_compare_frame(decisions: pd.DataFrame) -> pd.DataFrame:
    if decisions is None or decisions.empty:
        return pd.DataFrame(columns=["symbol", "qty", "price", "conviction"])
    work = decisions.copy()
    approved = pd.to_numeric(work.get("approved_shares"), errors="coerce").fillna(0)
    work = work.loc[approved > 0].copy()
    if work.empty:
        return pd.DataFrame(columns=["symbol", "qty", "price", "conviction"])
    return pd.DataFrame(
        {
            "symbol": work["symbol"].astype(str).str.strip().str.upper(),
            "qty": pd.to_numeric(work.get("approved_shares"), errors="coerce").fillna(0.0).astype(float),
            "price": pd.to_numeric(work.get("entry_price"), errors="coerce").fillna(0.0).astype(float),
            "conviction": pd.to_numeric(work.get("conviction_score"), errors="coerce").fillna(0.0).astype(float),
        }
    )


def _build_conviction_weights_calibration(
    candidates: list[object],
    retained_entries: list[PortfolioEntry],
    empirical_risk_calibration: dict[str, object] | None = None,
) -> dict[str, object]:
    calibration_rows = [
        (
            str(getattr(item, "symbol", "") or "").strip().upper(),
            str(getattr(item, "calibration_source", "") or "").strip(),
            str(getattr(item, "calibration_run_id", "") or "").strip(),
        )
        for item in [*retained_entries, *candidates]
        if str(getattr(item, "calibration_source", "") or "").strip()
        or str(getattr(item, "calibration_run_id", "") or "").strip()
    ]
    calibrated_symbols = {symbol for symbol, _, _ in calibration_rows if symbol}
    sources = sorted({source for _, source, _ in calibration_rows if source})
    run_ids = sorted({run_id for _, _, run_id in calibration_rows if run_id})
    if not calibration_rows:
        payload = {
            "source": "default",
            "calibration_run_id": None,
            "distinct_sources": [],
            "distinct_calibration_run_ids": [],
            "applied_candidates": 0,
            "retained_candidates": 0,
        }
        if empirical_risk_calibration:
            payload.update(
                {
                    "source": str(empirical_risk_calibration.get("source") or "weights_calibration_runs"),
                    "calibration_run_id": empirical_risk_calibration.get("run_id"),
                    "runtime_applied": empirical_risk_calibration.get("status") == "selected",
                    "runtime_status": empirical_risk_calibration.get("status"),
                    "runtime_metric_name": empirical_risk_calibration.get("metric_name"),
                    "runtime_metric_value": empirical_risk_calibration.get("metric_value"),
                    "runtime_window_start": (
                        empirical_risk_calibration["window_start"].isoformat()
                        if empirical_risk_calibration.get("window_start") is not None
                        else None
                    ),
                    "runtime_window_end": (
                        empirical_risk_calibration["window_end"].isoformat()
                        if empirical_risk_calibration.get("window_end") is not None
                        else None
                    ),
                    "runtime_best_weights": empirical_risk_calibration.get("best_weights") or {},
                    "runtime_segment_key": empirical_risk_calibration.get("segment_key"),
                    "runtime_requested_segment_key": empirical_risk_calibration.get("requested_segment_key"),
                    "runtime_horizon_days": empirical_risk_calibration.get("horizon_days"),
                    "runtime_lookback_months": empirical_risk_calibration.get("lookback_months"),
                    "runtime_requested_horizon_days": empirical_risk_calibration.get("requested_horizon_days"),
                    "runtime_requested_lookback_months": empirical_risk_calibration.get("requested_lookback_months"),
                    "runtime_market_regime_mode": empirical_risk_calibration.get("market_regime_mode"),
                    "runtime_requested_market_regime_mode": empirical_risk_calibration.get("requested_market_regime_mode"),
                    "runtime_market_regime_fallback_used": bool(
                        empirical_risk_calibration.get("market_regime_fallback_used")
                    ),
                    "runtime_fallback_level": empirical_risk_calibration.get("fallback_level"),
                    "runtime_fallback_reason": empirical_risk_calibration.get("fallback_reason"),
                    "runtime_fallback_journal": empirical_risk_calibration.get("fallback_journal") or [],
                    "runtime_fallback_policy_source": empirical_risk_calibration.get("fallback_policy_source"),
                    "runtime_eligible_for_live": empirical_risk_calibration.get("eligible_for_live"),
                    "runtime_eligibility_reason": empirical_risk_calibration.get("eligibility_reason"),
                }
            )
        return payload
    source = "default"
    if sources:
        source = sources[0] if len(sources) == 1 else "mixed"
    elif run_ids:
        source = "run_id_only"
    payload = {
        "source": source,
        "calibration_run_id": run_ids[0] if len(run_ids) == 1 else None,
        "distinct_sources": sources,
        "distinct_calibration_run_ids": run_ids,
        "applied_candidates": len(calibrated_symbols),
        "retained_candidates": sum(
            1
            for entry in retained_entries
            if str(entry.calibration_source or "").strip() or str(entry.calibration_run_id or "").strip()
        ),
    }
    if empirical_risk_calibration:
        payload.update(
            {
                "runtime_applied": empirical_risk_calibration.get("status") == "selected",
                "runtime_status": empirical_risk_calibration.get("status"),
                "runtime_source": empirical_risk_calibration.get("source"),
                "runtime_calibration_run_id": empirical_risk_calibration.get("run_id"),
                "runtime_metric_name": empirical_risk_calibration.get("metric_name"),
                "runtime_metric_value": empirical_risk_calibration.get("metric_value"),
                "runtime_window_start": (
                    empirical_risk_calibration["window_start"].isoformat()
                    if empirical_risk_calibration.get("window_start") is not None
                    else None
                ),
                "runtime_window_end": (
                    empirical_risk_calibration["window_end"].isoformat()
                    if empirical_risk_calibration.get("window_end") is not None
                    else None
                ),
                "runtime_best_weights": empirical_risk_calibration.get("best_weights") or {},
                "runtime_segment_key": empirical_risk_calibration.get("segment_key"),
                "runtime_requested_segment_key": empirical_risk_calibration.get("requested_segment_key"),
                "runtime_horizon_days": empirical_risk_calibration.get("horizon_days"),
                "runtime_lookback_months": empirical_risk_calibration.get("lookback_months"),
                "runtime_requested_horizon_days": empirical_risk_calibration.get("requested_horizon_days"),
                "runtime_requested_lookback_months": empirical_risk_calibration.get("requested_lookback_months"),
                "runtime_market_regime_mode": empirical_risk_calibration.get("market_regime_mode"),
                "runtime_requested_market_regime_mode": empirical_risk_calibration.get("requested_market_regime_mode"),
                "runtime_market_regime_fallback_used": bool(
                    empirical_risk_calibration.get("market_regime_fallback_used")
                ),
                "runtime_fallback_level": empirical_risk_calibration.get("fallback_level"),
                "runtime_fallback_reason": empirical_risk_calibration.get("fallback_reason"),
                "runtime_fallback_journal": empirical_risk_calibration.get("fallback_journal") or [],
                "runtime_fallback_policy_source": empirical_risk_calibration.get("fallback_policy_source"),
                "runtime_eligible_for_live": empirical_risk_calibration.get("eligible_for_live"),
                "runtime_eligibility_reason": empirical_risk_calibration.get("eligibility_reason"),
            }
        )
    return payload


def _load_empirical_risk_calibration(
    repo: RiskRepository,
    *,
    trade_date: date,
    run_id: str | None,
    market_regime_mode: str | None,
    horizon_days: int | None,
    lookback_months: int | None,
    disabled: bool,
) -> dict[str, object] | None:
    if disabled:
        return None
    loader = getattr(repo, "load_latest_empirical_risk_calibration", None)
    if not callable(loader):
        return None
    try:
        payload = loader(
            trade_date,
            run_id=run_id,
            market_regime_mode=market_regime_mode,
            horizon_days=horizon_days,
            lookback_months=lookback_months,
        )
    except Exception:
        LOGGER.warning("Calibration empirique risk indisponible pour trade_date=%s", trade_date, exc_info=True)
        return None
    return payload if isinstance(payload, dict) else None


def _apply_empirical_risk_calibration(
    config: RiskConfig,
    calibration: dict[str, object] | None,
) -> RiskConfig:
    if not calibration:
        return config
    if calibration.get("status") not in {None, "selected"}:
        LOGGER.info(
            "Calibration empirique risk non appliquée | status=%s fallback=%s reason=%s",
            calibration.get("status"),
            calibration.get("fallback_level"),
            calibration.get("eligibility_reason"),
        )
        return config
    if calibration.get("eligible_for_live") is False:
        LOGGER.info(
            "Calibration empirique risk bloquée par gouvernance | reason=%s segment=%s",
            calibration.get("eligibility_reason"),
            calibration.get("segment_key"),
        )
        return config
    best_weights = calibration.get("best_weights")
    if not isinstance(best_weights, dict):
        return config
    overrides: dict[str, float] = {}
    if {"score_weight", "prediction_weight"} <= set(best_weights):
        score_weight = float(best_weights["score_weight"])
        prediction_weight = float(best_weights["prediction_weight"])
        if abs((score_weight + prediction_weight) - 1.0) <= 1e-6:
            overrides["score_weight"] = score_weight
            overrides["prediction_weight"] = prediction_weight
    for field_name in ("kelly_fraction_multiplier", "min_effective_probability", "assumed_payoff_ratio"):
        if field_name in best_weights:
            overrides[field_name] = float(best_weights[field_name])
    if not overrides:
        return config
    LOGGER.info(
        "Calibration empirique risk appliquée | run_id=%s metric=%s value=%s overrides=%s",
        calibration.get("run_id"),
        calibration.get("metric_name"),
        calibration.get("metric_value"),
        overrides,
    )
    return replace(config, **overrides)


def _top_count_items(counts: dict[str, int], *, limit: int = 5) -> list[dict[str, object]]:
    return [
        {"code": code, "count": int(count)}
        for code, count in sorted(counts.items(), key=lambda item: (-int(item[1]), item[0]))[:limit]
        if int(count) > 0
    ]


def _build_postmortem_artifacts(
    *,
    candidates: list[object],
    entries: list[PortfolioEntry],
    retained_entries: list[PortfolioEntry],
    rejection_reason_code_counts: dict[str, int],
    reduction_reason_code_counts: dict[str, int],
    prices: dict[str, object],
    predictions: dict[str, object],
    win_rates: dict[str, object],
    return_matrix: pd.DataFrame,
    regime_snapshot_payload: dict[str, object] | None,
    config: RiskConfig,
    regime_allow_new_entries: bool,
) -> dict[str, object]:
    sector_rollup: dict[str, dict[str, object]] = {}
    for candidate in candidates:
        sector = str(getattr(candidate, "sector", "UNKNOWN") or "UNKNOWN")
        bucket = sector_rollup.setdefault(
            sector,
            {"sector": sector, "selections": 0, "retained": 0, "rejected": 0, "target_notional": 0.0, "target_weight": 0.0},
        )
        bucket["selections"] = int(bucket["selections"]) + 1
    for entry in entries:
        sector = str(entry.sector or "UNKNOWN")
        bucket = sector_rollup.setdefault(
            sector,
            {"sector": sector, "selections": 0, "retained": 0, "rejected": 0, "target_notional": 0.0, "target_weight": 0.0},
        )
        if float(entry.approved_shares or 0.0) > 0.0:
            bucket["retained"] = int(bucket["retained"]) + 1
            bucket["target_notional"] = round(float(bucket["target_notional"]) + float(entry.target_notional or 0.0), 2)
            bucket["target_weight"] = round(float(bucket["target_weight"]) + float(entry.target_weight or 0.0), 4)
        else:
            bucket["rejected"] = int(bucket["rejected"]) + 1
    sector_breakdown = sorted(
        sector_rollup.values(),
        key=lambda item: (-float(item["target_weight"]), -int(item["retained"]), str(item["sector"])),
    )
    matrix_empty = bool(getattr(return_matrix, "empty", True))
    return {
        "top_rejection_reason_codes": _top_count_items(rejection_reason_code_counts),
        "top_reduction_reason_codes": _top_count_items(reduction_reason_code_counts),
        "sector_breakdown": sector_breakdown,
        "external_source_coverage": {
            "selection_count": len(candidates),
            "price_symbols": len(prices),
            "prediction_symbols": len(predictions),
            "win_rate_symbols": len(win_rates),
            "correlation_matrix_rows": int(return_matrix.shape[0]) if not matrix_empty else 0,
            "correlation_matrix_columns": int(return_matrix.shape[1]) if not matrix_empty else 0,
            "retained_symbols": len(retained_entries),
        },
        "regime_summary": {
            "applied": regime_snapshot_payload is not None,
            "mode": regime_snapshot_payload.get("mode") if regime_snapshot_payload else None,
            "allow_new_entries": regime_allow_new_entries,
            "reasons": list(regime_snapshot_payload.get("reasons") or []) if regime_snapshot_payload else [],
            "risk_multiplier": float(config.risk_multiplier),
            "effective_max_positions": int(config.effective_max_positions),
            "effective_min_notional": float(config.effective_min_notional),
            "max_tickers_per_sector": int(config.max_tickers_per_sector) if config.max_tickers_per_sector is not None else None,
        },
    }


def _run_shadow_compare(
    *,
    enabled: bool,
    reference_run_id: str | None,
    trade_date: date,
    run_id: str,
    account_id: str | None,
    entries: list[PortfolioEntry],
    repo: RiskRepository,
    dry_run: bool,
) -> dict[str, object]:
    if not enabled:
        return {"enabled": False, "status": "disabled", "reference_run_id": None, "report": None}

    try:
        from risk_management.shadow_compare import compare_runs, persist_shadow_run

        reference_source = "explicit_run_id" if reference_run_id else "latest_trade_date"
        if reference_run_id:
            reference_decisions = repo.load_risk_decisions_for_run_id(reference_run_id, account_id=account_id)
        else:
            reference_decisions = repo.load_risk_decisions_for_date(trade_date, account_id=account_id)
            if not reference_decisions.empty and "run_id" in reference_decisions.columns:
                resolved_run_id = str(reference_decisions.iloc[0].get("run_id") or "").strip()
                reference_run_id = resolved_run_id or None

        if reference_decisions.empty or reference_run_id is None:
            return {
                "enabled": True,
                "status": "missing_reference",
                "reference_source": reference_source,
                "reference_run_id": reference_run_id,
                "report": None,
            }

        live_orders = _entries_to_shadow_compare_frame(entries)
        reference_orders = _risk_decisions_to_shadow_compare_frame(reference_decisions)
        report = compare_runs(
            live_orders,
            reference_orders,
            live_run_id=run_id,
            simulated_run_id=reference_run_id,
        )
        report_payload = report.to_payload()
        persisted_report_id = None
        persist_error = None
        if not dry_run:
            try:
                persisted_report_id = persist_shadow_run(report, engine=repo.engine)
            except Exception as exc:  # pragma: no cover - best effort persistance
                persist_error = str(exc)
                LOGGER.warning("Shadow compare non persisté pour run_id=%s", run_id, exc_info=True)
        return {
            "enabled": True,
            "status": "compared",
            "reference_source": reference_source,
            "reference_run_id": reference_run_id,
            "persisted_report_id": persisted_report_id,
            "persist_error": persist_error,
            "symbols_only_in_live_count": len(report.symbols_only_in_live),
            "symbols_only_in_reference_count": len(report.symbols_only_in_sim),
            "avg_qty_drift_pct": report.avg_qty_drift_pct,
            "avg_price_drift_pct": report.avg_price_drift_pct,
            "avg_conviction_drift": report.avg_conviction_drift,
            "report": report_payload,
        }
    except Exception as exc:  # pragma: no cover - best effort shadow compare
        LOGGER.warning("Shadow compare indisponible pour run_id=%s", run_id, exc_info=True)
        return {
            "enabled": True,
            "status": "unavailable",
            "reference_source": "explicit_run_id" if reference_run_id else "latest_trade_date",
            "reference_run_id": reference_run_id,
            "error": str(exc),
            "report": None,
        }


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Module de gestion de risque Alpha Trade")
    p.add_argument("--account-equity", type=float, default=100_000.0)
    p.add_argument("--risk-per-trade-pct", type=float, default=0.01)
    p.add_argument("--max-positions", type=int, default=20)
    p.add_argument("--max-position-weight", type=float, default=0.10)
    p.add_argument("--max-sector-weight", type=float, default=0.30)
    p.add_argument("--min-position-notional", type=float, default=500.0)
    p.add_argument("--trade-date", type=str, default=None, help="YYYY-MM-DD (défaut: aujourd'hui)")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument(
        "--run-mode",
        choices=[mode.value for mode in RiskRunMode],
        default=RiskRunMode.LIVE.value,
        help="Mode typé risk: shadow force dry-run et shadow compare; paper/live publient les targets selon --dry-run.",
    )
    p.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    # --- V2 arguments ---
    p.add_argument("--correlation-threshold", type=float, default=0.80)
    p.add_argument("--correlation-lookback-days", type=int, default=60)
    p.add_argument("--correlation-min-overlap", type=int, default=40)
    p.add_argument("--enable-kelly-sizing", action="store_true", default=False)
    # P2 (2026-06-27) — exclure les candidats sans modèle ML entraîné
    p.add_argument("--filter-no-ml", action="store_true", default=False, help="Exclure les sélections sans modèle ML entraîné (absence dans model_predictions).")
    p.add_argument("--allow-fractional-shares", action="store_true", default=False)
    p.add_argument("--assumed-payoff-ratio", type=float, default=1.5)
    p.add_argument("--kelly-fraction-multiplier", type=float, default=0.25)
    p.add_argument("--score-weight", type=float, default=0.40)
    p.add_argument("--prediction-weight", type=float, default=0.60)
    p.add_argument("--account", type=str, default=None, help="ID du compte Alpaca multi-comptes")
    # Sprint S3 / A-011 — overrides des seuils circuit breaker par préset.
    p.add_argument(
        "--max-portfolio-drawdown-pct",
        type=float,
        default=None,
        help="Override du seuil drawdown circuit breaker (ex: 0.08 = 8%%). Défaut config.yaml.",
    )
    p.add_argument(
        "--max-daily-loss-pct",
        type=float,
        default=None,
        help="Override du seuil perte journalière circuit breaker (ex: 0.03 = 3%%). Défaut config.yaml.",
    )
    p.add_argument(
        "--target-annual-vol",
        type=float,
        default=None,
        help="Cible de volatilité annualisée live (proxy benchmark). Désactivé si absent.",
    )
    p.add_argument(
        "--vol-target-lookback-days",
        type=int,
        default=60,
        help="Fenêtre de vol réalisée utilisée par le vol targeting live (défaut : 60 séances).",
    )
    p.add_argument(
        "--min-ml-coverage-ratio",
        type=float,
        default=None,
        help="Seuil minimal de couverture ML requis avant de publier de nouvelles cibles risk (ex: 0.80).",
    )
    p.add_argument(
        "--enable-shadow-compare",
        action="store_true",
        default=False,
        help="Compare le run courant avec le dernier run risk persiste du même jour ou avec --shadow-compare-run-id.",
    )
    p.add_argument(
        "--shadow-compare-run-id",
        type=str,
        default=None,
        help="Run de référence explicite pour le shadow compare (sinon dernier run du trade_date).",
    )
    p.add_argument(
        "--disable-empirical-calibration",
        action="store_true",
        default=False,
        help="Désactive l'application best-effort du dernier run weights_calibration_runs de scope risk.",
    )
    p.add_argument(
        "--empirical-calibration-run-id",
        type=str,
        default=None,
        help="Run de calibration risk explicite à appliquer (sinon dernier window_end <= trade_date).",
    )
    p.add_argument(
        "--empirical-calibration-horizon-days",
        type=int,
        default=5,
        help="Horizon de calibration risk attendu pour le runtime live (défaut : 5 jours).",
    )
    p.add_argument(
        "--empirical-calibration-lookback-months",
        type=int,
        default=12,
        help="Fenêtre de calibration risk attendue pour le runtime live (défaut : 12 mois).",
    )
    return p


def _print_summary(entries: list[PortfolioEntry], run_id: str, trade_date: date) -> None:
    accepted = [e for e in entries if e.approved_shares > 0]
    rejected = [e for e in entries if e.approved_shares == 0]
    total_notional = sum(e.target_notional for e in accepted)
    print(f"\n{'=' * 70}")
    print(f"  Risk Management — run_id={run_id}  trade_date={trade_date}")
    print(f"  Candidats evalues : {len(entries)}")
    print(f"  Positions retenues: {len(accepted)}  |  Rejetees: {len(rejected)}")
    print(f"  Notional total    : ${total_notional:,.2f}")
    print(f"{'=' * 70}")
    for e in accepted:
        print(f"  {e.symbol:<8} {e.decision:<10} shares={format_share_quantity(e.approved_shares):>6}  "
              f"price={e.entry_price:>8.2f}  weight={e.target_weight:>6.2%}  "
              f"score={e.score_used:.4f} ({e.score_source})  "
              f"conviction={e.conviction_score:.4f}  sizing={e.sizing_method}")
    if rejected:
        print("  --- rejetes ---")
        for e in rejected:
            print(f"  {e.symbol:<8} {e.decision:<10} raison={e.decision_reason}")
    print()


def main(args: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(args)
    run_mode = RiskRunMode(args.run_mode)
    if run_mode is RiskRunMode.SHADOW:
        args.dry_run = True
    configure_root_logging(
        level=getattr(logging, args.log_level),
        log_path="./log/risk_management.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )

    started_at = datetime.now()

    trade_date = datetime.strptime(args.trade_date, "%Y-%m-%d").date() if args.trade_date else date.today()
    raw_account_id = (args.account or "").strip() or None
    requested_equity = float(args.account_equity)
    # ── Initialisation des variables de résumé ───────────────────────
    daily_quality_report_path: str | None = None
    spread_snapshots: dict[str, object] = {}
    borrow_snapshots: dict[str, object] = {}
    liquidity_gate: object | None = None
    transition_plan: object | None = None
    operational_snapshot: object | None = None
    retained_entries: list[object] = []
    preflight_data_quality: dict[str, object] = {}
    decision_audit_path: str | None = None
    conviction_weights_calibration: dict[str, object] = {}
    empirical_risk_calibration: dict[str, object] = {}
    shadow_compare_summary: dict[str, object] | None = None
    postmortem_artifacts: list[object] = []
    # L'IHM transmet systématiquement `--account default`. On considère cette
    # valeur comme un compte implicite : si aucun snapshot n'est disponible, on
    # fallback sur `--account-equity` plutôt que de bloquer le pipeline.
    requested_account_id = None if (raw_account_id is None or raw_account_id.lower() == "default") else raw_account_id
    resolved_account_scope = raw_account_id or "default"

    repo = RiskRepository()
    account_snapshot = repo.load_account_risk_snapshot(requested_account_id, trade_date)
    effective_account_id = account_snapshot.account_id if account_snapshot is not None else requested_account_id
    equity_breakdown = repo.load_account_equity_breakdown(effective_account_id, trade_date)
    if account_snapshot is None:
        # Fallback systématique sur --account-equity quand aucun snapshot broker
        # n'est disponible. Cas typiques :
        #   - premier run de la journée pour un compte (broker_account_snapshots
        #     n'est rempli qu'après l'étape 12 — Execution paper/live).
        #   - switch vers un compte qui n'a jamais exécuté l'étape 12.
        #   - mode simulate (jamais d'écriture broker_account_snapshots).
        # Le sizing utilise --account-equity de l'IHM ; le risque est borné
        # par cette valeur, donc safe même en multi-comptes.
        effective_equity = requested_equity
        pnl_snapshot = PnLSnapshot(
            portfolio_high_watermark=effective_equity,
            portfolio_current_value=effective_equity,
            daily_pnl=0.0,
        )
        LOGGER.warning(
            "Aucun account_risk_snapshot pour account=%s date=%s ; fallback sur --account-equity=%.2f. "
            "Pour utiliser l'equity broker reel, lancez l'etape 12 (Execution paper/live) sur ce compte.",
            raw_account_id or "default",
            trade_date,
            effective_equity,
        )
    else:
        effective_equity = float(account_snapshot.equity)
        if account_snapshot.trade_date < trade_date and requested_equity > 0:
            capped_equity = min(effective_equity, requested_equity)
            if capped_equity < effective_equity:
                LOGGER.warning(
                    "Snapshot equity stale pour account=%s (snapshot=%s, trade_date=%s) ; "
                    "cap conservateur applique: snapshot=%.2f -> requested=%.2f.",
                    account_snapshot.account_id,
                    account_snapshot.trade_date,
                    trade_date,
                    effective_equity,
                    capped_equity,
                )
                effective_equity = capped_equity
        daily_pnl = account_snapshot.daily_total_pnl
        if daily_pnl is None:
            realized = account_snapshot.daily_realized_pnl or 0.0
            unrealized = account_snapshot.daily_unrealized_pnl or 0.0
            daily_pnl = realized + unrealized
        pnl_snapshot = PnLSnapshot(
            portfolio_high_watermark=account_snapshot.high_watermark,
            portfolio_current_value=account_snapshot.equity,
            daily_pnl=daily_pnl,
        )
        LOGGER.info(
            "Account snapshot charge | account=%s snapshot_trade_date=%s equity=%.2f buying_power=%.2f",
            account_snapshot.account_id,
            account_snapshot.trade_date,
            account_snapshot.equity,
            account_snapshot.buying_power,
        )

    # ── Section 17 Point 8 : snapshot opérationnel réel ─────────────────
    operational_snapshot = None
    try:
        from datetime import datetime as _dt, timezone as _tz

        from risk_management.operational_data import OperationalDataSnapshot
        from risk_management.transition_handler import OpenOrder, OpenPosition

        # Construire le snapshot opérationnel à partir des données disponibles
        account_as_of = (
            _dt.combine(account_snapshot.trade_date, _dt.min.time(), tzinfo=_tz.utc)
            if account_snapshot is not None
            else _dt.now(_tz.utc)
        )
        account_data: dict[str, object] = {
            "equity": effective_equity,
            "cash": float(getattr(account_snapshot, "cash", 0.0) or 0.0) if account_snapshot is not None else 0.0,
            "settled_cash": float(getattr(account_snapshot, "cash", 0.0) or 0.0) if account_snapshot is not None else 0.0,
            "buying_power": float(getattr(account_snapshot, "buying_power", effective_equity * 2.0) or effective_equity * 2.0)
            if account_snapshot is not None
            else effective_equity * 2.0,
        }

        # Charger les positions existantes depuis les décisions de risque précédentes
        existing_positions: list[OpenPosition] = []
        if account_snapshot is not None and hasattr(repo, "load_risk_decisions_for_date"):
            try:
                prev_decisions = repo.load_risk_decisions_for_date(
                    trade_date, account_id=effective_account_id or resolved_account_scope
                )
                if not prev_decisions.empty:
                    for _, row in prev_decisions.iterrows():
                        sym = str(row.get("symbol") or "").strip().upper()
                        side_raw = str(row.get("side") or "").strip().lower()
                        if not sym or side_raw not in ("buy", "sell"):
                            continue
                        qty = float(row.get("approved_shares", 0) or 0)
                        if qty <= 0:
                            continue
                        existing_positions.append(
                            OpenPosition(
                                symbol=sym,
                                side="short" if side_raw == "sell" else "long",
                                quantity=qty,
                                avg_entry_price=float(row.get("entry_price", 0) or 0),
                            )
                        )
            except Exception:
                LOGGER.debug("Impossible de charger les positions existantes pour le snapshot opérationnel.", exc_info=True)

        operational_snapshot = OperationalDataSnapshot.from_raw(
            account_id=effective_account_id or resolved_account_scope,
            account=account_data,
            positions=[
                {"symbol": p.symbol, "side": p.side, "qty": p.quantity,
                 "avg_entry_price": p.avg_entry_price, "current_price": p.avg_entry_price}
                for p in existing_positions
            ],
            orders=[],  # les ordres ouverts sont gérés par l'executor
            source="risk_cli_account_snapshot",
            as_of=account_as_of,
        )
        LOGGER.info(
            "Snapshot opérationnel construit | account=%s equity=%.2f positions=%d",
            operational_snapshot.account.account_id,
            operational_snapshot.account.equity,
            len(operational_snapshot.positions),
        )
    except Exception:
        LOGGER.warning("Construction du snapshot opérationnel échouée — le pipeline continue sans.", exc_info=True)
        operational_snapshot = None

    progress_total_steps = 8
    progress_context: dict[str, object] = {
        "trade_date": trade_date.isoformat(),
        "dry_run": bool(args.dry_run),
        "run_mode": run_mode.value,
        "effective_equity": round(float(effective_equity), 2),
        "account_id": effective_account_id or resolved_account_scope,
    }
    _emit_live_progress(
        dict(progress_context),
        current=1,
        total=progress_total_steps,
        label="🛡️ Progression risk management — résolution du compte",
        phase="resolve_account",
    )

    # ── Section 17 Point 6.1-6.2 : loader unifié ────────────────────
    # Priorité : defaults < config.yaml < capital_preset < CLI args
    from risk_management.config import load_risk_config

    config = load_risk_config(
        equity=effective_equity,
        cli_overrides={
            "account_equity": effective_equity,
            "risk_per_trade_pct": args.risk_per_trade_pct,
            "max_positions": args.max_positions,
            "max_position_weight": args.max_position_weight,
            "max_sector_weight": args.max_sector_weight,
            "min_position_notional": args.min_position_notional,
            "dry_run": args.dry_run,
            "correlation_threshold": args.correlation_threshold,
            "correlation_lookback_days": args.correlation_lookback_days,
            "correlation_min_overlap": args.correlation_min_overlap,
            "enable_kelly_sizing": args.enable_kelly_sizing,
            "filter_unmodeled_selections": args.filter_no_ml,
            "allow_fractional_shares": args.allow_fractional_shares,
            "assumed_payoff_ratio": args.assumed_payoff_ratio,
            "kelly_fraction_multiplier": args.kelly_fraction_multiplier,
            "score_weight": args.score_weight,
            "prediction_weight": args.prediction_weight,
            **({
                "target_annual_vol": float(args.target_annual_vol),
            } if args.target_annual_vol is not None and float(args.target_annual_vol) > 0 else {}),
            "vol_target_lookback_days": int(args.vol_target_lookback_days),
        },
    )

    # Appliquer les overrides drawdown spécifiques depuis le preset
    # (déjà intégrés par load_risk_config, mais les CLI args prennent le dessus)
    if args.max_portfolio_drawdown_pct is not None:
        config = config.with_overrides(
            max_portfolio_drawdown_pct=float(args.max_portfolio_drawdown_pct),
        )
    if args.max_daily_loss_pct is not None:
        config = config.with_overrides(
            max_daily_loss_pct=float(args.max_daily_loss_pct),
        )

    market_regimes_cfg = None
    try:
        from service.market import parse_market_regimes

        market_regimes_cfg = parse_market_regimes((load_config() or {}).get("market_regimes"))
    except Exception:
        LOGGER.warning("Chargement de la configuration market_regimes impossible côté risk_management.", exc_info=True)

    from risk_management.regime_apply import apply_snapshot, apply_structural_market_guards, apply_transition

    config = apply_structural_market_guards(
        config,
        market_regimes_config=market_regimes_cfg,
        equity=effective_equity,
    )
    regime_snapshot = _resolve_market_regime_snapshot(trade_date, effective_equity, repo)
    regime_snapshot_payload = _serialize_market_regime_snapshot(regime_snapshot)
    regime_transition = _evaluate_regime_transition(regime_snapshot)
    if regime_snapshot is not None:
        persist_market_macro_snapshot_daily(
            trade_date=trade_date,
            macro_payload=getattr(regime_snapshot, "macro", None),
            engine=getattr(repo, "engine", None),
        )

        config = apply_snapshot(config, regime_snapshot)
    config = apply_transition(config, regime_transition)
    # ── Section 17 Point 8 : construire le plan de transition si destructif ──
    transition_plan = None
    if (
        regime_transition is not None
        and getattr(regime_transition, "action", None) is not None
        and getattr(regime_transition.action, "is_destructive", False)
        and operational_snapshot is not None
    ):
        try:
            from risk_management.transition_handler import TransitionHandler

            handler = TransitionHandler()
            positions_list = list(operational_snapshot.positions)
            orders_list = list(operational_snapshot.open_orders)
            transition_plan = handler.build_plan(regime_transition, positions_list, orders_list)
            LOGGER.warning(
                "Plan de transition régime construit | action=%s steps=%d reason=%s",
                regime_transition.action.value,
                len(transition_plan.steps),
                regime_transition.reason,
            )
        except Exception:
            LOGGER.warning("Construction du plan de transition échouée.", exc_info=True)
            transition_plan = None
    # ── Point 10 : persister le plan de transition pour l'executor ──
    if transition_plan is not None and transition_plan.has_actions:
        _persist_transition_plan_artifact(
            transition_plan,
            trade_date=trade_date,
            risk_run_id=risk_run_id,
        )
    requested_calibration_market_regime_mode = (
        str(getattr(regime_snapshot, "mode", "") or "").strip().lower() or "all"
    )
    empirical_risk_calibration = _load_empirical_risk_calibration(
        repo,
        trade_date=trade_date,
        run_id=str(args.empirical_calibration_run_id or "").strip() or None,
        market_regime_mode=requested_calibration_market_regime_mode,
        horizon_days=int(args.empirical_calibration_horizon_days),
        lookback_months=int(args.empirical_calibration_lookback_months),
        disabled=bool(args.disable_empirical_calibration),
    )
    config = _apply_empirical_risk_calibration(config, empirical_risk_calibration)
    vol_target_state = VolTargetDecision(enabled=False, applied=False, reason="disabled")
    if config.target_annual_vol is not None and config.target_annual_vol > 0:
        benchmark_returns = repo.load_return_matrix_asof(
            [_VOL_TARGET_BENCHMARK_SYMBOL],
            trade_date,
            config.vol_target_lookback_days,
        )
        benchmark_series = (
            benchmark_returns[_VOL_TARGET_BENCHMARK_SYMBOL]
            if not benchmark_returns.empty and _VOL_TARGET_BENCHMARK_SYMBOL in benchmark_returns.columns
            else pd.Series(dtype=float)
        )
        vol_target_state = evaluate_vol_target(
            benchmark_series,
            target_annual_vol=config.target_annual_vol,
            lookback_days=config.vol_target_lookback_days,
            benchmark_symbol=_VOL_TARGET_BENCHMARK_SYMBOL,
        )
        config = apply_vol_target_to_risk_config(config, vol_target_state)
        LOGGER.info(
            "Vol targeting live | enabled=%s applied=%s reason=%s target=%.4f realized=%s scaler=%.4f benchmark=%s",
            vol_target_state.enabled,
            vol_target_state.applied,
            vol_target_state.reason,
            float(vol_target_state.target_annual_vol or 0.0),
            (
                f"{float(vol_target_state.realized_annual_vol):.4f}"
                if vol_target_state.realized_annual_vol is not None
                else "n/a"
            ),
            float(vol_target_state.scaler),
            vol_target_state.benchmark_symbol,
        )
    regime_allow_new_entries = bool(
        getattr(regime_transition, "allow_new_entries", True)
        if regime_transition is not None
        else getattr(regime_snapshot, "allow_new_entries", True) if regime_snapshot is not None else True
    )
    regime_entries_blocked = 0
    snapshot_source = str(getattr(account_snapshot, "source", "") or "").strip()
    breakdown_source = str(equity_breakdown.get("source") or "").strip()
    equity_source = snapshot_source or (breakdown_source if account_snapshot is not None else "cli_account_equity_fallback")
    equity_fallback_used = account_snapshot is None
    snapshot_freshness_days = (
        max((trade_date - account_snapshot.trade_date).days, 0)
        if account_snapshot is not None
        else None
    )

    circuit_breaker = CircuitBreaker(config, pnl_snapshot)
    circuit_breaker.notify_if_active()

    # ── Rotation factor : tracker de performance momentum (live) ─────
    from selector.regime_scoring import MomentumRotationState

    rotation_state = MomentumRotationState(lookback_weeks=4, threshold=-0.03)
    equity_history = repo.load_equity_history(
        effective_account_id, trade_date, lookback_days=25
    )
    if len(equity_history) >= 2:
        prev_equity: float | None = None
        for _eq_date, eq_val in equity_history:
            if prev_equity is not None and prev_equity > 0:
                daily_ret = (eq_val / prev_equity) - 1.0
                rotation_state.record(daily_ret)
            prev_equity = eq_val
        # Ajouter le retour du jour en cours (si PnL dispo)
        if pnl_snapshot is not None and prev_equity is not None and prev_equity > 0:
            current_equity = float(pnl_snapshot.portfolio_current_value)
            if current_equity > 0 and current_equity != prev_equity:
                daily_ret = (current_equity / prev_equity) - 1.0
                rotation_state.record(daily_ret)
        rot_triggered = rotation_state.should_rotate()
        rot_cum = rotation_state.cumulative_return()
        LOGGER.info(
            "Rotation factor live | ready=%s triggered=%s cum_return=%.4f data_points=%d",
            rotation_state.is_ready(),
            rot_triggered,
            rot_cum if rot_cum is not None else float('nan'),
            len(equity_history),
        )
    else:
        LOGGER.info(
            "Rotation factor live | insuffisant equity_history=%d (besoin ≥ 2 points)",
            len(equity_history),
        )

    # ── Breakout confirmation tracker (Quick Win 1) ──────────────────
    from risk_management.concentration import BreakoutConfirmationTracker

    _breakout_state_path = Path("artifacts/ihm_preferences/breakout_tracker.json")
    breakout_tracker: BreakoutConfirmationTracker
    if _breakout_state_path.exists():
        try:
            breakout_tracker = BreakoutConfirmationTracker.from_dict(
                json.loads(_breakout_state_path.read_text(encoding="utf-8"))
            )
            LOGGER.info("Breakout tracker chargé: %s", breakout_tracker.to_summary())
        except Exception:
            LOGGER.warning("Breakout tracker load failed, creating new.", exc_info=True)
            breakout_tracker = BreakoutConfirmationTracker(min_breakout_days=config.min_breakout_days)
    else:
        breakout_tracker = BreakoutConfirmationTracker(min_breakout_days=config.min_breakout_days)

    resolved_capital_preset = resolve_capital_preset_for_equity(effective_equity)
    if resolved_capital_preset is None:
        raise SystemExit("Aucun preset capital ne permet de résoudre l'univers tradable live.")
    universe = repo.load_tradable_universe_asof(trade_date, resolved_capital_preset.key)
    if universe.data_quality_grade.strip().lower() != "full":
        raise SystemExit(
            "L'univers tradable live doit être de qualité full; "
            f"grade reçu: {universe.data_quality_grade!r}."
        )
    universe_run_id = universe.universe_run_id
    universe_symbols = list(universe.symbols)
    universe_symbol_count = len(universe_symbols)
    LOGGER.info("Univers tradable ML-first chargé: run=%s symbols=%d", universe_run_id, universe_symbol_count)
    _emit_live_progress(
        dict(progress_context, targeted_symbols=universe_symbol_count),
        current=2,
        total=progress_total_steps,
        label="🛡️ Progression risk management — chargement des candidats",
        phase="load_candidates",
        unit="étapes",
    )

    from risk_management.ml_gate import apply_ml_gate_to_risk_config, resolve_ml_gate_state

    ml_gate_state = resolve_ml_gate_state(getattr(repo, "engine", None))
    config = apply_ml_gate_to_risk_config(config, ml_gate_state)
    mlops_allows_new_entries = bool(ml_gate_state.enabled)
    entry_gate_allows_new_entries = regime_allow_new_entries and mlops_allows_new_entries
    mlops_entries_blocked = 0
    LOGGER.info(
        "ML gate | enabled=%s reason=%s decision_id=%s drift_status=%s action=%s",
        ml_gate_state.enabled,
        ml_gate_state.reason,
        ml_gate_state.decision_id,
        ml_gate_state.drift_status,
        ml_gate_state.action,
    )
    if not mlops_allows_new_entries:
        LOGGER.warning(
            "Gate MLOps bloquant: aucune nouvelle entrée ne sera publiée | reason=%s decision_id=%s",
            ml_gate_state.reason,
            ml_gate_state.decision_id,
        )

    # ── Point 5 : Construire MLRankedCandidate plutôt que SelectionScore ──
    from risk_management.selection_contract import build_candidate_from_prediction, build_rankings as _ml_rank

    candidates: list[MLRankedCandidate] = []
    spread_snapshots: dict[str, object] = {}
    borrow_snapshots: dict[str, object] = {}
    liquidity_gate: object | None = None
    ml_coverage_gate = MlCoverageGateDecision(enabled=False, allowed=True, reason="disabled")
    if entry_gate_allows_new_entries:
        LOGGER.info("Chargement des predictions ML…")
        predictions = repo.load_predictions_asof(universe_symbols, trade_date) if ml_gate_state.enabled else {}
        LOGGER.info("Predictions chargees pour %d symboles.", len(predictions))

        ml_coverage_gate = evaluate_ml_coverage_gate(
            selection_count=universe_symbol_count,
            prediction_count=len(predictions),
            min_coverage_ratio=args.min_ml_coverage_ratio,
            regime_allows_new_entries=entry_gate_allows_new_entries,
            ml_gate_enabled=ml_gate_state.enabled,
        )
        if ml_coverage_gate.enabled and not ml_coverage_gate.allowed:
            LOGGER.error(
                "ML coverage gate bloquant | coverage=%.4f threshold=%.4f candidates=%d predictions=%d reason=%s",
                float(ml_coverage_gate.coverage_ratio or 0.0),
                float(ml_coverage_gate.required_ratio or 0.0),
                int(ml_coverage_gate.selection_count),
                int(ml_coverage_gate.prediction_count),
                ml_coverage_gate.reason,
            )
            raise SystemExit(
                "Couverture ML insuffisante pour publier de nouvelles cibles live : "
                f"{float(ml_coverage_gate.coverage_ratio or 0.0):.2%} < {float(ml_coverage_gate.required_ratio or 0.0):.2%}."
            )

        # Construire les MLRankedCandidate depuis les prédictions (après coverage gate)
        for symbol, pred in predictions.items():
            try:
                candidate = build_candidate_from_prediction(
                    symbol=symbol,
                    trade_date=trade_date,
                    predicted_side=pred.predicted_side,
                    proba_long=pred.proba_long,
                    proba_flat=pred.proba_flat,
                    proba_short=pred.proba_short,
                    proba=pred.predicted_proba,
                    model_run_id=pred.run_id,
                    universe_run_id=universe_run_id,
                    research_only=pred.research_only,
                )
            except (TypeError, ValueError) as exc:
                LOGGER.warning("MLRankedCandidate construction failed for %s: %s", symbol, exc)
                continue
            if candidate.is_actionable():
                candidates.append(candidate)
        # Apply ML rankings (longs then shorts, each by p_side descending)
        longs, shorts = _ml_rank(candidates)
        candidates = [*longs, *shorts]
        LOGGER.info("MLRankedCandidate construits: %d longs + %d shorts", len(longs), len(shorts))

        # Symbols list for loading prices/win_rates/returns
        symbols = [c.symbol for c in candidates]

        LOGGER.info("Chargement des prix et ATR…")
        prices = repo.load_prices_asof(symbols, trade_date, atr_window=config.atr_window)
        LOGGER.info("Prix charges pour %d symboles.", len(prices))
        _emit_live_progress(
            dict(progress_context, targeted_symbols=len(candidates), price_symbols=len(prices)),
            current=3,
            total=progress_total_steps,
            label="🛡️ Progression risk management — chargement prix & ATR",
            phase="load_prices",
        )

        _emit_live_progress(
            dict(progress_context, targeted_symbols=len(candidates), prediction_symbols=len(predictions)),
            current=4,
            total=progress_total_steps,
            label="🛡️ Progression risk management — chargement des prédictions ML",
            phase="load_predictions",
        )

        LOGGER.info("Chargement des win rates…")
        win_rates = repo.load_win_rates_asof(symbols, trade_date)
        LOGGER.info("Win rates charges pour %d symboles.", len(win_rates))
        directional_loader = getattr(repo, "load_directional_win_rates_asof", None)
        directional_win_rates = directional_loader(symbols, trade_date) if callable(directional_loader) else {}
        LOGGER.info("Métriques OOS directionnelles chargées pour %d symboles/sides.", len(directional_win_rates))
        _emit_live_progress(
            dict(progress_context, targeted_symbols=len(candidates), win_rate_symbols=len(win_rates)),
            current=5,
            total=progress_total_steps,
            label="🛡️ Progression risk management — chargement des win rates",
            phase="load_win_rates",
        )

        LOGGER.info("Chargement de la matrice de rendements…")
        return_matrix = repo.load_return_matrix_asof(symbols, trade_date, config.correlation_lookback_days)
        LOGGER.info("Matrice de rendements : %s", return_matrix.shape if not return_matrix.empty else "vide")
        _emit_live_progress(
            dict(
                progress_context,
                targeted_symbols=len(candidates),
                return_matrix_rows=int(return_matrix.shape[0]) if not return_matrix.empty else 0,
                return_matrix_columns=int(return_matrix.shape[1]) if not return_matrix.empty else 0,
            ),
            current=6,
            total=progress_total_steps,
            label="🛡️ Progression risk management — chargement de la matrice de rendements",
            phase="load_return_matrix",
        )

        # ── Section 17 Point 2.4 : rapport quotidien de qualité des données ──
        daily_quality_report_path: str | None = None
        try:
            from common.data_availability import (
                DataAvailabilityInfo,
                make_availability_from_bar_date,
            )
            from common.daily_quality_report import build_and_persist_daily_report
            from datetime import timezone as _tz

            # Construire la map de disponibilité par symbole depuis les prix chargés
            availability_map: dict[str, object] = {}
            decision_cutoff = datetime(trade_date.year, trade_date.month, trade_date.day, 21, 0, 0, tzinfo=_tz.utc)
            for sym in symbols:
                price_info = prices.get(sym)
                if price_info is not None and price_info.price_asof_date is not None:
                    avail = make_availability_from_bar_date(
                        bar_date=price_info.price_asof_date,
                        source="repository",
                        decision_cutoff=decision_cutoff,
                    )
                else:
                    # Symbole sans prix → MISSING_NO_SOURCE
                    from common.data_availability import QualityState
                    avail = DataAvailabilityInfo(
                        event_time=decision_cutoff,
                        available_at=decision_cutoff,
                        source="repository",
                        quality=QualityState.MISSING_NO_SOURCE,
                    )
                availability_map[sym] = avail

            combined = build_and_persist_daily_report(
                trade_date=trade_date,
                symbols=list(symbols),
                availability_map=availability_map,
                decision_cutoff=decision_cutoff,
            )
            daily_quality_report_path = combined.report_path
            if combined.quality.alerts:
                LOGGER.warning(
                    "Rapport qualité quotidien : %d alertes — couverture=%.1f%%",
                    len(combined.quality.alerts),
                    combined.quality.coverage_ratio * 100,
                )
                for alert in combined.quality.alerts[:5]:
                    LOGGER.warning("  ⚠️  %s", alert)
            else:
                LOGGER.info(
                    "Rapport qualité quotidien OK : couverture=%.1f%% (%d/%d symboles)",
                    combined.quality.coverage_ratio * 100,
                    combined.quality.symbols_with_data,
                    combined.quality.total_symbols,
                )
        except Exception:
            LOGGER.debug("Rapport qualité quotidien indisponible.", exc_info=True)

        liquidity_gate = None
        if not config.dry_run:
            from risk_management.liquidity import LiquidityGate

            liquidity_gate = LiquidityGate()
            spread_snapshots = _load_live_spread_snapshots(
                symbols,
                account_id=effective_account_id,
            )
            # ── Section 17 Point 9 : charger les statuts borrow PIT ─────
            borrow_snapshots = _load_live_borrow_snapshots(
                symbols,
                account_id=effective_account_id or resolved_account_scope,
                trade_date=trade_date,
            )

        builder = PortfolioBuilder(
            config,
            pnl=pnl_snapshot,
            circuit_breaker=circuit_breaker,
            regime_snapshot=regime_snapshot,
            regime_transition=regime_transition,
            rotation_state=rotation_state,
            breakout_tracker=breakout_tracker,
        )
        # ── Section 17 Point 8 : injecter le snapshot opérationnel ──────
        # Enrichir avec les données PIT borrow/spread/quote si disponibles
        if operational_snapshot is not None and (spread_snapshots or borrow_snapshots):
            try:
                # Enrichir le snapshot avec les métadonnées de spread et borrow
                spread_summary = {
                    "symbols_loaded": len(spread_snapshots),
                    "sources": list({getattr(s, "source", "unknown") for s in spread_snapshots.values() if hasattr(s, "source")}),
                }
                borrow_summary = {
                    "symbols_loaded": len(borrow_snapshots),
                    "etb_count": sum(1 for b in borrow_snapshots.values() if hasattr(b, "status") and str(getattr(b, "status", "")).startswith("easy")),
                    "htb_count": sum(1 for b in borrow_snapshots.values() if hasattr(b, "status") and str(getattr(b, "status", "")).startswith("hard")),
                    "not_shortable_count": sum(1 for b in borrow_snapshots.values() if hasattr(b, "status") and str(getattr(b, "status", "")).startswith("not")),
                }
                LOGGER.info(
                    "Snapshot opérationnel enrichi PIT | spreads=%d borrow=%d (ETB=%d HTB=%d)",
                    spread_summary["symbols_loaded"],
                    borrow_summary["symbols_loaded"],
                    borrow_summary["etb_count"],
                    borrow_summary["htb_count"],
                )
            except Exception:
                LOGGER.debug("Enrichissement PIT spread/borrow ignoré.", exc_info=True)

        if operational_snapshot is not None and hasattr(builder, "set_operational_snapshot"):
            builder.set_operational_snapshot(operational_snapshot)
        # ── Factor risk model (Priorité 3) : construire les exposures ──
        if config.enable_factor_model:
            try:
                from risk_management.factor_model import (
                    build_exposures_from_score_frame,
                    build_factor_returns,
                    estimate_factor_covariance,
                )
                # Charger les colonnes factorielles depuis stock_scores_history
                factor_df = repo.load_factor_columns_asof(
                    [c.symbol for c in candidates],
                    trade_date,
                )
                if not factor_df.empty:
                    factor_exposures_raw = build_exposures_from_score_frame(
                        factor_df, trade_date,
                    )
                    factor_exposures_live: dict[str, object] = {
                        sym: exp for sym, exp in factor_exposures_raw.items()
                    }
                    # Construire les rendements factoriels
                    if not return_matrix.empty:
                        factor_returns = build_factor_returns(
                            symbols=list(factor_exposures_live.keys()),
                            close_prices=return_matrix,
                            benchmark_prices=None,
                            factor_exposures_map=factor_exposures_raw,
                        )
                        factor_cov_live = estimate_factor_covariance(
                            factor_returns,
                            lookback_days=config.factor_lookback_days,
                            ewma_half_life=config.factor_ewma_half_life,
                            estimation_date=trade_date,
                            stock_returns=return_matrix,
                        ) if factor_returns is not None else None
                        # Recréer le builder avec le modèle factoriel
                        builder = PortfolioBuilder(
                            config,
                            pnl=pnl_snapshot,
                            circuit_breaker=circuit_breaker,
                            regime_snapshot=regime_snapshot,
                            regime_transition=regime_transition,
                            rotation_state=rotation_state,
                            breakout_tracker=breakout_tracker,
                            factor_exposures=factor_exposures_live,
                            factor_covariance=factor_cov_live,
                        )
                        if operational_snapshot is not None and hasattr(builder, "set_operational_snapshot"):
                            builder.set_operational_snapshot(operational_snapshot)
                        LOGGER.info(
                            "Factor model enabled: %d exposures, %d factor names",
                            len(factor_exposures_live),
                            len(getattr(factor_cov_live, "factor_names", [])),
                        )
                    else:
                        LOGGER.warning("Factor model: no return matrix, skipping covariance estimation")
                else:
                    LOGGER.warning("Factor model: no factor columns loaded from DB")
            except Exception:
                LOGGER.warning(
                    "Factor model setup failed for live pipeline",
                    exc_info=True,
                )
        set_directional_win_rates = getattr(builder, "set_directional_win_rates", None)
        if callable(set_directional_win_rates):
            set_directional_win_rates(directional_win_rates)
        set_liquidity_data = getattr(builder, "set_liquidity_data", None)
        if liquidity_gate is not None and callable(set_liquidity_data):
            set_liquidity_data(
                liquidity_gate,
                spread_snapshots=spread_snapshots,
                borrow_snapshots=borrow_snapshots,
            )
        # ── Section 17 Point 9 : covariance PIT → PortfolioOptimizer ────
        _wire_covariance_to_optimizer(
            builder,
            factor_cov_live=(
                builder._factor_covariance
                if hasattr(builder, "_factor_covariance")
                else None
            ),
            operational_snapshot=operational_snapshot,
            directional_win_rates=directional_win_rates,
            config=config,
        )
        builder.progress_callback = emit_run_summary

        # ── Section 17 Point 6.4 : gate de fraîcheur avant entrées ───────
        freshness_blocked = False
        freshness_result = None
        if not config.dry_run:
            try:
                from risk_management.freshness_gate import FreshnessConfig, FreshnessGate

                # Collecter les timestamps de fraîcheur disponibles
                now = datetime.now(timezone.utc)
                # Prix : utiliser la date de trade comme proxy (données EOD jour J)
                price_data_at = datetime.combine(trade_date, datetime.min.time(), tzinfo=timezone.utc) if trade_date else None
                # Modèle ML : dernière prédiction la plus récente
                ml_timestamps = [
                    p.prediction_date for p in predictions.values()
                    if p.prediction_date is not None
                ]
                ml_model_at = max(ml_timestamps) if ml_timestamps else None
                if ml_model_at and not isinstance(ml_model_at, datetime):
                    ml_model_at = None
                # Régime : snapshot du jour
                regime_at = datetime.combine(trade_date, datetime.min.time(), tzinfo=timezone.utc) if trade_date else None

                fg = FreshnessGate(FreshnessConfig())
                freshness_result = fg.evaluate(
                    price_data_at=price_data_at,
                    volume_adv_at=price_data_at,  # même source que les prix
                    earnings_at=None,  # pas encore de source PIT pour earnings
                    corporate_actions_at=None,
                    ml_model_at=ml_model_at,
                    calibration_at=ml_model_at,  # calibration même timestamp que modèle
                    market_regime_at=regime_at,
                    borrow_at=None,  # pas encore de source PIT pour borrow
                    reference_time=now,
                )
                if freshness_result.must_block:
                    freshness_blocked = True
                    LOGGER.warning(
                        "FRESHNESS_GATE_BLOCK blocked_dimensions=%s",
                        list(freshness_result.blocked_dimensions),
                    )
            except Exception:
                LOGGER.warning("FreshnessGate evaluation failed", exc_info=True)

        if freshness_blocked:
            entries = []
            LOGGER.warning(
                "PORTFOLIO_SKIPPED_FRESHNESS_GATE reason=%s",
                "critical_data_stale",
            )
        else:
            entries = builder.build_from_ml_candidates(
                candidates, prices,
                win_rates=win_rates,
                directional_win_rates=directional_win_rates,
                return_matrix=return_matrix,
                trade_date=trade_date,
            )
        _emit_live_progress(
            dict(progress_context, targeted_symbols=len(candidates), built_entries=len(entries)),
            current=7,
            total=progress_total_steps,
            label="🛡️ Progression risk management — portefeuille construit",
            phase="build_portfolio",
        )
    else:
        regime_entries_blocked = universe_symbol_count if not regime_allow_new_entries else 0
        mlops_entries_blocked = universe_symbol_count if not mlops_allows_new_entries else 0
        candidates = []
        prices = {}
        predictions = {}
        win_rates = {}
        return_matrix = pd.DataFrame()
        entries = []
        ml_coverage_gate = evaluate_ml_coverage_gate(
            selection_count=universe_symbol_count,
            prediction_count=0,
            min_coverage_ratio=args.min_ml_coverage_ratio,
            regime_allows_new_entries=entry_gate_allows_new_entries,
            ml_gate_enabled=ml_gate_state.enabled,
        )
        _emit_live_progress(
            dict(progress_context, targeted_symbols=universe_symbol_count, price_symbols=0),
            current=3,
            total=progress_total_steps,
            label="🛡️ Progression risk management — chargement prix & ATR",
            phase="load_prices",
        )
        _emit_live_progress(
            dict(progress_context, targeted_symbols=universe_symbol_count, prediction_symbols=0),
            current=4,
            total=progress_total_steps,
            label="🛡️ Progression risk management — chargement des prédictions ML",
            phase="load_predictions",
        )
        _emit_live_progress(
            dict(progress_context, targeted_symbols=universe_symbol_count, win_rate_symbols=0),
            current=5,
            total=progress_total_steps,
            label="🛡️ Progression risk management — chargement des win rates",
            phase="load_win_rates",
        )
        _emit_live_progress(
            dict(progress_context, targeted_symbols=universe_symbol_count, return_matrix_rows=0, return_matrix_columns=0),
            current=6,
            total=progress_total_steps,
            label="🛡️ Progression risk management — chargement de la matrice de rendements",
            phase="load_return_matrix",
        )
        LOGGER.warning(
            "Les gates d'entrée bloquent les nouvelles cibles | regime_allowed=%s mlops_allowed=%s candidats_bloques=%d",
            regime_allow_new_entries,
            mlops_allows_new_entries,
            universe_symbol_count,
        )
        _emit_live_progress(
            dict(progress_context, targeted_symbols=universe_symbol_count, built_entries=0, entries_blocked_by_regime=regime_entries_blocked),
            current=7,
            total=progress_total_steps,
            label="🛡️ Progression risk management — portefeuille construit",
            phase="build_portfolio",
        )

    preflight_data_quality = _build_preflight_data_quality(
        trade_date=trade_date,
        account_snapshot=account_snapshot,
        effective_equity=effective_equity,
        requested_equity=requested_equity,
        equity_breakdown=equity_breakdown,
        selections=candidates,
        prices=prices,
        return_matrix=return_matrix,
        regime_allow_new_entries=regime_allow_new_entries,
    )

    run_id = build_run_id()
    shadow_compare_summary = _run_shadow_compare(
        enabled=bool(args.enable_shadow_compare or run_mode is RiskRunMode.SHADOW),
        reference_run_id=str(args.shadow_compare_run_id or "").strip() or None,
        trade_date=trade_date,
        run_id=run_id,
        account_id=effective_account_id or resolved_account_scope,
        entries=entries,
        repo=repo,
        dry_run=bool(config.dry_run),
    )
    model_run_ids = sorted({str(prediction.run_id) for prediction in predictions.values() if prediction.run_id})
    decision_audit_path = persist_decision_audit_log(
        entries,
        run_id=run_id,
        trade_date=trade_date,
        config_fingerprint=config.fingerprint,
        model_run_id="|".join(model_run_ids),
        regime_mode=str(getattr(regime_snapshot, "mode", "normal") or "normal"),
    )
    _print_summary(entries, run_id, trade_date)

    n_dec = 0
    n_tgt = 0
    if config.dry_run:
        LOGGER.info("Mode dry-run — aucune ecriture métier en DB (hors caches/télémétrie best-effort).")
    else:
        n_dec = persist_decisions(repo, entries, run_id, trade_date, account_id=effective_account_id or resolved_account_scope)
        n_tgt = persist_portfolio_targets(repo, entries, run_id, trade_date, account_id=effective_account_id or resolved_account_scope)
        LOGGER.info("Ecrit %d decisions et %d cibles en DB.", n_dec, n_tgt)

    _emit_live_progress(
        dict(
            progress_context,
            targeted_symbols=len(entries),
            persisted_decisions=0 if config.dry_run else int(n_dec),
            persisted_targets=0 if config.dry_run else int(n_tgt),
        ),
        current=8,
        total=progress_total_steps,
        label="🛡️ Progression risk management — finalisation",
        phase="persist_results",
    )

    accepted_entries = [entry for entry in entries if entry.approved_shares > 0 and str(entry.decision).upper() == "ACCEPTED"]
    reduced_entries = [entry for entry in entries if entry.approved_shares > 0 and str(entry.decision).upper() == "REDUCED"]
    rejected_entries = [entry for entry in entries if entry.approved_shares == 0]
    retained_entries = [entry for entry in entries if entry.approved_shares > 0]
    conviction_weights_calibration = _build_conviction_weights_calibration(
        candidates,
        retained_entries,
        empirical_risk_calibration=empirical_risk_calibration,
    )
    total_target_notional = sum(entry.target_notional for entry in retained_entries)
    gross_exposure_pct = (total_target_notional / effective_equity) if effective_equity > 0 else 0.0
    max_target_weight = max((entry.target_weight for entry in retained_entries), default=0.0)
    sector_weights: dict[str, float] = {}
    for entry in retained_entries:
        sector_weights[entry.sector] = sector_weights.get(entry.sector, 0.0) + entry.target_weight
    max_sector_weight_realized = max(sector_weights.values(), default=0.0)
    total_initial_risk_dollars = sum(float(entry.initial_risk_dollars or 0.0) for entry in retained_entries)
    total_risk_budget_dollars = sum(float(entry.risk_budget_dollars or 0.0) for entry in retained_entries)
    atr_available_symbols = sum(1 for entry in entries if entry.atr_20 is not None and entry.atr_20 > 0)
    prediction_available_symbols = sum(1 for entry in entries if entry.predicted_proba is not None)
    atr_coverage_pct = (atr_available_symbols / len(entries)) if entries else 0.0
    prediction_coverage_pct = (prediction_available_symbols / len(entries)) if entries else 0.0
    rejection_reason_counts = dict(Counter(str(entry.decision_reason or "").strip() or "UNKNOWN" for entry in rejected_entries))
    rejection_reason_code_counts = dict(
        Counter(str(entry.decision_reason_code or "").strip() or "unknown" for entry in rejected_entries)
    )
    reduction_reason_code_counts = dict(
        Counter(str(entry.decision_reason_code or "").strip() or "unknown" for entry in reduced_entries)
    )
    # Sprint S3 / A-010 — télémétrie sizing : on agrège par ``sizing_method``
    # (tagué dans ``risk_management.position_sizer``) pour exposer combien de
    # candidats ont été rejetés faute d'ATR ou faute de notional minimum.
    sizing_method_counts: dict[str, int] = dict(
        Counter(str(getattr(entry, "sizing_method", "") or "").strip() or "unknown" for entry in entries)
    )
    selector_signal_mode_counts = dict(
        Counter(
            str(getattr(candidate, "selector_signal_mode", "") or "").strip() or "unknown"
            for candidate in candidates
        )
    )
    retained_selector_signal_mode_counts = dict(
        Counter(
            str(getattr(entry, "selector_signal_mode", "") or "").strip() or "unknown"
            for entry in retained_entries
        )
    )
    selection_rank_available = sum(1 for candidate in candidates if getattr(candidate, "selection_rank", None) is not None)
    selection_earnings_blackout_count = sum(
        1
        for candidate in candidates
        if int(getattr(candidate, "selector_earnings_blackout", 0) or 0) > 0
    )
    rejected_for_atr_missing = int(sizing_method_counts.get("rejected_atr_missing", 0))
    rejected_for_notional_below_enforced = int(sizing_method_counts.get("rejected_notional_below_enforced", 0))
    rejected_for_notional = int(sizing_method_counts.get("rejected_notional", 0)) + rejected_for_notional_below_enforced
    rejected_for_zero_shares = int(sizing_method_counts.get("rejected_zero_shares", 0))
    rejected_for_invalid_price = int(sizing_method_counts.get("rejected_invalid_price", 0))
    postmortem_artifacts = _build_postmortem_artifacts(
        candidates=candidates,
        entries=entries,
        retained_entries=retained_entries,
        rejection_reason_code_counts=rejection_reason_code_counts,
        reduction_reason_code_counts=reduction_reason_code_counts,
        prices=prices,
        predictions=predictions,
        win_rates=win_rates,
        return_matrix=return_matrix,
        regime_snapshot_payload=regime_snapshot_payload,
        config=config,
        regime_allow_new_entries=regime_allow_new_entries,
    )
    finished_at = datetime.now()
    summary = {
        "run_id": run_id,
        "trade_date": trade_date.isoformat(),
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "loaded_candidates": len(candidates),
        "targeted_symbols": len(entries),
        "accepted_symbols": len(accepted_entries),
        "reduced_symbols": len(reduced_entries),
        "rejected_symbols": len(rejected_entries),
        "entries_blocked_by_regime": regime_entries_blocked,
        "entries_blocked_by_mlops": mlops_entries_blocked,
        "target_positions": len(retained_entries),
        "total_target_shares": normalize_share_quantity(sum(entry.approved_shares for entry in retained_entries)),
        "total_target_notional": round(total_target_notional, 2),
        "gross_exposure_pct": round(gross_exposure_pct, 4),
        "max_target_weight": round(max_target_weight, 4),
        "max_sector_weight_realized": round(max_sector_weight_realized, 4),
        "total_initial_risk_dollars": round(total_initial_risk_dollars, 2),
        "total_risk_budget_dollars": round(total_risk_budget_dollars, 2),
        "atr_available_symbols": atr_available_symbols,
        "prediction_available_symbols": prediction_available_symbols,
        "atr_coverage_pct": round(atr_coverage_pct, 4),
        "prediction_coverage_pct": round(prediction_coverage_pct, 4),
        "rejection_reason_counts": rejection_reason_counts,
        "rejection_reason_code_counts": rejection_reason_code_counts,
        "reduction_reason_code_counts": reduction_reason_code_counts,
        # Sprint S3 / A-010 — télémétrie sizing dédiée (visible IHM/CI).
        "rejected_for_atr_missing": rejected_for_atr_missing,
        "rejected_for_notional": rejected_for_notional,
        "rejected_for_notional_below_enforced": rejected_for_notional_below_enforced,
        "rejected_for_zero_shares": rejected_for_zero_shares,
        "rejected_for_invalid_price": rejected_for_invalid_price,
        "sizing_method_counts": sizing_method_counts,
        "selector_signal_mode_counts": selector_signal_mode_counts,
        "retained_selector_signal_mode_counts": retained_selector_signal_mode_counts,
        "selection_rank_available": selection_rank_available,
        "selection_rank_coverage_pct": round((selection_rank_available / len(candidates)), 4) if candidates else 0.0,
        "selection_earnings_blackout_count": selection_earnings_blackout_count,
        # Sprint S3 / A-011 — visibilité des seuils circuit breaker effectifs.
        "circuit_breaker_thresholds": {
            "max_portfolio_drawdown_pct": float(config.max_portfolio_drawdown_pct),
            "max_daily_loss_pct": float(config.max_daily_loss_pct),
            "rolling_peak_window_days": int(config.rolling_peak_window_days),
            "degraded_entry_allocation_pct": float(config.degraded_entry_allocation_pct),
        },
        "vol_targeting": vol_target_state.to_summary(),
        "ml_coverage_gate": ml_coverage_gate.to_summary(),
        "risk_controls_effective": {
            "risk_multiplier": float(config.risk_multiplier),
            "effective_max_positions": int(config.effective_max_positions),
            "effective_min_notional": float(config.effective_min_notional),
            "max_gross_exposure": float(config.max_gross_exposure),
            "max_tickers_per_sector": int(config.max_tickers_per_sector) if config.max_tickers_per_sector is not None else None,
        },
        "dry_run": bool(config.dry_run),
        "run_mode": run_mode.value,
        "effective_equity": round(float(effective_equity), 2),
        "account_equity": round(float(args.account_equity), 2),
        "equity_source": equity_source,
        "equity_fallback_used": equity_fallback_used,
        "snapshot_freshness_days": snapshot_freshness_days,
        "account_snapshot_trade_date": account_snapshot.trade_date.isoformat() if account_snapshot is not None else None,
        "circuit_breaker_active": circuit_breaker.is_active(),
        # Rotation factor (Priorité 5)
        "rotation_factor": {
            "enabled": True,
            "ready": rotation_state.is_ready(),
            "triggered": rotation_state.should_rotate(),
            "cumulative_return": rotation_state.cumulative_return(),
            "data_points": len(rotation_state._daily_returns),
            "lookback_weeks": rotation_state.lookback_weeks,
            "threshold": rotation_state.threshold,
        },
        "breakout_factor": breakout_tracker.to_summary(),
        "regime_snapshot_applied": regime_snapshot is not None,
        "regime_mode": regime_snapshot_payload.get("mode") if regime_snapshot_payload else None,
        "regime_allow_new_entries": regime_allow_new_entries,
        "mlops_allows_new_entries": mlops_allows_new_entries,
        "entry_gate_allows_new_entries": entry_gate_allows_new_entries,
        "regime_reasons": list(regime_snapshot_payload.get("reasons") or []) if regime_snapshot_payload else [],
        "regime_snapshot": regime_snapshot_payload,
        "regime_transition": regime_transition.to_dict() if regime_transition is not None else None,
        # ── Section 17 Point 8 : snapshot opérationnel et plan de transition ──
        "operational_snapshot": {
            "available": operational_snapshot is not None,
            "account_id": operational_snapshot.account.account_id if operational_snapshot is not None else None,
            "equity": round(float(operational_snapshot.account.equity), 2) if operational_snapshot is not None else None,
            "buying_power": round(float(operational_snapshot.account.buying_power), 2) if operational_snapshot is not None else None,
            "positions_count": len(operational_snapshot.positions) if operational_snapshot is not None else 0,
            "open_orders_count": len(operational_snapshot.open_orders) if operational_snapshot is not None else 0,
            "source": operational_snapshot.account.source if operational_snapshot is not None else None,
            "as_of": operational_snapshot.account.as_of.isoformat() if operational_snapshot is not None and operational_snapshot.account.as_of is not None else None,
        },
        # ── Section 17 Point 9 : liquidité et borrow ────────────────────
        "liquidity_market_data": {
            "spread_symbols_loaded": len(spread_snapshots),
            "borrow_symbols_loaded": len(borrow_snapshots),
            "borrow_etb_count": sum(1 for b in borrow_snapshots.values() if hasattr(b, "status") and str(getattr(b, "status", "")).startswith("easy")),
            "borrow_htb_count": sum(1 for b in borrow_snapshots.values() if hasattr(b, "status") and str(getattr(b, "status", "")).startswith("hard")),
            "borrow_not_shortable_count": sum(1 for b in borrow_snapshots.values() if hasattr(b, "status") and str(getattr(b, "status", "")).startswith("not")),
            "liquidity_gate_active": liquidity_gate is not None,
        },
        "transition_plan": transition_plan.to_dict() if transition_plan is not None and hasattr(transition_plan, "to_dict") else None,
        # ── Section 17 Point 8 / Point 15 : réconciliation quotidienne ──
        "daily_reconciliation": _build_reconciliation_summary(
            trade_date=trade_date,
            operational_snapshot=operational_snapshot,
            target_entries=retained_entries,
        ),
        # ── Section 17 Point 2.4 : rapport qualité quotidien ────────────
        "daily_quality_report_path": daily_quality_report_path,
        "preflight_data_quality": preflight_data_quality,
        # Phase 5.1.a — décomposition equity (cash + positions + dividendes ledger)
        "account_equity_breakdown": equity_breakdown,
        # Phase 5.1.b — pondérations conviction unifiées via core.conviction
        "conviction_weights": {
            "score_weight": float(config.score_weight),
            "prediction_weight": float(config.prediction_weight),
            "source": "core.conviction",
            "effective_policy": "quant_only" if not ml_gate_state.enabled else "score_plus_ml",
        },
        # Phase 5.1.c / P3 — traçabilité calibration upstream effectivement transportée.
        "conviction_weights_calibration": conviction_weights_calibration,
        "empirical_risk_calibration": empirical_risk_calibration,
        "shadow_compare": shadow_compare_summary,
        "decision_audit_log_path": str(decision_audit_path),
        "postmortem_artifacts": postmortem_artifacts,
        **ml_gate_state.to_summary(),
    }
    summary = attach_schema_version(summary, version=1)

    # Persister l'état du breakout tracker pour le prochain run live
    try:
        _breakout_state_path.parent.mkdir(parents=True, exist_ok=True)
        _breakout_state_path.write_text(
            json.dumps(breakout_tracker.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        LOGGER.info("Breakout tracker saved: %s", breakout_tracker.to_summary())
    except Exception:
        LOGGER.warning("Breakout tracker save failed.", exc_info=True)

    persist_run_business_summary(
        summary=summary,
        step_key="risk_management",
        run_kind="step",
        status="completed",
        summary_run_id=run_id,
        entity_run_id=run_id,
        account_id=effective_account_id or resolved_account_scope,
        trade_date=trade_date,
        started_at=started_at,
        finished_at=finished_at,
    )
    emit_run_summary(summary)


if __name__ == "__main__":
    raise SystemExit(main())

