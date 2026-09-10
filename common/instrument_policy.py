"""Politique commune de classification des instruments non-actions.

Le projet cible les actions d'entreprises. Les produits collectifs et structurés
restent utiles comme benchmarks, mais ne doivent pas entrer dans l'univers
cross-sectionnel Oracle ni dans l'univers tradable publié.

La classification par nom est volontairement conservatrice : le seul mot
``trust`` n'est pas éliminatoire afin de ne pas rejeter les REIT. Elle complète
les métadonnées de type lorsqu'elles ne sont pas disponibles chez le provider.
"""
from __future__ import annotations

import re


COLLECTIVE_INSTRUMENT_NAME_PATTERNS: tuple[str, ...] = (
    "etf",
    "etn",
    "exchange traded fund",
    "exchange-traded fund",
    "exchange traded note",
    "exchange-traded note",
    "index fund",
    "bond fund",
    "mutual fund",
    "closed-end fund",
    "closed end fund",
    "ishares",
    "spdr",
    "vanguard",
    "proshares",
    "direxion",
    "wisdomtree",
    "global x",
    "first trust",
    "xtrackers",
    "schwab etf",
    "microsectors",
    "etracs",
)

_FUND_WORD = re.compile(r"\bfunds?\b", re.IGNORECASE)
_STRUCTURED_NOTE = re.compile(r"\b(notes?|securities)\s+due\b", re.IGNORECASE)
_LEVERAGED_OR_INVERSE = re.compile(
    r"\b(?:inverse|leveraged|ultra(?:pro)?|bear\s+[123]x|bull\s+[123]x|[+-]?[23]x)\b",
    re.IGNORECASE,
)
_PRODUCT_CONTEXT = re.compile(
    r"\b(?:etf|etn|fund|trust|proshares|direxion|flexshares|microsectors|etracs)\b",
    re.IGNORECASE,
)
_INVESCO_PRODUCT = re.compile(
    r"\binvesco\b.*\b(?:trust|qqq|currencyshares|db|municipal)\b",
    re.IGNORECASE,
)


def excluded_collective_instrument_reason(company_name: object) -> str | None:
    """Retourne un motif stable si ``company_name`` désigne un produit exclu.

    Les ADR, REIT, BDC et sociétés dont la forme juridique contient ``Trust``
    ne sont pas rejetés par ce seul terme.
    """
    normalized = " ".join(str(company_name or "").strip().lower().split())
    if not normalized:
        return None
    if "etf" in normalized or "etn" in normalized:
        return "excluded_etf_or_etn"
    if _STRUCTURED_NOTE.search(normalized):
        return "excluded_structured_note"
    if _LEVERAGED_OR_INVERSE.search(normalized) and _PRODUCT_CONTEXT.search(normalized):
        return "excluded_leveraged_or_inverse_product"
    if _FUND_WORD.search(normalized):
        return "excluded_fund"
    if _INVESCO_PRODUCT.search(normalized):
        return "excluded_collective_instrument"
    if any(pattern in normalized for pattern in COLLECTIVE_INSTRUMENT_NAME_PATTERNS):
        return "excluded_collective_instrument"
    return None


__all__ = [
    "COLLECTIVE_INSTRUMENT_NAME_PATTERNS",
    "excluded_collective_instrument_reason",
]
