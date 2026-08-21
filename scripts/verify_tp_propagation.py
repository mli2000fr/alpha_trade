"""Smoke test : vérifie que take_profit_price est propagé PortfolioEntry -> ExecutionTarget
après le correctif (execution_bridge.py + execution_replay.py)."""
from __future__ import annotations

import sys
from datetime import date

sys.path.insert(0, r"F:\projets")

from backtesting.execution_bridge import portfolio_entries_to_execution_targets
from backtesting.execution_replay import _entry_to_target
from risk_management.models import PortfolioEntry


def make_entry() -> PortfolioEntry:
    return PortfolioEntry(
        symbol="TEST",
        sector="Tech",
        entry_price=100.0,
        score_used=0.9,
        score_source="ml",
        atr_20=2.0,
        proposed_shares=10,
        approved_shares=10,
        target_notional=1000.0,
        target_weight=0.1,
        decision="ACCEPTED",
        decision_reason="OK",
        selection_rank=1,
        stop_price_initial=95.0,
        take_profit_price=107.0,  # ATR TP (min(3*ATR, 7%)) serait ~107
        risk_per_share=5.0,
        side="buy",
        selector_signal_mode="ml_first",
    )


def main() -> None:
    entry = make_entry()

    targets = portfolio_entries_to_execution_targets(
        [entry], risk_run_id="bt_test", trade_date=date(2025, 1, 3)
    )
    t1 = targets[0]
    print(f"[execution_bridge] take_profit_price : {t1.take_profit_price} "
          f"(attendu 107.0) -> {'OK' if t1.take_profit_price == 107.0 else 'ECHEC'}")

    t2 = _entry_to_target(entry, risk_run_id="bt_test",
                          execution_date=__import__("pandas").Timestamp("2025-01-03"),
                          entry_price=100.0)
    print(f"[execution_replay ] take_profit_price : {t2.take_profit_price} "
          f"(attendu 107.0) -> {'OK' if t2.take_profit_price == 107.0 else 'ECHEC'}")


if __name__ == "__main__":
    main()
