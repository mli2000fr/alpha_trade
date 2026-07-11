"""Journalisation des décisions de risque et portefeuille cible."""
from __future__ import annotations

import logging
import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy.engine import Engine

from risk_management.db_io import RiskRepository
from risk_management.models import PortfolioEntry
from risk_management.decision_fingerprint import (
    AuditLogEntry,
    DecisionAuditLog,
    DecisionFingerprint,
    build_position_fingerprint,
)

LOGGER = logging.getLogger(__name__)


def build_run_id() -> str:
    """Génère un identifiant unique de run."""
    return uuid.uuid4().hex[:16]


def persist_decision_audit_log(
    entries: list[PortfolioEntry],
    *,
    run_id: str,
    trade_date: date,
    config_fingerprint: str,
    model_run_id: str,
    regime_mode: str,
    output_dir: Path = Path("artifacts/risk_decision_audit"),
) -> Path:
    """Persiste le journal rejouable d'une décision live de façon atomique."""
    universe_fingerprint = ",".join(sorted(entry.symbol for entry in entries))
    decision_fingerprint = DecisionFingerprint(
        trade_date=trade_date,
        run_id=run_id,
        config_fingerprint=config_fingerprint,
        model_run_id=model_run_id,
        policy_version=1,
        universe_fingerprint=universe_fingerprint,
        regime_mode=regime_mode,
        candidate_count=len(entries),
    )
    audit_log = DecisionAuditLog(
        trade_date=trade_date,
        run_id=run_id,
        decision_fingerprint=decision_fingerprint,
    )
    decision_timestamp = datetime.combine(trade_date, datetime.min.time())
    for entry in entries:
        side = "short" if entry.side == "sell" else "long"
        position_fingerprint = build_position_fingerprint(
            entry.symbol,
            side,
            decision_fingerprint.fingerprint,
            predicted_proba=float(entry.predicted_proba or 0.0),
            p_side=float(entry.predicted_proba or 0.0),
            price=float(entry.entry_price),
            atr=entry.atr_20,
            config_fingerprint=config_fingerprint,
        )
        audit_log.add_entry(AuditLogEntry(
            trade_date=trade_date,
            timestamp=decision_timestamp,
            run_id=run_id,
            symbol=entry.symbol,
            side=side,
            decision=str(entry.decision),
            reason=entry.decision_reason,
            proposed_shares=float(entry.proposed_shares),
            approved_shares=float(entry.approved_shares),
            entry_price=float(entry.entry_price),
            stop_price=entry.stop_price_initial,
            fingerprint=position_fingerprint.fingerprint,
            predicted_proba=entry.predicted_proba,
            atr=entry.atr_20,
            config_fingerprint=config_fingerprint,
            model_run_id=model_run_id,
        ))

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{trade_date.isoformat()}_{run_id}.json"
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(audit_log.to_dict(), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    os.replace(temporary_path, path)
    return path


def persist_decisions(
    repo: RiskRepository,
    entries: list[PortfolioEntry],
    run_id: str,
    trade_date: date,
    account_id: str | None = None,
) -> int:
    """Écrit toutes les décisions dans risk_decisions."""
    records: list[dict[str, Any]] = [
        {
            "run_id": run_id,
            "trade_date": trade_date,
            "symbol": e.symbol,
            "decision": e.decision,
            "reason": e.decision_reason,
            "reason_code": e.decision_reason_code,
            "score_used": e.score_used,
            "score_source": e.score_source,
            "entry_price": e.entry_price,
            "atr_20": e.atr_20,
            "proposed_shares": e.proposed_shares,
            "approved_shares": e.approved_shares,
            "target_weight": e.target_weight,
            "sector": e.sector,
            "side": e.side,
            # --- V2 audit fields ---
            "conviction_score": e.conviction_score,
            "predicted_proba": e.predicted_proba,
            "historical_win_rate": e.historical_win_rate,
            "effective_probability": e.effective_probability,
            "kelly_fraction": e.kelly_fraction,
            "sizing_method": e.sizing_method,
            "correlation_blocker": e.correlation_blocker,
            "correlation_value": e.correlation_value,
            "company_idio_score": e.company_idio_score,
            "macro_regime_score": e.macro_regime_score,
            "company_idio_signal_norm": e.company_idio_signal_norm,
            "macro_regime_signal_norm": e.macro_regime_signal_norm,
            "company_idio_component": e.company_idio_component,
            "macro_regime_component": e.macro_regime_component,
            "quant_component": e.quant_component,
            "walk_forward_sentiment_weight": e.walk_forward_sentiment_weight,
            "walk_forward_macro_weight": e.walk_forward_macro_weight,
            "walk_forward_quant_weight": e.walk_forward_quant_weight,
            "calibration_run_id": e.calibration_run_id,
            "calibration_source": e.calibration_source,
            "selection_rank": e.selection_rank,
            "selector_signal_mode": e.selector_signal_mode,
            "selection_explanation": e.selection_explanation,
            "selector_earnings_blackout": e.selector_earnings_blackout,
            "decision_rank": e.decision_rank,
            "target_notional": e.target_notional,
            "stop_price_initial": e.stop_price_initial,
            "risk_per_share": e.risk_per_share,
            "risk_budget_dollars": e.risk_budget_dollars,
            "initial_risk_dollars": e.initial_risk_dollars,
            "score_snapshot_date": e.score_snapshot_date,
            "price_asof_date": e.price_asof_date,
            "atr_asof_date": e.atr_asof_date,
            "prediction_asof_date": e.prediction_asof_date,
            "ml_metrics_asof_date": e.ml_metrics_asof_date,
        }
        for e in entries
    ]
    written = repo.write_risk_decisions(records, account_id=account_id)
    # Sprint S12.2 — chaîne d'audit HMAC SOX-like (best-effort).
    try:
        from database.audit_chain import AuditChainRepository

        engine = getattr(repo, "engine", None)
        if engine is not None:
            AuditChainRepository(cast(Engine, engine)).append(
                "risk_runs",
                run_id,
                {
                    "run_id": run_id,
                    "trade_date": str(trade_date),
                    "account_id": account_id or "default",
                    "decisions_count": len(records),
                    "approved_count": sum(1 for r in records if (r.get("approved_shares") or 0) > 0),
                    "event": "persist_decisions",
                },
            )
    except Exception:  # noqa: BLE001
        LOGGER.debug("audit_chain append (risk) indisponible run_id=%s", run_id, exc_info=True)
    return written


def persist_portfolio_targets(
    repo: RiskRepository,
    entries: list[PortfolioEntry],
    run_id: str,
    trade_date: date,
    account_id: str | None = None,
) -> int:
    """Écrit le portefeuille cible (entrées ACCEPTED/REDUCED uniquement)."""
    accepted = [e for e in entries if e.approved_shares > 0]
    records: list[dict[str, Any]] = [
        {
            "run_id": run_id,
            "trade_date": trade_date,
            "symbol": e.symbol,
            "shares": e.approved_shares,
            "entry_price": e.entry_price,
            "atr_20": e.atr_20,
            "target_weight": e.target_weight,
            "sector": e.sector,
            "side": e.side,
            "score_used": e.score_used,
            "score_source": e.score_source,
            "reason_code": e.decision_reason_code,
            # --- V2 audit fields ---
            "conviction_score": e.conviction_score,
            "sizing_method": e.sizing_method,
            "kelly_fraction": e.kelly_fraction,
            "company_idio_score": e.company_idio_score,
            "macro_regime_score": e.macro_regime_score,
            "company_idio_signal_norm": e.company_idio_signal_norm,
            "macro_regime_signal_norm": e.macro_regime_signal_norm,
            "company_idio_component": e.company_idio_component,
            "macro_regime_component": e.macro_regime_component,
            "quant_component": e.quant_component,
            "walk_forward_sentiment_weight": e.walk_forward_sentiment_weight,
            "walk_forward_macro_weight": e.walk_forward_macro_weight,
            "walk_forward_quant_weight": e.walk_forward_quant_weight,
            "calibration_run_id": e.calibration_run_id,
            "calibration_source": e.calibration_source,
            "selection_rank": e.selection_rank,
            "selector_signal_mode": e.selector_signal_mode,
            "selection_explanation": e.selection_explanation,
            "selector_earnings_blackout": e.selector_earnings_blackout,
            "decision_rank": e.decision_rank,
            "target_notional": e.target_notional,
            "stop_price_initial": e.stop_price_initial,
            "risk_per_share": e.risk_per_share,
            "risk_budget_dollars": e.risk_budget_dollars,
            "initial_risk_dollars": e.initial_risk_dollars,
            "price_asof_date": e.price_asof_date,
            "atr_asof_date": e.atr_asof_date,
        }
        for e in accepted
    ]
    return repo.write_portfolio_targets(records, account_id=account_id)
