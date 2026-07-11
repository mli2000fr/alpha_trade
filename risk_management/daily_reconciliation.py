"""risk_management/daily_reconciliation.py — Réconciliation quotidienne (Sprint Maître 15).

Réconcilie quotidiennement :
1. Ordres (intentions vs soumissions vs fills)
2. Positions (attendues vs réelles)
3. Protections (stops, TP, OCO — existants et valides)
4. PnL (calculé vs rapporté par le broker)
5. Cash (ledger vs broker)

Usage ::

    from risk_management.daily_reconciliation import (
        DailyReconciliation, ReconciliationReport, ReconStatus,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


# ── ReconStatus ─────────────────────────────────────────────────────────────


class ReconStatus(StrEnum):
    """Statut de réconciliation (Sprint Maître 15)."""

    MATCHED = "matched"
    MISMATCHED = "mismatched"
    PENDING = "pending"
    FAILED = "failed"


# ── ReconItem ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReconItem:
    """Un élément de réconciliation (Sprint Maître 15)."""

    category: str  # orders, positions, protections, pnl, cash
    item_id: str
    expected_value: object
    actual_value: object
    status: ReconStatus = ReconStatus.PENDING
    delta: str = ""
    detail: str = ""

    @property
    def is_matched(self) -> bool:
        return self.status == ReconStatus.MATCHED

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "item_id": self.item_id,
            "status": self.status.value,
            "delta": self.delta,
            "detail": self.detail,
        }


# ── ReconciliationReport ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Rapport de réconciliation quotidien (Sprint Maître 15).

    Attributes
    ----------
    trade_date : date
    timestamp : datetime
    overall_status : ReconStatus
    total_items : int
    matched_items : int
    mismatched_items : int
    items : tuple[ReconItem, ...]
    categories : dict[str, ReconStatus]
    summary : str
    requires_operator_action : bool
    """

    trade_date: date
    timestamp: datetime = field(default_factory=datetime.now)
    overall_status: ReconStatus = ReconStatus.PENDING
    total_items: int = 0
    matched_items: int = 0
    mismatched_items: int = 0
    items: tuple[ReconItem, ...] = ()
    categories: dict[str, ReconStatus] = field(default_factory=dict)
    summary: str = ""
    requires_operator_action: bool = False

    @property
    def match_rate(self) -> float:
        if self.total_items == 0:
            return 1.0
        return self.matched_items / self.total_items

    @property
    def is_clean(self) -> bool:
        """True si tout est réconcilié (100% match)."""
        return self.overall_status == ReconStatus.MATCHED and self.mismatched_items == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "trade_date": self.trade_date.isoformat(),
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status.value,
            "total_items": self.total_items,
            "matched_items": self.matched_items,
            "mismatched_items": self.mismatched_items,
            "match_rate": round(self.match_rate, 4),
            "is_clean": self.is_clean,
            "requires_operator_action": self.requires_operator_action,
            "summary": self.summary,
            "categories": {k: v.value for k, v in self.categories.items()},
            "items": [i.to_dict() for i in self.items],
        }


# ── DailyReconciliation ─────────────────────────────────────────────────────


