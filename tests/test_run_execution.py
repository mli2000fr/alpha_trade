from typing import Any, cast

import run_execution


def test_run_bridges_executor_live_progress_to_run_summaries(monkeypatch) -> None:
    emitted_payloads: list[dict[str, object]] = []
    captured_progress_callbacks: list[object] = []

    class _FakeExecutor:
        def __init__(self, config, repo, broker, oco, circuit_breaker=None, progress_callback=None):
            captured_progress_callbacks.append(progress_callback)
            self._progress_callback = progress_callback

        def execute_run(self, risk_run_id=None, trade_date=None):
            if callable(self._progress_callback):
                self._progress_callback(
                    {
                        "progress_live": True,
                        "progress_current": 1,
                        "progress_total": 1,
                        "progress_phase": "finalize",
                        "progress_label": "⚙️ Progression execution — finalisation",
                    }
                )
            return {
                "exec_run_id": "exec-1",
                "risk_run_id": risk_run_id,
                "trade_date": trade_date.isoformat() if trade_date else None,
                "status": "COMPLETED",
                "targets": 0,
                "submitted": 0,
                "filled": 0,
                "failed": 0,
                "skipped": 0,
            }

    class _FakeRepo:
        pass

    class _FakeClient:
        def __init__(self, broker_mode=None, account_id=None):
            self.broker_mode = broker_mode
            self.account_id = account_id

    class _FakeBrokerAdapter:
        def __init__(self, client, config):
            self.client = client
            self.config = config

        def get_account_equity(self):
            return 100_000.0

    class _FakeOcoManager:
        def __init__(self, broker, repo):
            self.broker = broker
            self.repo = repo

    class _FakeCircuitBreaker:
        def __init__(self, config, pnl):
            self.config = config
            self.pnl = pnl

    monkeypatch.setattr(run_execution, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        run_execution,
        "emit_run_summary",
        lambda summary: emitted_payloads.append(cast(dict[str, object], dict(cast(dict[str, Any], summary)))),
    )
    monkeypatch.setattr(run_execution, "persist_run_business_summary", lambda **kwargs: None)

    import execution_engine.audit as execution_audit
    import execution_engine.broker_adapter as broker_adapter_module
    import execution_engine.db_io as execution_db_io
    import execution_engine.executor as executor_module
    import execution_engine.oco_manager as oco_manager_module
    import risk_management.circuit_breaker as circuit_breaker_module
    import service.alpaca.trading_client as trading_client_module

    monkeypatch.setattr(execution_audit, "build_execution_run_summary", lambda metrics, **kwargs: {"run_id": "exec-1", "status": metrics["status"], "trade_date": metrics.get("trade_date")})
    monkeypatch.setattr(broker_adapter_module, "BrokerAdapter", _FakeBrokerAdapter)
    monkeypatch.setattr(execution_db_io, "ExecutionRepository", _FakeRepo)
    monkeypatch.setattr(executor_module, "ProductionExecutor", _FakeExecutor)
    monkeypatch.setattr(oco_manager_module, "OcoManager", _FakeOcoManager)
    monkeypatch.setattr(trading_client_module, "AlpacaTradingClient", _FakeClient)
    monkeypatch.setattr(circuit_breaker_module, "CircuitBreaker", _FakeCircuitBreaker)

    run_execution.run("simulate", "risk-1", "2026-05-01", debug=False)

    assert captured_progress_callbacks
    assert any(payload.get("progress_live") for payload in emitted_payloads)
    assert any(payload.get("run_id") == "exec-1" for payload in emitted_payloads)


def test_run_execution_importable():
    assert hasattr(run_execution, "__doc__")


