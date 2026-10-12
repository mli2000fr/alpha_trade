from dataclasses import asdict
from functools import partial
from pathlib import Path

import pandas as pd
import pytest

from backtesting.oracle_exit_policy import OracleBacktestExitPolicy, load_oracle_backtest_exit_policy
from common.config_loader import override_config_path
from scripts.research.us_concentrated_live_portfolio import run_portfolio
from scripts.research.us_oracle_barrier_exit_grid import GridLedger
from scripts.research.us_oracle_configured_replay import configured_case
from service.market import parse_market_regimes
from tests.test_us_concentrated_live_portfolio import fixture_data


def config_file(tmp_path, body):
    path = tmp_path/'config.yaml'
    path.write_text(body, encoding='utf-8')
    return path


def test_defaults_are_twenty_ten_not_training_labels(tmp_path):
    path = config_file(tmp_path, 'oracle_barrier:\n  take_profit_pct: 0.3\n  stop_loss_pct: 0.07\n')
    assert asdict(load_oracle_backtest_exit_policy(path)) == dict(take_profit_pct=.20, stop_loss_pct=.10)


def test_root_yaml_has_selected_defaults_and_keeps_training_and_paper_separate():
    from common.config_loader import load_config
    path = Path(__file__).resolve().parents[1]/'config.yaml'
    assert load_oracle_backtest_exit_policy(path) == OracleBacktestExitPolicy(.20, .10)
    config = load_config(path)
    assert config['oracle_barrier']['stop_loss_pct'] == .07
    assert config['llm_directional_filter']['protections']['stop_loss_pct'] == .07


def test_custom_values_and_environment_config_override(tmp_path):
    path = config_file(tmp_path, 'oracle_backtest:\n  take_profit_pct: 0.25\n  stop_loss_pct: 0.05\n')
    with override_config_path(path):
        assert load_oracle_backtest_exit_policy() == OracleBacktestExitPolicy(.25, .05)


@pytest.mark.parametrize('tp,sl', [(True,.1), (.2,False), (20,.1), (.2,10), (0,.1),
    (.2,-.1), (.2,float('nan')), (float('inf'),.1), ('.2',.1), (.2,None)])
def test_invalid_values_fail_closed(tp, sl):
    with pytest.raises(ValueError, match='oracle_backtest'):
        OracleBacktestExitPolicy(tp, sl)


@pytest.mark.parametrize('body', ['oracle_backtest: null\n', 'oracle_backtest: []\n',
    'oracle_backtest:\n  trailing_enabled: true\n', 'oracle_backtest:\n  stop_loss: 0.1\n'])
def test_malformed_section_or_ignored_parameter_rejected(tmp_path, body):
    with pytest.raises(ValueError, match='oracle_backtest'):
        load_oracle_backtest_exit_policy(config_file(tmp_path, body))


@pytest.mark.parametrize('tp,sl', [(.20,.10), (.25,.05)])
def test_configured_policy_reaches_actual_fill_protections_and_expiry(tmp_path, tp, sl):
    path = config_file(tmp_path, f'oracle_backtest:\n  take_profit_pct: {tp}\n  stop_loss_pct: {sl}\n')
    policy = load_oracle_backtest_exit_policy(path)
    frames, scores, macro, days = fixture_data()
    output = tmp_path/'replay'
    result = run_portfolio(frames=frames, scores=scores, sectors={'FIXTURE':'Technology'},
        macro=macro, market_config=parse_market_regimes({'enabled':False}), policy='ORACLE_TOP10',
        variant='CURRENT_NO_EXPIRY', output=output, decision_end_date=days[0], expiry_open_sessions=20,
        ledger_factory=partial(GridLedger, tp_pct=policy.take_profit_pct, sl_pct=policy.stop_loss_pct, events=()),
        protection_options=dict(take_profit_enabled=True, trailing_enabled=False))
    trade = pd.read_parquet(output/'trades.parquet').iloc[0]
    assert trade.replay_initial_stop_price == pytest.approx(trade.entry_price*(1-sl))
    assert trade.replay_take_profit_price == pytest.approx(trade.entry_price*(1+tp))
    assert trade.exit_reason == 'expiry_open'
    assert trade.exit_date == days[21]
    assert abs(result['cash_reconciliation_error']) < 1e-8