@dataclass
class DailyReconciliation:
    """Moteur de réconciliation quotidien (Sprint Maître 15).

    Compare 5 dimensions :
    1. Ordres : intentions vs soumissions vs fills
    2. Positions : cibles vs portefeuille réel
    3. Protections : stops/TP/OCO existants et valides
    4. PnL : calculé vs broker
    5. Cash : ledger vs broker

    Le moteur est PUR : il compare des données déjà extraites.
    """

    def reconcile(
        self,
        trade_date: date,
        *,
        intended_orders: list[dict[str, object]] | None = None,
        submitted_orders: list[dict[str, object]] | None = None,
        fills: list[dict[str, object]] | None = None,
        target_positions: list[dict[str, object]] | None = None,
        actual_positions: list[dict[str, object]] | None = None,
        expected_protections: list[dict[str, object]] | None = None,
        actual_protections: list[dict[str, object]] | None = None,
        calculated_pnl: float | None = None,
        broker_pnl: float | None = None,
        calculated_cash: float | None = None,
        broker_cash: float | None = None,
    ) -> ReconciliationReport:
        """Exécute la réconciliation complète.

        Returns
        -------
        ReconciliationReport
        """
        items: list[ReconItem] = []
        cat_statuses: dict[str, ReconStatus] = {}

        # ── 1. Ordres ─────────────────────────────────────────────────
        orders_status = self._reconcile_orders(
            items, intended_orders or [], submitted_orders or [], fills or [],
        )
        cat_statuses["orders"] = orders_status

        # ── 2. Positions ───────────────────────────────────────────────
        pos_status = self._reconcile_positions(
            items, target_positions or [], actual_positions or [],
        )
        cat_statuses["positions"] = pos_status

        # ── 3. Protections ─────────────────────────────────────────────
        prot_status = self._reconcile_protections(
            items, expected_protections or [], actual_protections or [],
        )
        cat_statuses["protections"] = prot_status

        # ── 4. PnL ─────────────────────────────────────────────────────
        pnl_status = self._reconcile_pnl(items, calculated_pnl, broker_pnl)
        cat_statuses["pnl"] = pnl_status

        # ── 5. Cash ────────────────────────────────────────────────────
        cash_status = self._reconcile_cash(items, calculated_cash, broker_cash)
        cat_statuses["cash"] = cash_status

        # ── Synthèse ───────────────────────────────────────────────────
        matched = sum(1 for i in items if i.is_matched)
        mismatched = len(items) - matched
        overall = ReconStatus.MATCHED if mismatched == 0 else ReconStatus.MISMATCHED

        requires_action = any(
            s in (ReconStatus.MISMATCHED, ReconStatus.FAILED)
            for s in cat_statuses.values()
        )

        summary_parts: list[str] = []
        for cat, status in cat_statuses.items():
            if status != ReconStatus.MATCHED:
                cat_matched = sum(1 for i in items if i.category == cat and i.is_matched)
                cat_total = sum(1 for i in items if i.category == cat)
                summary_parts.append(f"{cat}: {cat_matched}/{cat_total} matched")
        if not summary_parts:
            summary_parts.append("Toutes les catégories sont réconciliées")

        return ReconciliationReport(
            trade_date=trade_date,
            overall_status=overall,
            total_items=len(items),
            matched_items=matched,
            mismatched_items=mismatched,
            items=tuple(items),
            categories=cat_statuses,
            summary="; ".join(summary_parts),
            requires_operator_action=requires_action,
        )

    # ── Private reconcilers ────────────────────────────────────────────

    def _reconcile_orders(
        self,
        items: list[ReconItem],
        intended: list[dict[str, object]],
        submitted: list[dict[str, object]],
        fills: list[dict[str, object]],
    ) -> ReconStatus:
        intended_ids = {str(o.get("intent_id", "")) for o in intended}
        submitted_ids = {str(o.get("intent_id", "")) for o in submitted}
        fill_intent_ids = {str(f.get("intent_id", "")) for f in fills}

        # Intentions non soumises
        for iid in intended_ids - submitted_ids:
            items.append(ReconItem("orders", iid, "intended", "not_submitted",
                                   ReconStatus.MISMATCHED, delta="missing_submission",
                                   detail="Intention non soumise au broker"))

        # Soumissions sans intention
        for sid in submitted_ids - intended_ids:
            items.append(ReconItem("orders", sid, "none", "submitted",
                                   ReconStatus.MISMATCHED, delta="orphan_submission",
                                   detail="Soumission sans intention correspondante"))

        # Intentions non fillées
        for iid in intended_ids & submitted_ids - fill_intent_ids:
            items.append(ReconItem("orders", iid, "submitted", "not_filled",
                                   ReconStatus.MISMATCHED, delta="pending_fill",
                                   detail="Ordre soumis mais pas encore filled"))

        # Fills sans intention
        for fid in fill_intent_ids - intended_ids:
            items.append(ReconItem("orders", fid, "none", "filled",
                                   ReconStatus.MISMATCHED, delta="orphan_fill",
                                   detail="Fill sans intention correspondante"))

        # Matchs parfaits
        for iid in intended_ids & submitted_ids & fill_intent_ids:
            items.append(ReconItem("orders", iid, "filled", "filled",
                                   ReconStatus.MATCHED, detail="Ordre réconcilié"))

        mismatched = sum(1 for i in items if i.category == "orders" and not i.is_matched)
        return ReconStatus.MISMATCHED if mismatched > 0 else ReconStatus.MATCHED

    def _reconcile_positions(
        self,
        items: list[ReconItem],
        targets: list[dict[str, object]],
        actuals: list[dict[str, object]],
    ) -> ReconStatus:
        target_by_sym = {str(p["symbol"]): p for p in targets}
        actual_by_sym = {str(p["symbol"]): p for p in actuals}

        all_syms = set(target_by_sym.keys()) | set(actual_by_sym.keys())

        for sym in sorted(all_syms):
            t = target_by_sym.get(sym, {})
            a = actual_by_sym.get(sym, {})

            t_qty = float(t.get("quantity", 0))
            a_qty = float(a.get("quantity", 0))
            t_side = str(t.get("side", ""))
            a_side = str(a.get("side", ""))

            if not t:
                items.append(ReconItem("positions", sym, "none", f"qty={a_qty}",
                                       ReconStatus.MISMATCHED, delta="extra_position",
                                       detail="Position non ciblée"))
            elif not a:
                items.append(ReconItem("positions", sym, f"qty={t_qty}", "none",
                                       ReconStatus.MISMATCHED, delta="missing_position",
                                       detail="Position cible non trouvée"))
            elif t_side != a_side:
                items.append(ReconItem("positions", sym, f"{t_side} {t_qty}", f"{a_side} {a_qty}",
                                       ReconStatus.MISMATCHED, delta="side_mismatch",
                                       detail=f"Côté différent: target={t_side} actual={a_side}"))
            elif abs(t_qty - a_qty) > 0.01:
                items.append(ReconItem("positions", sym, f"qty={t_qty}", f"qty={a_qty}",
                                       ReconStatus.MISMATCHED, delta=f"{t_qty - a_qty:.1f}",
                                       detail=f"Quantité différente: Δ={t_qty - a_qty:.1f}"))
            else:
                items.append(ReconItem("positions", sym, f"qty={t_qty}", f"qty={a_qty}",
                                       ReconStatus.MATCHED))

        mismatched = sum(1 for i in items if i.category == "positions" and not i.is_matched)
        return ReconStatus.MISMATCHED if mismatched > 0 else ReconStatus.MATCHED

    def _reconcile_protections(
        self,
        items: list[ReconItem],
        expected: list[dict[str, object]],
        actuals: list[dict[str, object]],
    ) -> ReconStatus:
        expected_ids = {str(p.get("oco_id", "")): p for p in expected}
        actual_ids = {str(p.get("oco_id", "")): p for p in actuals}

        # Protections manquantes
        for oid in expected_ids.keys() - actual_ids.keys():
            items.append(ReconItem("protections", oid, "expected", "missing",
                                   ReconStatus.MISMATCHED, delta="missing_protection",
                                   detail="Protection attendue non trouvée"))

        # Protections orphelines
        for oid in actual_ids.keys() - expected_ids.keys():
            items.append(ReconItem("protections", oid, "none", "present",
                                   ReconStatus.MISMATCHED, delta="orphan_protection",
                                   detail="Protection sans cible correspondante"))

        # Protections OK
        for oid in expected_ids.keys() & actual_ids.keys():
            items.append(ReconItem("protections", oid, "present", "present",
                                   ReconStatus.MATCHED, detail="Protection réconciliée"))

        mismatched = sum(1 for i in items if i.category == "protections" and not i.is_matched)
        return ReconStatus.MISMATCHED if mismatched > 0 else ReconStatus.MATCHED

    @staticmethod
    def _reconcile_pnl(
        items: list[ReconItem],
        calculated: float | None,
        broker: float | None,
    ) -> ReconStatus:
        if calculated is None and broker is None:
            return ReconStatus.PENDING
        if calculated is None or broker is None:
            items.append(ReconItem("pnl", "pnl", str(calculated), str(broker),
                                   ReconStatus.MISMATCHED, delta="missing_data"))
            return ReconStatus.MISMATCHED

        delta = calculated - broker
        if abs(delta) > 0.01:
            items.append(ReconItem("pnl", "pnl", f"{calculated:.2f}", f"{broker:.2f}",
                                   ReconStatus.MISMATCHED, delta=f"{delta:.2f}",
                                   detail=f"PnL diffère de ${delta:.2f}"))
            return ReconStatus.MISMATCHED
        else:
            items.append(ReconItem("pnl", "pnl", f"{calculated:.2f}", f"{broker:.2f}",
                                   ReconStatus.MATCHED))
            return ReconStatus.MATCHED

    @staticmethod
    def _reconcile_cash(
        items: list[ReconItem],
        calculated: float | None,
        broker: float | None,
    ) -> ReconStatus:
        if calculated is None and broker is None:
            return ReconStatus.PENDING
        if calculated is None or broker is None:
            items.append(ReconItem("cash", "cash", str(calculated), str(broker),
                                   ReconStatus.MISMATCHED, delta="missing_data"))
            return ReconStatus.MISMATCHED

        delta = calculated - broker
        if abs(delta) > 0.01:
            items.append(ReconItem("cash", "cash", f"{calculated:.2f}", f"{broker:.2f}",
                                   ReconStatus.MISMATCHED, delta=f"{delta:.2f}",
                                   detail=f"Cash diffère de ${delta:.2f}"))
            return ReconStatus.MISMATCHED
        else:
            items.append(ReconItem("cash", "cash", f"{calculated:.2f}", f"{broker:.2f}",
                                   ReconStatus.MATCHED))
            return ReconStatus.MATCHED
