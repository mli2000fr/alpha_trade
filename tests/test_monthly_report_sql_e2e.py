"""Sprint S21.4 — E2E ``broker_statements`` → ``MonthlyReport`` sur 3 mois.

Vérifie : continuité des périodes, signature HMAC valide, comptes cohérents.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from reporting.monthly_report import build_monthly_report, verify_signature
from service.alpaca.statements import load_monthly_inputs_from_db

SECRET = b"unit-test-secret-32bytes-or-more!"


def _bootstrap(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE broker_statements (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id      VARCHAR(64) NOT NULL,
                activity_id     VARCHAR(128) NOT NULL,
                activity_type   VARCHAR(32) NOT NULL,
                symbol          VARCHAR(32),
                side            VARCHAR(16),
                qty             NUMERIC(20, 8),
                price           NUMERIC(20, 8),
                transaction_time DATETIME,
                raw_json        TEXT NOT NULL DEFAULT '',
                ingested_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (account_id, activity_id)
            )
            """
        ))


def _seed_3_months(engine, account: str = "ACC1") -> None:
    """Janvier : 1 BUY 10@100, 1 SELL 5@110, 1 DIV 0.5x10=5
    Février : 1 BUY 5@120, 1 FEE -1
    Mars    : 1 SELL 10@130, 1 WHTAX -2"""
    rows = [
        # Jan
        (account, "j1", "FILL", "AAPL", "buy",  10, 100, datetime(2026, 1, 5,  10, 0)),
        (account, "j2", "FILL", "AAPL", "sell",  5, 110, datetime(2026, 1, 20, 10, 0)),
        (account, "j3", "DIV",  "AAPL", None,    1,   5, datetime(2026, 1, 28, 16, 0)),
        # Fév
        (account, "f1", "FILL", "AAPL", "buy",   5, 120, datetime(2026, 2, 10, 10, 0)),
        (account, "f2", "FEE",  None,   None,    1,   1, datetime(2026, 2, 28,  0, 0)),
        # Mars
        (account, "m1", "FILL", "AAPL", "sell", 10, 130, datetime(2026, 3, 15, 10, 0)),
        (account, "m2", "WHTAX","AAPL", None,    1,   2, datetime(2026, 3, 28, 16, 0)),
    ]
    with engine.begin() as conn:
        for r in rows:
            conn.execute(text(
                "INSERT INTO broker_statements (account_id, activity_id, activity_type, "
                "symbol, side, qty, price, transaction_time, raw_json) "
                "VALUES (:a, :i, :t, :s, :sd, :q, :p, :tm, '{}')"
            ), dict(zip(["a", "i", "t", "s", "sd", "q", "p", "tm"], r)))


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    _bootstrap(eng)
    _seed_3_months(eng)
    return eng


def test_monthly_report_3_months_continuous(engine):
    months = [
        (date(2026, 1, 1), date(2026, 2, 1)),  # period_end exclusif côté loader
        (date(2026, 2, 1), date(2026, 3, 1)),
        (date(2026, 3, 1), date(2026, 4, 1)),
    ]
    reports = []
    for start, end in months:
        inputs = load_monthly_inputs_from_db(
            engine, account_id="ACC1", period_start=start, period_end=end,
        )
        report = build_monthly_report(inputs, secret=SECRET)
        reports.append(report)

    # Continuité : period_end[i] == period_start[i+1]
    for i in range(len(reports) - 1):
        assert reports[i].period_end == reports[i + 1].period_start

    # Signatures valides
    for r in reports:
        assert verify_signature(r.to_dict(), SECRET) is True

    # Comptages
    assert reports[0].fills_count == 2  # j1, j2
    assert reports[0].trades_count == 2
    assert reports[1].fills_count == 1  # f1
    assert reports[2].fills_count == 1  # m1

    # PnL réalisé janvier : sell 5@110 sur lot 10@100 → +50
    assert reports[0].realized_pnl == pytest.approx(50.0)
    # Mars : sell 10@130 sur lots restants (5@100 + 5@120) → 5*(130-100)+5*(130-120)=200
    assert reports[2].realized_pnl == pytest.approx(200.0)

    # Dividendes / fees / withholding
    assert reports[0].dividends == pytest.approx(5.0)
    assert reports[1].fees == pytest.approx(1.0)
    assert reports[2].withholding_tax == pytest.approx(2.0)


def test_signature_tamper_detection(engine):
    inputs = load_monthly_inputs_from_db(
        engine, account_id="ACC1",
        period_start=date(2026, 1, 1), period_end=date(2026, 2, 1),
    )
    report = build_monthly_report(inputs, secret=SECRET)
    d = report.to_dict()
    assert verify_signature(d, SECRET) is True
    d["realized_pnl"] = 999.99
    assert verify_signature(d, SECRET) is False

