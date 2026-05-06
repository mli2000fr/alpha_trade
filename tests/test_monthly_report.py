"""Phase C / S16.1 — Tests rapport mensuel + signature HMAC."""
from __future__ import annotations

from datetime import date

from reporting import (
    MonthlyReportInputs,
    build_monthly_report,
    sign_report,
    verify_signature,
)
from reporting.monthly_report import CashEvent, FillRow
from reporting.json_schema import SCHEMA_VERSION
from reporting.pdf_renderer import render_text


SECRET = b"unit-test-secret"


def _sample() -> MonthlyReportInputs:
    return MonthlyReportInputs(
        account_id="ACC-1",
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        fills=[
            FillRow("f1", "AAPL", 100, 100.5, 100.0, fees=1.0),
            FillRow("f2", "MSFT", -50, 199.5, 200.0, fees=0.5),
        ],
        cash_events=[
            CashEvent("d1", "AAPL", "dividend", 25.0),
            CashEvent("w1", "AAPL", "withholding", -3.75),
            CashEvent("c1", "", "fee", -2.0),
        ],
        realized_pnl=1234.56,
        trades_count=2,
    )


def test_build_and_sign_report():
    rpt = build_monthly_report(_sample(), secret=SECRET)
    assert rpt.schema_version == SCHEMA_VERSION
    assert rpt.account_id == "ACC-1"
    assert rpt.fills_count == 2
    assert rpt.dividends == 25.0
    assert rpt.withholding_tax == -3.75
    assert rpt.fees == 1.0 + 0.5 - 2.0
    # slippage AAPL = +50 bps, MSFT = -25 bps → moyenne = 12.5
    assert rpt.average_slippage_bps == 12.5
    assert rpt.signature["algorithm"] == "HMAC-SHA256"
    assert verify_signature(rpt.to_dict(), SECRET)


def test_signature_detects_tampering():
    rpt = build_monthly_report(_sample(), secret=SECRET)
    d = rpt.to_dict()
    d["realized_pnl"] = 999_999.0
    assert verify_signature(d, SECRET) is False


def test_signature_rejects_wrong_secret():
    rpt = build_monthly_report(_sample(), secret=SECRET)
    assert verify_signature(rpt.to_dict(), b"other-secret") is False


def test_pdf_renderer_text_fallback(tmp_path):
    rpt = build_monthly_report(_sample(), secret=SECRET)
    text = render_text(rpt.to_dict())
    assert "Realized P&L" in text
    assert "ACC-1" in text


def test_sign_report_helper_alone():
    payload = {"a": 1, "b": "x"}
    sig = sign_report(payload, SECRET)
    assert sig["algorithm"] == "HMAC-SHA256"
    payload["signature"] = sig
    assert verify_signature(payload, SECRET)