def test_selected_case_uses_policy_not_hardcoded_training_stops():
    case = configured_case(2026, 20, 'NEW_BARRIER_LONG', OracleBacktestExitPolicy(.25,.05))
    assert case == (2026,20,'NEW_BARRIER_LONG','CONFIGURED',.25,.05)


@pytest.mark.parametrize('year,count,arm', [(2024,10,'NEW_BARRIER_LONG'),
    (2026,True,'NEW_BARRIER_LONG'), (2026,15,'NEW_BARRIER_LONG'), (2026,10,'SHORT')])
def test_unsupported_case_rejected(year, count, arm):
    with pytest.raises(ValueError):
        configured_case(year,count,arm,OracleBacktestExitPolicy())


def replay_test_setup(tmp_path, monkeypatch):
    import json
    import scripts.research.us_oracle_configured_replay as replay
    from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
    from scripts.research.us_concentrated_historical_tapes import digest
    from common.config_loader import load_config
    # Only the archived input readers/worker are replaced. The configuration,
    # source hashes, output protocol and post-run trade audit remain real.
    inputs, source = tmp_path/'inputs', tmp_path/'source'
    inputs.mkdir()
    source.mkdir()
    risk = frozen_backtest_config('2025-01-01', '2026-10-07')
    market = parse_market_regimes(load_config().get('market_regimes'))
    (source/'protocol.json').write_text(json.dumps(dict(as_of='2026-10-07', portfolio=dict(
        risk=asdict(risk.risk_config), market=asdict(market))), default=str), encoding='utf-8')
    (inputs/'prepared.json').write_text('{"files":{}}', encoding='utf-8')
    (inputs/'input-protocol.json').write_text(json.dumps(dict(source=str(source),
        source_hashes={str(source/'protocol.json'): digest(source/'protocol.json')})), encoding='utf-8')
    monkeypatch.setattr(replay.grid, 'worker_init', lambda inputs: None)
    return replay, inputs


def test_runner_freezes_policy_and_audits_executed_prices(tmp_path, monkeypatch):
    import json
    replay, inputs = replay_test_setup(tmp_path, monkeypatch)
    config = config_file(tmp_path, Path('config.yaml').read_text(encoding='utf-8'))
    # Alternative YAML changes exits only; risk/market retain the input contract.
    body = config.read_text(encoding='utf-8')
    body = body.replace('  take_profit_pct: 0.20\n  stop_loss_pct: 0.10\n',
                        '  take_profit_pct: 0.25\n  stop_loss_pct: 0.05\n')
    config.write_text(body, encoding='utf-8')
    calendar = pd.bdate_range('2025-01-01', periods=23)
    monkeypatch.setattr(replay, 'nyse_sessions', lambda *args: calendar)

    def case_runner(case, output):
        assert case[-2:] == (.25,.05)
        destination = Path(output)/'case'
        destination.mkdir()
        pd.DataFrame([dict(side='buy', entry_price=100., replay_initial_stop_price=95.,
            replay_take_profit_price=125., entry_date=calendar[1], exit_date=calendar[21],
            exit_reason='expiry_open', exit_price=100.)]).to_parquet(destination/'trades.parquet')
        return dict(status='COMPLETED', output=str(destination), tp_pct=case[-2], sl_pct=case[-1])

    monkeypatch.setattr(replay.grid, 'run_case', case_runner)
    output = tmp_path/'output'
    result = replay.run(inputs,output,year=2025,config=config)
    protocol = json.loads((output/'protocol.json').read_text())
    assert result['trade_contract_audit']['trades'] == 1
    assert result['exit_policy'] == protocol['exit_policy'] == dict(take_profit_pct=.25,stop_loss_pct=.05)
    assert result['trailing'] is False
    assert protocol['broker_orders'] is False
    assert json.loads((output/'progress.json').read_text())['status'] == 'COMPLETED'
    with pytest.raises(FileExistsError):
        replay.run(inputs,output,year=2025,config=config)


def test_runner_failure_is_recorded_without_success(tmp_path, monkeypatch):
    import json
    replay, inputs = replay_test_setup(tmp_path, monkeypatch)
    monkeypatch.setattr(replay.grid, 'run_case', lambda *args: dict(status='FAILED', failures=['bad bar']))
    output = tmp_path/'output'
    with pytest.raises(RuntimeError, match='bad bar'):
        replay.run(inputs,output)
    assert json.loads((output/'progress.json').read_text())['status'] == 'FAILED'
    assert json.loads((output/'report.json').read_text())['status'] == 'FAILED'
