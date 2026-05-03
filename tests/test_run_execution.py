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
    monkeypatch.setattr(run_execution, "emit_run_summary", lambda summary: emitted_payloads.append(dict(summary)))
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


def test_build_parser_defaults_to_overnight_cash_swing_inputs() -> None:
    parser = run_execution.build_parser()

    args = parser.parse_args(["paper"])

    assert args.account_type == "cash"
    assert args.pdt_rule == "off"
    assert args.swing_only is True
    assert args.submission_window is None


