"""Sprint 12-B : scénarios synthétiques, aucune performance historique inférée."""

import json
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from modelFactory.cn_portfolio_replay import load_inputs
from service.market.cn_execution_contract import CNExecutionContractError
from service.market.cn_portfolio_replay import (
    CNAction,
    CNBar,
    CNInstrument,
    CNIntent,
    CNPortfolioReplay,
    ReplayConfig,
)

D1 = date(2024, 3, 4)
D2 = date(2024, 3, 5)
D3 = date(2024, 3, 6)
D4 = date(2024, 3, 7)
D5 = date(2024, 3, 8)


@pytest.fixture
def cn_conn():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE market_execution_rules (
                rule_id INTEGER PRIMARY KEY,market_code TEXT,exchange_mic TEXT,board_code TEXT,
                valid_from DATE,valid_to DATE,currency TEXT,settlement_cycle_days INTEGER,
                buy_lot_size INTEGER,sell_lot_size INTEGER,tick_size TEXT,
                daily_price_limit_pct TEXT,short_selling_allowed INTEGER,
                same_day_sell_allowed INTEGER,metadata_json TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE cn_execution_cost_profiles (
                profile_id INTEGER PRIMARY KEY,market_code TEXT,profile_key TEXT,
                valid_from DATE,valid_to DATE,currency TEXT,source_type TEXT,
                commission_bps_buy TEXT,commission_bps_sell TEXT,commission_min_cny TEXT,
                transfer_fee_bps_buy TEXT,transfer_fee_bps_sell TEXT,
                stamp_duty_bps_sell TEXT,slippage_bps_buy TEXT,slippage_bps_sell TEXT,
                source_ref TEXT
            )
        """))
        for number, mic, board, increment, minimum in (
            (1, "XSHG", "SH_MAIN", 100, 100),
            (2, "XSHE", "SZ_MAIN", 100, 100),
            (3, "XSHG", "STAR", 1, 200),
        ):
            conn.execute(text("""
                INSERT INTO market_execution_rules VALUES (
                  :id,'CN_A',:mic,:board,'2018-01-01','2025-12-31','CNY',
                  1,:increment,1,'0.01',NULL,0,0,:metadata
                )
            """), {"id": number, "mic": mic, "board": board,
                   "increment": increment,
                   "metadata": json.dumps({"minimum_buy_shares": minimum,
                                           "minimum_sell_shares": minimum,
                                           "research_only": True, "rule_version": "test_v1"})})
        conn.execute(text("""
            INSERT INTO cn_execution_cost_profiles VALUES (
              1,'CN_A','cn_a_research','2018-01-01','2025-12-31','CNY',
              'RESEARCH_PROXY','10','10','5','0','0','0','0','0','test_only'
            )
        """))
    with engine.connect() as conn:
        yield conn
    engine.dispose()


def _instrument(instrument_id=1, *, board="SH_MAIN", delist=None):
    return CNInstrument(instrument_id, "XSHE" if board == "SZ_MAIN" else "XSHG",
                        board, date(2020, 1, 1), delist)


def _bar(day, instrument_id=1, *, opening="10", closing="10", volume="100000",
         status="TRADE", policy="CN_MAIN_10PCT_V1", locked_up=False, locked_down=False,
         factor=False):
    return CNBar(day, instrument_id, Decimal(opening) if opening else None,
                 Decimal(closing) if closing else None, status, policy, locked_up, locked_down,
                 Decimal(volume) if volume else None, factor)


def _config(**kwargs):
    return ReplayConfig(initial_cash_cny=Decimal("10000"), allow_research_rules=True,
                        allow_research_proxy=True, **kwargs)


def _run(conn, *, days=None, instruments=None, bars=None, intents=None, actions=None, config=None):
    return CNPortfolioReplay(conn, config or _config()).run(
        sessions=days or [D1, D2, D3, D4], instruments=instruments or [_instrument()],
        bars=bars if bars is not None else [_bar(day) for day in [D1, D2, D3, D4]],
        intents=intents or [], actions=actions,
    )


def _events(result, kind):
    return [event for event in result.journal if event["event"] == kind]


def test_no_same_day_fill_and_cash_fees_inventory_t1(cn_conn):
    result = _run(cn_conn, intents=[
        CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005")),
        CNIntent("stop", D2, 1, "SELL"),
    ])
    fills = _events(result, "HYPOTHETICAL_FILL")
    assert [(row["session_date"], row["side"], row["shares"]) for row in fills] == [
        (D2.isoformat(), "BUY", 100), (D3.isoformat(), "SELL", 100),
    ]
    assert result.cash_cny == Decimal("9990")
    assert Decimal(result.daily[1]["cash_spendable_cny"]) == 8995
    assert Decimal(result.daily[2]["cash_withdrawable_cny"]) == 8995
    assert Decimal(result.daily[3]["cash_withdrawable_cny"]) == 9990
    assert result.lots == {}
    assert result.economic_result_valid


def test_stop_on_buy_day_is_queued_and_never_filled_on_same_day(cn_conn):
    # Les deux signaux sont produits après la clôture D1 : à D2 l'ordre
    # vendeur est traité avant l'achat et doit être rejeté sans inventaire.
    result = _run(cn_conn, intents=[
        CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005")),
        CNIntent("stop", D1, 1, "SELL"),
    ])
    assert any(row["intent_id"] == "stop" and row["reason"] == "INVALID_SELL_QUANTITY_OR_INVENTORY"
               for row in _events(result, "ORDER_REJECTED"))
    assert all(row["intent_id"] != "stop" for row in _events(result, "HYPOTHETICAL_FILL"))


def test_locked_limit_and_suspension_carry_then_expire(cn_conn):
    bars = [_bar(D1), _bar(D2, locked_down=True), _bar(D3, status="SUSPENDED"), _bar(D4)]
    result = _run(cn_conn, bars=bars, intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005"))],
                  config=_config(max_wait_sessions=2))
    assert not _events(result, "HYPOTHETICAL_FILL")
    assert [row["reason"] for row in _events(result, "ORDER_NOT_FILLED")] == [
        "LOCKED_LIMIT_SIDE_DEPENDENT", "SUSPENDED_SESSION",
    ]
    assert _events(result, "ORDER_CANCELLED")[0]["reason"] == "MAX_WAIT_SESSIONS"


def test_scenario_participation_and_star_minimum(cn_conn):
    star = _instrument(3, board="STAR")
    bars = [_bar(day, 3, volume="5000", policy="CN_STAR_20PCT_V1") for day in [D1, D2, D3, D4]]
    intent = CNIntent("buy", D1, 3, "BUY", budget_cny=Decimal("2005"))
    base = _run(cn_conn, instruments=[star], bars=bars, intents=[intent],
                config=_config(scenario="base", max_wait_sessions=1))
    conservative = _run(cn_conn, instruments=[star], bars=bars, intents=[intent],
                        config=_config(scenario="conservative", max_wait_sessions=1))
    assert _events(base, "HYPOTHETICAL_FILL")[0]["shares"] == 200
    assert _events(conservative, "ORDER_NOT_FILLED")[0]["reason"] == "PARTICIPATION_CAP"


def test_unknown_factor_event_and_delisting_not_silent(cn_conn):
    result = _run(cn_conn, days=[D1, D2, D3, D4],
                  instruments=[_instrument(delist=D3)],
                  bars=[_bar(D1), _bar(D2), _bar(D3, factor=True)],
                  intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005"))])
    assert result.unresolved[1] == "DELISTING_WITHOUT_VERIFIED_CASH_RECOVERY"
    assert result.lots[1][0].shares == 100
    assert not result.economic_result_valid
    assert result.daily[-1]["stale_marks"] == [1]


def test_split_and_dividend_are_accounted_if_explicitly_verified(cn_conn):
    actions = [
        CNAction("split", 1, D3, "SPLIT", share_multiplier=Decimal("2")),
        CNAction("dividend", 1, D3, "CASH_DIVIDEND",
                 cash_per_share_cny=Decimal("0.5"), payment_date=D4),
    ]
    result = _run(cn_conn, bars=[_bar(D1), _bar(D2), _bar(D3, closing="5"), _bar(D4, closing="5")],
                  intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005"))], actions=actions)
    assert result.lots[1][0].shares == 200
    assert result.cash_cny == Decimal("9045")
    assert _events(result, "SPLIT_APPLIED") and _events(result, "DIVIDEND_PAID")
    assert result.economic_result_valid


def test_no_research_opt_in_and_2026_gap_fail_closed(cn_conn):
    with pytest.raises(CNExecutionContractError, match="opt-in"):
        _run(cn_conn, config=ReplayConfig(initial_cash_cny=Decimal("10000")))
    future = [date(2026, 1, 5), date(2026, 1, 6)]
    with pytest.raises(CNExecutionContractError, match="trouvé=0"):
        _run(cn_conn, days=future, bars=[_bar(day) for day in future], config=_config())


def test_missing_bar_keeps_position_and_marks_stale(cn_conn):
    result = _run(cn_conn, bars=[_bar(D1), _bar(D2), _bar(D4)],
                  intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005"))])
    assert result.daily[2]["stale_marks"] == [1]
    assert not result.economic_result_valid
    assert result.lots[1][0].shares == 100


def test_unsettled_sale_cash_can_be_reinvested_without_withdrawal(cn_conn):
    instruments = [_instrument(1), _instrument(2, board="SZ_MAIN")]
    bars = [_bar(day, instrument_id) for day in [D1, D2, D3, D4] for instrument_id in (1, 2)]
    result = _run(cn_conn, instruments=instruments, bars=bars, intents=[
        CNIntent("buy1", D1, 1, "BUY", budget_cny=Decimal("9005")),
        CNIntent("sell1", D2, 1, "SELL"),
        CNIntent("buy2", D2, 2, "BUY", budget_cny=Decimal("9000")),
    ])
    d3fills = [row for row in _events(result, "HYPOTHETICAL_FILL") if row["session_date"] == D3.isoformat()]
    assert [row["side"] for row in d3fills] == ["SELL", "BUY"]
    assert Decimal(result.daily[2]["cash_withdrawable_cny"]) >= 0
    assert Decimal(result.daily[2]["cash_spendable_cny"]) >= Decimal(result.daily[2]["cash_withdrawable_cny"])


def test_intent_file_requires_cn_and_after_close(tmp_path):
    source = tmp_path / "signals.json"
    source.write_text(json.dumps({
        "market_code": "CN_A", "signal_timing": "after_close",
        "start_date": "2024-03-04", "end_date": "2024-03-07",
        "signals": [{"intent_id": "a", "signal_date": "2024-03-04",
                     "instrument_id": 3, "side": "BUY", "budget_cny": "1005"}],
    }), encoding="utf-8")
    raw, signals = load_inputs(source)
    assert raw["market_code"] == "CN_A"
    assert signals[0].budget_cny == Decimal("1005")
    source.write_text(source.read_text(encoding="utf-8").replace('"CN_A"', '"US"'), encoding="utf-8")
    with pytest.raises(ValueError, match="CN_A"):
        load_inputs(source)
    source.write_text(json.dumps({
        "market_code": "CN_A", "signal_timing": "after_close",
        "start_date": "2024-03-04", "end_date": "2024-03-07",
        "signals": [{"intent_id": "a", "signal_date": "2024-03-04",
                     "instrument_id": 3, "side": "BUY", "budget_cny": "1005",
                     "future_return": 0.3}],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="labels futurs"):
        load_inputs(source)


def test_priority_and_no_pyramiding_are_deterministic(cn_conn):
    instruments = [_instrument(1), _instrument(2, board="SZ_MAIN")]
    bars = [_bar(day, instrument_id) for day in [D1, D2, D3, D4] for instrument_id in (1, 2)]
    result = _run(cn_conn, instruments=instruments, bars=bars, config=_config(max_positions=1),
                  intents=[
                      CNIntent("low", D1, 1, "BUY", budget_cny=Decimal("1005"), priority=Decimal("0.1")),
                      CNIntent("high", D1, 2, "BUY", budget_cny=Decimal("1005"), priority=Decimal("0.9")),
                      CNIntent("again", D2, 2, "BUY", budget_cny=Decimal("1005")),
                  ])
    assert _events(result, "HYPOTHETICAL_FILL")[0]["intent_id"] == "high"
    assert any(row["intent_id"] == "again" and row["reason"] == "PYRAMIDING_DISABLED"
               for row in _events(result, "ORDER_REJECTED"))


def test_replay_is_reproducible_and_one_shot(cn_conn):
    inputs = [CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005"))]
    first = _run(cn_conn, intents=inputs)
    second = _run(cn_conn, intents=inputs)
    assert first.journal == second.journal
    assert first.daily == second.daily
    runner = CNPortfolioReplay(cn_conn, _config())
    runner.run(sessions=[D1, D2], instruments=[_instrument()],
               bars=[_bar(D1), _bar(D2)], intents=inputs)
    with pytest.raises(RuntimeError, match="une fois"):
        runner.run(sessions=[D1, D2], instruments=[_instrument()],
                   bars=[_bar(D1), _bar(D2)], intents=inputs)


def test_position_bought_before_suspension_is_not_sold_there(cn_conn):
    result = _run(cn_conn,
                  bars=[_bar(D1), _bar(D2), _bar(D3, opening="0", closing="0",
                                                    status="SUSPENDED"), _bar(D4)],
                  intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005")),
                           CNIntent("exit", D2, 1, "SELL")])
    assert [(row["session_date"], row["side"]) for row in _events(result, "HYPOTHETICAL_FILL")] == [
        (D2.isoformat(), "BUY"), (D4.isoformat(), "SELL"),
    ]
    assert result.daily[2]["stale_marks"] == [1]
    assert not result.economic_result_valid


def test_multiple_limit_down_sessions_defer_exit(cn_conn):
    days = [D1, D2, D3, D4, D5]
    bars = [_bar(day, locked_down=day in {D3, D4}) for day in days]
    result = _run(cn_conn, days=days, bars=bars, config=_config(max_wait_sessions=3),
                  intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005")),
                           CNIntent("exit", D2, 1, "SELL")])
    assert [row["session_date"] for row in _events(result, "ORDER_NOT_FILLED")
            if row["intent_id"] == "exit"] == [D3.isoformat(), D4.isoformat()]
    assert _events(result, "HYPOTHETICAL_FILL")[-1]["session_date"] == D5.isoformat()


def test_ipo_limit_unknown_never_fills_and_full_odd_residual_can_sell(cn_conn):
    ipo = _run(cn_conn, bars=[_bar(D1), _bar(D2, policy="IPO_FIRST_5_OBS_NO_LIMIT_CONSERVATIVE"),
                              _bar(D3), _bar(D4)],
               intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005"))],
               config=_config(pending_policy="cancel_day"))
    assert not _events(ipo, "HYPOTHETICAL_FILL")
    assert _events(ipo, "ORDER_NOT_FILLED")[0]["reason"] == "LIMIT_POLICY_NOT_VERIFIED"
    odd = _run(cn_conn,
               bars=[_bar(D1), _bar(D2), _bar(D3, opening="20", closing="20"),
                     _bar(D4, opening="20", closing="20")],
               intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005")),
                        CNIntent("exit", D2, 1, "SELL")],
               actions=[CNAction("reverse_split", 1, D3, "SPLIT", share_multiplier=Decimal("0.5"))])
    assert _events(odd, "HYPOTHETICAL_FILL")[-1]["shares"] == 50
    assert odd.lots == {}


def test_price_off_tick_is_not_hypothetically_filled(cn_conn):
    result = _run(cn_conn, bars=[_bar(D1), _bar(D2, opening="10.005"), _bar(D3), _bar(D4)],
                  intents=[CNIntent("buy", D1, 1, "BUY", budget_cny=Decimal("1005"))],
                  config=_config(pending_policy="cancel_day"))
    assert not _events(result, "HYPOTHETICAL_FILL")
    assert _events(result, "ORDER_NOT_FILLED")[0]["reason"] == "OPEN_PRICE_OFF_TICK"
