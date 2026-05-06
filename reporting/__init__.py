"""Phase C / S16.1 — Génération de rapport broker mensuel.

Modules :

* ``monthly_report`` — agrégation P&L réalisé / dividendes / frais /
  slippage + signature HMAC.
* ``json_schema`` — schéma versionné ``monthly_report.v1``.
* ``pdf_renderer`` — wrapper ``reportlab`` opt-in (fallback texte).
"""
from reporting.monthly_report import (  # noqa: F401
    MonthlyReport,
    MonthlyReportInputs,
    build_monthly_report,
    sign_report,
    verify_signature,
)

__all__ = [
    "MonthlyReport",
    "MonthlyReportInputs",
    "build_monthly_report",
    "sign_report",
    "verify_signature",
]

