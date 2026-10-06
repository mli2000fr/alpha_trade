from copy import deepcopy
from decimal import Decimal

import pytest
import yaml

from service.fr.execution_costs import load_cost_profile
from service.fr.portfolio_replay_12b import ReplayBlocked, replay
from service.fr.universe_contract_6a import ROOT


def fixture(tmp_path):
    days = ["2025-03-27", "2025-03-28", "2025-03-31", "2025-04-01", "2025-04-02"]
    tape = {"schema_version": 1, "market_code": "FR_EQ", "currency": "EUR",
            "canonical_writes_enabled": False, "serving_enabled": False,
            "sessions": days, "calendar_evidence": "synthetic_test_only", "horizon": 1,
            "max_positions": 1, "initial_equity": "1000",
            "instruments": {"A": {"isin": "FR_TEST_A", "ticker": "A.PA"}},
            "corporate_action_coverage": {"A": {"from": days[0], "to": days[-1], "verified": True, "evidence": "synthetic"}},
            "candidates": [{"session": days[0], "uid": "A", "rank": 1, "available_at": days[0] + "T07:00:00+00:00"}],
            "decision_at": {d: d + "T08:00:00+00:00" for d in days},
            "entry_at": {d: d + "T08:00:00+00:00" for d in days},
            "settlements": {d: {"date": days[min(i + 2, 4)], "evidence": "synthetic"} for i, d in enumerate(days)},
            "events": [], "bars": {d: {"A": {"open": "100", "close": "110", "tradable": True,
                                              "economic_verified": True, "evidence": "synthetic"}} for d in days}}
    path = tmp_path / "tax.yaml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "market_code": "FR_EQ", "unknown_policy": "block",
                                  "instruments": [{"isin": "FR_TEST_A", "ticker": "A.PA", "from": "2024-01-01", "to": "2025-12-31",
                                                   "liable": True, "evidence": "synthetic_test_only"}]}), encoding="utf-8")
    return tape, load_cost_profile(ROOT / "config/markets/fr_execution_research_v1.yaml"), path


