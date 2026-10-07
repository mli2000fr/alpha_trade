"""Coûts FR configurables et décomposés ; scénarios, pas devis de courtier."""
from __future__ import annotations

from datetime import date
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import yaml

from service.fr.universe_contract_6a import ROOT


def number(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("Coût/paramètre non négatif fini requis")
    return result


def load_cost_profile(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (cfg["schema_version"], cfg["market_code"], cfg["currency"]) != (1, "FR_EQ", "EUR"):
        raise ValueError("Profil de coûts FR/EUR requis")
    if cfg["canonical_writes_enabled"] is not False or cfg["serving_enabled"] is not False:
        raise ValueError("Profil recherche uniquement")
    for value in cfg["commission"].values():
        number(value)
    number(cfg["spread"]["full_bid_ask_bps"])
    fraction = number(cfg["spread"]["charged_fraction_per_execution"])
    if fraction > 1:
        raise ValueError("Fraction de spread invalide")
    number(cfg["slippage"]["bps_per_execution"])
    if cfg["ttf"]["buy_only"] is not True or cfg["ttf"]["unknown_eligibility"] != "block":
        raise ValueError("TTF achat seulement ; inconnus bloquants")
    ranges = sorted(cfg["ttf"]["historical_rates"], key=lambda r: r["from"])
    for i, interval in enumerate(ranges):
        if date.fromisoformat(interval["from"]) > date.fromisoformat(interval["to"]):
            raise ValueError("Intervalle fiscal invalide")
        if i and ranges[i-1]["to"] >= interval["from"]:
            raise ValueError("Taux fiscaux chevauchants")
        if number(interval["rate"]) > 1:
            raise ValueError("Taux fiscal invalide")
    number(cfg["ttf"]["default_rate"])
    return cfg


def resolve_liability(path: Path, *, isin: str, ticker: str, settlement_date: date) -> bool:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data["schema_version"] != 1 or data["market_code"] != "FR_EQ" or data["unknown_policy"] != "block":
        raise ValueError("Contrat de liste fiscale invalide")
    day = settlement_date.isoformat()
    matches = [row for row in data["instruments"] if row["isin"] == isin and row["from"] <= day <= row["to"]]
    if len(matches) != 1:
        raise ValueError(f"Éligibilité TTF inconnue/ambiguë {isin}/{day}")
    row = matches[0]
    if not row.get("evidence") or type(row.get("liable")) is not bool or (row.get("ticker") and row["ticker"] != ticker):
        raise ValueError("Preuve fiscale ou identité incohérente")
    return row["liable"]


def execution_costs(cfg: dict, *, side: str, quantity: int, reference_price: Decimal,
                    settlement_date: date | None = None, issuer_liability: bool | None = None,
                    executed: bool = True, stress_multiplier: Decimal = Decimal(1)) -> dict:
    """Cost against a reference price: caller must not charge these again in fills.

    Applies only to cash LONG orders with no same-ISIN intraday offset, as in
    11-A. General netting belongs to a settlement-group ledger, not this function.
    """
    if side not in ("BUY", "SELL") or type(quantity) is not int or quantity <= 0 or reference_price <= 0 or not reference_price.is_finite():
        raise ValueError("Ordre LONG au comptant invalide")
    stress = number(stress_multiplier)
    if stress < 1:
        raise ValueError("Stress multiplicateur au moins 1")
    if not executed:
        return {k: Decimal(0) for k in ("commission", "spread", "slippage", "taxes", "total")}
    notional = reference_price * quantity
    commission = max(number(cfg["commission"]["minimum_eur"]), number(cfg["commission"]["fixed_eur_per_executed_order"])
                     + notional * number(cfg["commission"]["bps"]) / Decimal(10000)) * stress
    spread = notional * number(cfg["spread"]["full_bid_ask_bps"]) * number(cfg["spread"]["charged_fraction_per_execution"]) / Decimal(10000) * stress
    slippage = notional * number(cfg["slippage"]["bps_per_execution"]) / Decimal(10000) * stress
    taxes = Decimal(0)
    if side == "BUY":
        if settlement_date is None or type(issuer_liability) is not bool:
            raise ValueError("Date de règlement et assujettissement explicite requis")
        matches = [r for r in cfg["ttf"]["historical_rates"] if r["from"] <= settlement_date.isoformat() <= r["to"]]
        if len(matches) > 1:
            raise ValueError("Calendrier fiscal ambigu")
        if not matches and settlement_date < date(2026, 1, 1):
            raise ValueError("Taux historique inconnu")
        rate = number(matches[0]["rate"] if matches else cfg["ttf"]["default_rate"])
        # Modelled executed purchase price includes spread/slippage, but excludes
        # commission. Do not substitute midpoint for the acquisition tax basis.
        acquisition_price = reference_price + (spread + slippage) / quantity
        taxes = quantity * acquisition_price.quantize(Decimal("0.01"), rounding=ROUND_CEILING) * rate if issuer_liability else Decimal(0)
    return {"commission": commission, "spread": spread, "slippage": slippage, "taxes": taxes,
            "total": commission + spread + slippage + taxes}


def costs_for_instrument(cfg: dict, *, isin: str, ticker: str, side: str, quantity: int,
                         reference_price: Decimal, settlement_date: date, executed: bool = True) -> dict:
    liability = resolve_liability(ROOT / cfg["ttf"]["eligibility_file"], isin=isin, ticker=ticker, settlement_date=settlement_date) if side == "BUY" and executed else None
    return execution_costs(cfg, side=side, quantity=quantity, reference_price=reference_price,
                           settlement_date=settlement_date, issuer_liability=liability, executed=executed)