def test_run_propagates_regime_max_gross_exposure_to_execution_config(monkeypatch) -> None:
    captured_configs: list[object] = []

    class _FakeSnapshot:
        mode = "capital_preservation"
        risk_multiplier = 1.0
        effective_max_positions = 2
        enforced_min_notional = None
        allowed_slots = None
        max_position_weight = 0.20
        max_sector_weight = 0.25
        max_gross_exposure = 0.35
        allow_new_entries = True
        active_patterns = ()
        blocked_sectors = ()
        earnings_shielded_symbols = {}
        buyback_blackout_symbols = {}
        macro = {}
        reasons = ("capital_preservation_max_gross_exposure",)

        def to_dict(self):
            return {
                "trade_date": "2026-05-01",
                "mode": self.mode,
                "risk_multiplier": self.risk_multiplier,
                "effective_max_positions": self.effective_max_positions,
                "max_position_weight": self.max_position_weight,
                "max_sector_weight": self.max_sector_weight,
                "max_gross_exposure": self.max_gross_exposure,
                "allow_new_entries": self.allow_new_entries,
                "active_patterns": [],
                "blocked_sectors": [],
                "earnings_shielded_symbols": {},
                "buyback_blackout_symbols": {},
                "macro": {},
                "reasons": list(self.reasons),
            }

    class _FakeExecutor:
        def __init__(self, config, repo, broker, oco, circuit_breaker=None, progress_callback=None):
            captured_configs.append(config)
            self._progress_callback = progress_callback

        def execute_run(self, risk_run_id=None, trade_date=None):
            return {
                "exec_run_id": "exec-1",
                "risk_run_id": risk_run_id,
                "trade_date": trade_date.isoformat() if trade_date else None,
                "status": "COMPLETED",
                "targets": 0,
                "submitted": 0,
                "filled": 0,
                "failed": 0,
                "skipped": 0,
            }

    class _FakeRepo:
        pass

    class _FakeClient:
        def __init__(self, broker_mode=None, account_id=None):
            self.broker_mode = broker_mode
            self.account_id = account_id

    class _FakeBrokerAdapter:
        def __init__(self, client, config):
            self.client = client
            self.config = config

        def get_account_equity(self):
            return 100_000.0

    class _FakeOcoManager:
        def __init__(self, broker, repo):
            self.broker = broker
            self.repo = repo

    class _FakeCircuitBreaker:
        def __init__(self, config, pnl):
            self.config = config
            self.pnl = pnl

    monkeypatch.setattr(run_execution, "configure_root_logging", lambda **kwargs: None)
    monkeypatch.setattr(run_execution, "emit_run_summary", lambda summary: None)
    monkeypatch.setattr(run_execution, "persist_run_business_summary", lambda **kwargs: None)
    monkeypatch.setattr(run_execution, "_persist_market_macro_snapshot", lambda **kwargs: 0)

    import common.config_loader as config_loader_module
    import execution_engine.audit as execution_audit
    import execution_engine.broker_adapter as broker_adapter_module
    import execution_engine.db_io as execution_db_io
    import execution_engine.executor as executor_module
    import execution_engine.market_regime_preflight as market_regime_preflight_module
    import execution_engine.oco_manager as oco_manager_module
    import risk_management.circuit_breaker as circuit_breaker_module
    import service.alpaca.trading_client as trading_client_module
    import service.market as service_market_module

    monkeypatch.setattr(config_loader_module, "load_config", lambda: {"market_regimes": {"enabled": True}})
    monkeypatch.setattr(execution_audit, "build_execution_run_summary", lambda metrics, **kwargs: {"run_id": "exec-1", "status": metrics["status"], "trade_date": metrics.get("trade_date")})
    monkeypatch.setattr(broker_adapter_module, "BrokerAdapter", _FakeBrokerAdapter)
    monkeypatch.setattr(execution_db_io, "ExecutionRepository", _FakeRepo)
    monkeypatch.setattr(executor_module, "ProductionExecutor", _FakeExecutor)
    monkeypatch.setattr(oco_manager_module, "OcoManager", _FakeOcoManager)
    monkeypatch.setattr(trading_client_module, "AlpacaTradingClient", _FakeClient)
    monkeypatch.setattr(circuit_breaker_module, "CircuitBreaker", _FakeCircuitBreaker)
    monkeypatch.setattr(market_regime_preflight_module, "derive_entry_mode", lambda payload: "capital_preservation")
    monkeypatch.setattr(market_regime_preflight_module, "emit_preflight", lambda payload: "market preflight")
    monkeypatch.setattr(service_market_module, "parse_market_regimes", lambda raw: cast(Any, type("_Cfg", (), {"enabled": True, "sentinel": type("_Sentinel", (), {"preflight_summary": False})()})()))
    monkeypatch.setattr(service_market_module, "build_default_macro_provider", lambda raw: object())
    monkeypatch.setattr(service_market_module, "DbSentimentScoreProvider", lambda trade_date: object())
    monkeypatch.setattr(service_market_module, "build_snapshot", lambda *args, **kwargs: _FakeSnapshot())

    run_execution.run("simulate", "risk-1", "2026-05-01", debug=False)

    assert captured_configs
    assert any(getattr(config, "regime_max_gross_exposure", None) == 0.35 for config in captured_configs)
    assert getattr(captured_configs[-1], "regime_max_gross_exposure", None) == 0.35


def test_resolve_mode_from_broker_mode_prefers_simulate_when_dry_run() -> None:
    assert run_execution.resolve_mode_from_broker_mode(broker_mode="paper", dry_run=True) == "simulate"
    assert run_execution.resolve_mode_from_broker_mode(broker_mode="paper", dry_run=False) == "paper"
    assert run_execution.resolve_mode_from_broker_mode(broker_mode="live", dry_run=False) == "live"


def test_build_runtime_preset_accepts_executor_compat_overrides() -> None:
    preset = run_execution._build_runtime_preset(
        "paper",
        submission_window="pre_open",
        max_entry_gap_pct=0.03,
        trailing_activation_trigger="profit_pct",
        trailing_activation_profit_pct=0.04,
        protection_transition_timeout_seconds=12,
        fill_timeout_seconds=240,
        max_slippage_bps=15,
    )

    assert preset["submission_window"] == "pre_open"
    assert preset["max_entry_gap_pct"] == 0.03
    assert preset["trailing_activation_trigger"] == "profit_pct"
    assert preset["trailing_activation_profit_pct"] == 0.04
    assert preset["protection_transition_timeout_seconds"] == 12
    assert preset["fill_timeout_seconds"] == 240
    assert preset["max_slippage_bps"] == 15


def test_build_parser_defaults_to_overnight_cash_swing_inputs() -> None:
    parser = run_execution.build_parser()

    args = parser.parse_args(["paper"])

    assert args.account_type == "cash"
    assert args.swing_only is True
    assert args.submission_window is None
    assert args.profit_taker_pct is None
    assert args.trailing_stop_pct is None


def test_build_parser_accepts_custom_profit_taker_pct() -> None:
    parser = run_execution.build_parser()

    args = parser.parse_args(["paper", "--profit-taker-pct", "0.065"])

    assert args.profit_taker_pct == 0.065


def test_build_parser_accepts_custom_trailing_stop_pct() -> None:
    parser = run_execution.build_parser()

    args = parser.parse_args(["paper", "--trailing-stop-pct", "0.04"])

    assert args.trailing_stop_pct == 0.04


def test_build_parser_accepts_custom_max_entry_gap_pct() -> None:
    parser = run_execution.build_parser()

    args = parser.parse_args(["paper", "--max-entry-gap-pct", "0.03"])

    assert args.max_entry_gap_pct == 0.03


