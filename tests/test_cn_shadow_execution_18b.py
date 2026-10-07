"""Shadow CN : décision PIT, tentative ex post et aucune route broker."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from service.market.cn_execution_contract import (
    CNExecutionContractError, CostProfile, ExecutionRule, InventoryLot,
)
from service.market.cn_shadow_execution_18b import (
    ShadowBar, ShadowIntent, assess_shadow_attempt, mark_shadow_attempt,
    plan_shadow_intent, write_shadow_audit,
)

CN_TZ = ZoneInfo("Asia/Shanghai")
SIGNAL = datetime(2024, 3, 4, 16, 0, tzinfo=CN_TZ)
DAY = date(2024, 3, 5)


def _rule() -> ExecutionRule:
    return ExecutionRule(1, date(2020, 1, 1), date(2025, 12, 31),
                         "XSHG", "SH_MAIN", 100, 100, 1, Decimal("0.01"),
                         False, False, 1, True, "RESEARCH_V1")


def _profile() -> CostProfile:
    return CostProfile(2, "research", date(2020, 1, 1), date(2025, 12, 31),
                       "RESEARCH_PROXY", Decimal("1"), Decimal("1"), Decimal("5"),
                       Decimal("0"), Decimal("0"), Decimal("5"), Decimal("2"),
                       Decimal("2"), "test-research-profile")


def _intent(side="BUY", **changes) -> ShadowIntent:
    base = ShadowIntent("shadow-1", 123, "600000.SH", "CN_A", "XSHG", "SH_MAIN",
                        SIGNAL, DAY, side, Decimal("1010") if side == "BUY" else None,
                        None if side == "BUY" else 100, "fixed-research-signal")
    return replace(base, **changes)


def _plan(intent=None, **kwargs):
    return plan_shadow_intent(intent or _intent(), listing_date=date(2010, 1, 1),
                              delisting_date=None, **kwargs)


def _bar(**changes) -> ShadowBar:
    base = ShadowBar(DAY, 123, "CN_A", datetime(2024, 3, 5, 16, 0, tzinfo=CN_TZ),
                     Decimal("10"), Decimal("10.5"), Decimal("100000"),
                     "TRADE", "CN_MAIN_10PCT_V1", False, False, "baostock-daily")
    return replace(base, **changes)


def _assess(plan=None, bar=None, **changes):
    return assess_shadow_attempt(
        plan or _plan(), bar=bar if bar is not None else _bar(),
        rule=_rule(), profile=_profile(), cash_available_cny=Decimal("1010"),
        allow_research_rules=True, allow_research_proxy=True, **changes,
    )


def test_buy_shadow_uses_lot_fees_and_never_claims_real_fill(tmp_path) -> None:
    plan = _plan()
    attempt = _assess(plan)
    assert plan.state == "QUEUED"
    assert (attempt.state, attempt.shares, attempt.hypothetical_price_cny) == (
        "HYPOTHETICAL_FILL", 100, Decimal("10"))
    assert attempt.hypothetical_cost_cny > 0
    assert attempt.evidence == "DAILY_BAR_PROXY_NOT_OBSERVED_EXECUTION"
    assert attempt.observed_at > plan.intent.signal_at
    path = tmp_path / "proof.json"
    write_shadow_audit(path, plan=plan, attempt=attempt)
    proof = json.loads(path.read_text(encoding="utf-8"))
    assert proof["not_broker_execution"] is True
    assert proof["attempt"]["state"] == "HYPOTHETICAL_FILL"
    assert proof["attempt"]["observed_bar"]["instrument_id"] == 123
    with pytest.raises(FileExistsError):
        write_shadow_audit(path, plan=plan, attempt=attempt)
    with pytest.raises(CNExecutionContractError, match="incohérente"):
        write_shadow_audit(tmp_path / "tampered.json", plan=plan,
                           attempt=replace(attempt, observation_fingerprint="fake"))


def test_no_same_day_signal_and_no_foreign_market() -> None:
    with pytest.raises(CNExecutionContractError, match="postérieure"):
        _plan(_intent(execution_session=SIGNAL.date()))
    with pytest.raises(CNExecutionContractError, match="CN_A"):
        _plan(_intent(market_code="US_EQ"))
    with pytest.raises(CNExecutionContractError, match="fuseau"):
        _plan(_intent(signal_at=SIGNAL.replace(tzinfo=None)))


def test_pretrade_pit_does_not_use_future_suspension() -> None:
    future = datetime(2024, 3, 5, 10, 0, tzinfo=CN_TZ)
    known = datetime(2024, 3, 4, 15, 30, tzinfo=CN_TZ)
    assert _plan(known_trading_status="SUSPENDED", status_available_at=future).state == "QUEUED"
    rejected = _plan(known_trading_status="SUSPENDED", status_available_at=known)
    assert (rejected.state, rejected.reason) == ("REJECTED", "KNOWN_SUSPENSION")
    assert _assess(rejected).state == "REJECTED"


def test_delisting_date_requires_pit_provenance() -> None:
    with pytest.raises(CNExecutionContractError, match="Radiation future"):
        plan_shadow_intent(_intent(), listing_date=date(2010, 1, 1),
                           delisting_date=DAY)
    late = plan_shadow_intent(
        _intent(), listing_date=date(2010, 1, 1), delisting_date=DAY,
        delisting_available_at=datetime(2024, 3, 5, 9, 0, tzinfo=CN_TZ))
    assert late.state == "QUEUED"
    known = plan_shadow_intent(
        _intent(), listing_date=date(2010, 1, 1), delisting_date=date(2024, 3, 4),
        delisting_available_at=datetime(2024, 3, 4, 15, 0, tzinfo=CN_TZ))
    assert known.state == "REJECTED"


def test_observation_checks_are_ex_post_and_fail_closed() -> None:
    assert _assess(bar=_bar(trading_status="SUSPENDED")).state == "NOT_FILLED"
    assert _assess(bar=_bar(locked_up=True)).state == "UNVERIFIABLE"
    assert _assess(bar=_bar(factor_event_unresolved=True)).state == "UNVERIFIABLE"
    assert _assess(bar=_bar(volume_shares=None)).state == "UNVERIFIABLE"
    assert _assess(bar=_bar(open_cny=Decimal("10.001"))).state == "UNVERIFIABLE"
    assert _assess(bar=_bar(volume_shares=Decimal("1000"))).reason == "PARTICIPATION_CAP"
    with pytest.raises(CNExecutionContractError, match="avant la clôture"):
        _assess(bar=_bar(observed_at=datetime(2024, 3, 5, 14, 0, tzinfo=CN_TZ)))
    with pytest.raises(CNExecutionContractError, match="hors séance"):
        _assess(bar=_bar(instrument_id=999))
    with pytest.raises(CNExecutionContractError, match="hors séance"):
        _assess(bar=_bar(market_code="US_EQ"))
    with pytest.raises(CNExecutionContractError, match="provenance"):
        _assess(bar=_bar(source_ref=""))
    missing = assess_shadow_attempt(
        _plan(), bar=None, rule=_rule(), profile=_profile(),
        cash_available_cny=Decimal("1010"), allow_research_rules=True,
        allow_research_proxy=True)
    assert (missing.state, missing.reason) == ("NOT_FILLED", "NO_SESSION_BAR")


def test_t1_and_dated_rule_proxy_optins() -> None:
    plan = _plan(_intent(side="SELL"))
    today_lot = (InventoryLot(100, DAY),)
    assert _assess(plan, lots=today_lot).state == "DEFERRED_T1"
    old_lot = (InventoryLot(100, date(2024, 3, 4)),)
    assert _assess(plan, lots=old_lot).state == "HYPOTHETICAL_FILL"
    with pytest.raises(CNExecutionContractError, match="opt-in"):
        assess_shadow_attempt(plan, bar=_bar(), rule=_rule(), profile=_profile(), lots=old_lot)
    with pytest.raises(CNExecutionContractError, match="non valide"):
        assess_shadow_attempt(plan, bar=_bar(), rule=replace(_rule(), valid_to=date(2024, 3, 4)),
                              profile=_profile(), lots=old_lot,
                              allow_research_rules=True, allow_research_proxy=True)


def test_later_price_comparison_cannot_rewrite_attempt(tmp_path) -> None:
    buy = _assess()
    later = _bar(session_date=date(2024, 3, 6),
                 observed_at=datetime(2024, 3, 6, 16, 0, tzinfo=CN_TZ),
                 close_cny=Decimal("11"))
    mark = mark_shadow_attempt(buy, next_bar=later)
    assert mark.directional_move_pct == Decimal("0.1")
    write_shadow_audit(tmp_path / "marked.json", plan=_plan(), attempt=buy, mark=mark)
    with pytest.raises(CNExecutionContractError, match="altérée"):
        write_shadow_audit(tmp_path / "bad-mark.json", plan=_plan(), attempt=buy,
                           mark=replace(mark, directional_move_pct=Decimal("0.9")))
    sell = _assess(_plan(_intent(side="SELL")),
                   lots=(InventoryLot(100, date(2024, 3, 4)),))
    assert mark_shadow_attempt(sell, next_bar=later).directional_move_pct == Decimal("-0.1")
    with pytest.raises(CNExecutionContractError, match="ultérieure"):
        mark_shadow_attempt(buy, next_bar=_bar())
    with pytest.raises(CNExecutionContractError, match="Aucun prix"):
        mark_shadow_attempt(_assess(bar=_bar(locked_down=True)), next_bar=later)
