"""Phase C / S16.3 — Détecteur de wash sale (règle US 30 jours).

Implémente la règle IRS Section 1091 (substantially identical security
acheté dans les 30 jours avant ou après la vente à perte) sous une forme
simplifiée mais auditable :

* Une vente d'un lot avec perte est marquée *wash sale* si une autre
  acquisition du même symbole a lieu dans la fenêtre [vente - 30 j ;
  vente + 30 j].
* La perte non déductible est ajoutée au cost basis du lot de
  remplacement le plus proche dans le temps (FIFO en cas d'égalité).

Cette implémentation ne tient pas compte de l'option *short-against-the-box*
ni des splits/CA appliqués entre temps : ces aspects sont déférés à
``corporate_actions/`` pour ajustement préalable du cost basis.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


WASH_WINDOW_DAYS = 30


@dataclass(frozen=True, slots=True)
class Lot:
    """Lot acheté ou vendu (positif = acquisition, négatif = vente)."""
    lot_id: str
    symbol: str
    trade_date: date
    qty: float
    price: float

    @property
    def is_acquisition(self) -> bool:
        return self.qty > 0

    @property
    def is_disposition(self) -> bool:
        return self.qty < 0


@dataclass(frozen=True, slots=True)
class WashSaleAdjustment:
    sale_lot_id: str
    replacement_lot_id: str
    symbol: str
    disallowed_loss: float
    sale_date: date
    replacement_date: date


@dataclass(slots=True)
class WashSaleReport:
    adjustments: list[WashSaleAdjustment] = field(default_factory=list)
    adjusted_cost_basis: dict[str, float] = field(default_factory=dict)

    @property
    def total_disallowed_loss(self) -> float:
        return sum(a.disallowed_loss for a in self.adjustments)


def detect_wash_sales(
    lots: list[Lot],
    realized_pnl_per_sale: dict[str, float] | None = None,
) -> WashSaleReport:
    """Retourne les ajustements wash sale.

    Parameters
    ----------
    lots: list[Lot]
        Tous les mouvements (achats + ventes) pour un compte sur la
        période d'analyse, déjà ajustés des CA.
    realized_pnl_per_sale: dict[lot_id -> realized PnL signed]
        Optionnel : si fourni, utilisé pour identifier les ventes à
        perte (PnL < 0). Sinon, on considère qu'une vente est à perte
        ssi son ``price`` < le ``price`` moyen des achats antérieurs
        du même symbole (best-effort).
    """
    by_symbol: dict[str, list[Lot]] = {}
    for lot in lots:
        by_symbol.setdefault(lot.symbol, []).append(lot)

    report = WashSaleReport()
    for symbol, slots in by_symbol.items():
        slots.sort(key=lambda l: l.trade_date)
        for sale in (l for l in slots if l.is_disposition):
            # PnL réalisé
            if realized_pnl_per_sale is not None:
                pnl = realized_pnl_per_sale.get(sale.lot_id)
                if pnl is None or pnl >= 0:
                    continue
                disallowed = -pnl  # perte → loss positif
            else:
                # heuristique : moyenne pondérée des achats précédents
                prior = [l for l in slots if l.is_acquisition and l.trade_date <= sale.trade_date]
                if not prior:
                    continue
                total_qty = sum(l.qty for l in prior)
                avg = sum(l.qty * l.price for l in prior) / total_qty
                if sale.price >= avg:
                    continue
                disallowed = (avg - sale.price) * abs(sale.qty)

            window = timedelta(days=WASH_WINDOW_DAYS)
            replacements = [
                l for l in slots
                if l.is_acquisition
                and l.lot_id != sale.lot_id
                and abs((l.trade_date - sale.trade_date).days) <= WASH_WINDOW_DAYS
                and (sale.trade_date - window) <= l.trade_date <= (sale.trade_date + window)
            ]
            if not replacements:
                continue
            replacements.sort(
                key=lambda l: (abs((l.trade_date - sale.trade_date).days), l.trade_date)
            )
            replacement = replacements[0]
            report.adjustments.append(
                WashSaleAdjustment(
                    sale_lot_id=sale.lot_id,
                    replacement_lot_id=replacement.lot_id,
                    symbol=symbol,
                    disallowed_loss=disallowed,
                    sale_date=sale.trade_date,
                    replacement_date=replacement.trade_date,
                )
            )
            # report disallowed loss into replacement cost basis
            report.adjusted_cost_basis[replacement.lot_id] = (
                report.adjusted_cost_basis.get(replacement.lot_id, 0.0) + disallowed
            )
    return report