def test_cash_costs_reconciliation_and_integer_size(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    result = replay(tape, cfg, tax)
    buys = [r for r in result["ledger"]["orders"] if r["side"] == "BUY"]
    assert buys[0]["quantity"] == 9  # ten shares cannot pay their fees
    assert buys[0]["taxes"] == Decimal("2.70216")  # settlement March31 .3%
    assert result["gross_pnl"] == 90
    assert result["net_pnl"] == 90 - sum(result["costs"].values())
    assert all(r["cash"] >= 0 and r["positions"] <= 1 for r in result["ledger"]["equity"])
    assert result["economic_go_allowed"] is False


def test_no_stacking_no_sale_cash_reuse_next_session_reentry(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    first = tape["candidates"][0]
    tape["candidates"] += [dict(first, session=tape["sessions"][1]), dict(first, session=tape["sessions"][2])]
    result = replay(tape, cfg, tax)
    buys = [r["session"] for r in result["ledger"]["orders"] if r["side"] == "BUY"]
    assert buys == [tape["sessions"][0], tape["sessions"][2]]
    assert result["trades"] == 2
    assert any(r.get("reason") == "ALREADY_HELD" for r in result["ledger"]["orders"])


def test_dividend_ex_date_exit_and_payment_after_sale(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    tape["events"] = [{"id": "d", "uid": "A", "session": tape["sessions"][1], "kind": "DIVIDEND",
                       "payment_session": tape["sessions"][3], "cash_per_share": "2", "currency": "EUR",
                       "verified": True, "evidence": "synthetic"}]
    result = replay(tape, cfg, tax)
    assert result["gross_pnl"] == 108
    assert result["ledger"]["equity"][1]["dividend_receivable"] == 18
    assert result["ledger"]["equity"][3]["dividend_receivable"] == 0
    tape["events"][0]["session"] = tape["sessions"][0]
    assert replay(tape, cfg, tax)["gross_pnl"] == 90


def test_split_preserves_value_and_blocks_fractional_entitlement(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    day = tape["sessions"][1]
    tape["bars"][day]["A"].update(open="50", close="55")
    tape["events"] = [{"id": "s", "uid": "A", "session": day, "kind": "SPLIT", "numerator": 2,
                       "denominator": 1, "verified": True, "evidence": "synthetic"}]
    result = replay(tape, cfg, tax)
    assert result["gross_pnl"] == 90
    assert result["ledger"]["orders"][1]["quantity"] == 18
    tape["events"][0].update(numerator=1, denominator=2)
    with pytest.raises(ReplayBlocked, match="rompus"):
        replay(tape, cfg, tax)


def test_unknown_tax_and_missing_exit_abort_not_future_filter(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    tax.write_text(yaml.safe_dump({"schema_version": 1, "market_code": "FR_EQ", "unknown_policy": "block", "instruments": []}))
    with pytest.raises(ReplayBlocked, match="TTF"):
        replay(tape, cfg, tax)
    tape, cfg, tax = fixture(tmp_path)
    del tape["bars"][tape["sessions"][1]]["A"]
    with pytest.raises(ReplayBlocked, match="Prix") as blocked:
        replay(tape, cfg, tax)
    assert blocked.value.ledger["orders"][0]["side"] == "BUY"


def test_verified_no_open_rejects_without_cash_fees_or_future_gates(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    first = tape["sessions"][0]
    tape["bars"][first]["A"].update(open=None, tradable=False,
        opening_execution={"status": "NO_OPENING_TRANSACTION", "evidence": "official_zero_volume_no_open"})
    tape["corporate_action_coverage"] = {}
    tape["settlements"] = {}
    tax.write_text(yaml.safe_dump({"schema_version": 1, "market_code": "FR_EQ", "unknown_policy": "block", "instruments": []}))
    result = replay(tape, cfg, tax)
    assert result["trades"] == 0
    assert result["final_equity"] == 1000
    assert sum(result["costs"].values()) == 0
    assert result["ledger"]["cash_movements"] == []
    assert result["ledger"]["orders"][0]["side"] == "REJECT"
    assert result["ledger"]["orders"][0]["rank"] == 1
    assert all(row["positions"] == 0 for row in result["ledger"]["equity"])


@pytest.mark.parametrize("case", ["no_evidence", "contradictory_open", "unknown_open"])
def test_no_open_unknown_or_contradictory_still_blocks(tmp_path, case):
    tape, cfg, tax = fixture(tmp_path)
    bar = tape["bars"][tape["sessions"][0]]["A"]
    bar["opening_execution"] = {"status": "NO_OPENING_TRANSACTION", "evidence": "official"}
    if case == "no_evidence":
        bar.update(open=None)
        bar["opening_execution"]["evidence"] = None
    elif case == "unknown_open":
        bar.update(open=None)
        del bar["opening_execution"]
    with pytest.raises(ReplayBlocked):
        replay(tape, cfg, tax)


def test_no_open_rejection_does_not_consume_capacity(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    tape["instruments"]["B"] = {"isin": "FR_TEST_B", "ticker": "B.PA"}
    tape["corporate_action_coverage"]["B"] = deepcopy(tape["corporate_action_coverage"]["A"])
    for bars in tape["bars"].values():
        bars["B"] = deepcopy(bars["A"])
    first = tape["sessions"][0]
    tape["bars"][first]["A"].update(open=None, tradable=False,
        opening_execution={"status": "NO_OPENING_TRANSACTION", "evidence": "official"})
    tape["candidates"].append(dict(tape["candidates"][0], uid="B", rank=2))
    eligibility = yaml.safe_load(tax.read_text())
    eligibility["instruments"].append(dict(eligibility["instruments"][0], isin="FR_TEST_B", ticker="B.PA"))
    tax.write_text(yaml.safe_dump(eligibility))
    result = replay(tape, cfg, tax)
    assert [(r["side"], r["uid"]) for r in result["ledger"]["orders"][:2]] == [("REJECT", "A"), ("BUY", "B")]


@pytest.mark.parametrize("change, message", [
    ("future", "réservée"), ("availability", "disponible"), ("coverage", "Couverture"),
    ("settlement", "Règlement"), ("complex", "complexe"), ("duplicate", "dupliqué"),
])
def test_fail_closed_contract(tmp_path, change, message):
    tape, cfg, tax = fixture(tmp_path)
    if change == "future":
        tape["sessions"].append("2026-01-02")
    elif change == "availability":
        tape["candidates"][0]["available_at"] = "2025-03-27T09:00:00+00:00"
    elif change == "coverage":
        tape["corporate_action_coverage"]["A"]["verified"] = False
    elif change == "settlement":
        tape["settlements"] = {}
    elif change == "duplicate":
        tape["candidates"] *= 2
    else:
        tape["events"] = [{"id": "x", "uid": "A", "session": tape["sessions"][1], "kind": "MERGER",
                           "verified": True, "evidence": "synthetic"}]
    with pytest.raises(ValueError, match=message):
        replay(tape, cfg, tax)


def test_stress_costs_without_mutating_input(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    saved = deepcopy(tape)
    basic = replay(tape, cfg, tax)
    stressed = replay(tape, cfg, tax, stress_multiplier=Decimal(2))
    assert stressed["costs"]["commission"] == basic["costs"]["commission"] * 2
    assert stressed["net_pnl"] < basic["net_pnl"]
    assert tape == saved


def test_decision_after_open_and_multiple_isin_aliases_rejected(tmp_path):
    tape, cfg, tax = fixture(tmp_path)
    tape["decision_at"][tape["sessions"][0]] = "2025-03-27T09:00:00+00:00"
    with pytest.raises(ValueError, match="disponible"):
        replay(tape, cfg, tax)
    tape, cfg, tax = fixture(tmp_path)
    tape["instruments"]["ALIAS"] = dict(tape["instruments"]["A"])
    with pytest.raises(ValueError, match="ISIN"):
        replay(tape, cfg, tax)
