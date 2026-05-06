"""Phase C / S16.1 — Renderer PDF (opt-in via reportlab).

Si ``reportlab`` n'est pas installé, on retourne le rapport au format
texte (suffisant pour CI ; le PDF est généré en prod opt-in).
"""
from __future__ import annotations

from pathlib import Path


def render_text(report_dict: dict) -> str:
    lines = [
        "==== Alpha Trade — Monthly Broker Report ====",
        f"Account     : {report_dict['account_id']}",
        f"Period      : {report_dict['period_start']} → {report_dict['period_end']}",
        "",
        f"Realized P&L         : {report_dict['realized_pnl']:>14.2f}",
        f"Dividends            : {report_dict['dividends']:>14.2f}",
        f"Withholding tax      : {report_dict['withholding_tax']:>14.2f}",
        f"Fees                 : {report_dict['fees']:>14.2f}",
        f"Avg slippage (bps)   : {report_dict['average_slippage_bps']:>14.4f}",
        f"Fills count          : {report_dict['fills_count']:>14d}",
        f"Trades count         : {report_dict['trades_count']:>14d}",
        "",
        f"Signature ({report_dict['signature']['algorithm']}):",
        f"  {report_dict['signature']['value']}",
    ]
    return "\n".join(lines)


def render_pdf(report_dict: dict, output: Path) -> Path:
    """Rend en PDF (reportlab) ; fallback ``.txt`` si reportlab absent."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        from reportlab.lib.pagesizes import letter  # type: ignore[import-not-found]
        from reportlab.pdfgen import canvas  # type: ignore[import-not-found]
    except ImportError:
        # Fallback texte (mêmes contenus, extension .txt à côté)
        txt_path = output.with_suffix(".txt")
        txt_path.write_text(render_text(report_dict), encoding="utf-8")
        return txt_path

    c = canvas.Canvas(str(output), pagesize=letter)
    text = c.beginText(72, 720)
    text.setFont("Helvetica", 10)
    for line in render_text(report_dict).splitlines():
        text.textLine(line)
    c.drawText(text)
    c.showPage()
    c.save()
    return output

