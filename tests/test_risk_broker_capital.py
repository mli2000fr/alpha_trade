from datetime import datetime,date,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from risk_management import cli,broker_account
from risk_management.models import AccountRiskSnapshot
from risk_management.operational_data import OperationalDataUnavailable,validate_current_broker_snapshot

NOW=datetime(2026,10,28,0,30,tzinfo=timezone.utc)


def broker(**changes):
    data=dict(equity='1974.30',cash='1500',buying_power='0',last_equity='2000',
              trading_blocked=False,account_blocked=False)
    data.update(changes)
    return SimpleNamespace(get_account=Mock(return_value=data),get_positions=Mock(return_value=[]),
        list_orders=Mock(return_value=[]),submit_order=Mock())


def capture(client=None,mode='paper',account='default'):
    return broker_account.capture_current_account(account,mode,client=client or broker(),clock=lambda:NOW)


def test_real_capital_and_zero_buying_power_are_never_replaced():
    data,raw=capture()
    result=broker_account.risk_snapshot(data,raw)
    assert result.equity==1974.30 and result.cash==1500 and result.buying_power==0
    assert result.source=='broker:paper:risk' and result.captured_at==NOW
    assert result.daily_total_pnl==pytest.approx(-25.70)
    assert result.trade_date==date(2026,10,27)  # Actual NY date, no backdated timestamp.


@pytest.mark.parametrize('equity',['0','-1','NaN','Infinity',None,'bad'])
def test_invalid_equity_blocks_without_fallback(equity):
    with pytest.raises(OperationalDataUnavailable,match='aucun fallback'):
        capture(broker(equity=equity))


@pytest.mark.parametrize('field',['trading_blocked','account_blocked'])
def test_blocked_account_is_rejected(field):
    with pytest.raises(OperationalDataUnavailable):capture(broker(**{field:True}))


def test_api_failure_and_truncated_order_list_block():
    client=broker();client.get_account.side_effect=RuntimeError('offline')
    with pytest.raises(OperationalDataUnavailable):capture(client)
    client=broker();client.list_orders.return_value=[{}]*500
    with pytest.raises(OperationalDataUnavailable):capture(client)
    client.submit_order.assert_not_called()


def test_positions_and_pending_orders_remain_in_snapshot():
    client=broker()
    client.get_positions.return_value=[dict(symbol='ABC',side='long',qty='3',avg_entry_price='10',current_price='11')]
    client.list_orders.return_value=[dict(id='pending',symbol='XYZ',side='buy',qty='2',filled_qty='0',status='new')]
    data,_=capture(client)
    assert data.positions[0].symbol=='ABC' and data.open_orders[0].symbol=='XYZ'
    client.submit_order.assert_not_called()


def test_peak_history_is_retained_but_never_supplies_current_equity():
    data,raw=capture()
    previous=AccountRiskSnapshot('default',date(2026,10,26),0,4000,8000,5000)
    current=broker_account.risk_snapshot(data,raw,previous)
    assert current.equity==1974.30 and current.high_watermark==5000


def test_selected_account_and_broker_mode_are_explicit(monkeypatch):
    from service.alpaca import accounts,trading_client
    client=broker();factory=Mock(return_value=client)
    session=Mock()
    monkeypatch.setattr('common.public_data_http.verified_session',lambda:session)
    monkeypatch.setattr(accounts.AccountRegistry,'get',lambda:SimpleNamespace(resolve=lambda account:SimpleNamespace(mode='paper')))
    monkeypatch.setattr(trading_client,'AlpacaTradingClient',factory)
    data,_=broker_account.capture_current_account('test1','paper',clock=lambda:NOW)
    factory.assert_called_once_with(broker_mode='paper',account_id='test1',session=session)
    assert data.account.account_id=='test1'
    with pytest.raises(OperationalDataUnavailable,match='Mode'):
        broker_account.capture_current_account('test1','live')


def test_current_account_overnight_freshness_is_checked():
    data,_=capture()
    calendar=SimpleNamespace(session_dates=lambda a,b:[date(2026,10,27)],next_session=lambda d:date(2026,10,28),
        session_bounds=lambda d:(datetime(2026,10,28,13,30,tzinfo=timezone.utc),
                                 datetime(2026,10,27,20,tzinfo=timezone.utc)))
    validate_current_broker_snapshot(data,date(2026,10,27),now=NOW,calendar=calendar)
    with pytest.raises(ValueError,match='périmé'):
        validate_current_broker_snapshot(data,date(2026,10,27),now=NOW+timedelta(minutes=6),calendar=calendar)


@pytest.mark.parametrize('mode',['paper','live'])
def test_cli_passes_broker_equity_to_config_even_when_cli_requests_100000(monkeypatch,mode):
    from risk_management import config
    data,raw=capture(mode=mode)
    monkeypatch.setattr(broker_account,'capture_current_account',lambda account,run_mode:(data,raw))
    monkeypatch.setattr(cli,'configure_root_logging',lambda **kw:None)
    class Repo:
        def load_account_risk_snapshot(self,account,day):
            assert account=='default'
            return None
        def load_account_equity_breakdown(self,*a):pytest.fail('No cached fallback in PAPER/LIVE')
    monkeypatch.setattr(cli,'RiskRepository',Repo)
    class ConfigReached(Exception):pass
    def load(equity,cli_overrides,**kw):
        assert equity==1974.30 and cli_overrides['account_equity']==1974.30
        raise ConfigReached()
    monkeypatch.setattr(config,'load_risk_config',load)
    with pytest.raises(ConfigReached):
        cli.main(['--run-mode',mode,'--trade-date','2026-10-27','--account','default','--account-equity','100000','--dry-run'])


def test_cli_blocks_before_any_target_if_broker_unavailable(monkeypatch):
    monkeypatch.setattr(cli,'configure_root_logging',lambda **kw:None)
    monkeypatch.setattr(broker_account,'capture_current_account',lambda *a:(_ for _ in ()).throw(
        OperationalDataUnavailable('No real account')))
    monkeypatch.setattr(cli,'persist_portfolio_targets',lambda *a,**kw:pytest.fail('Targets forbidden'))
    with pytest.raises(OperationalDataUnavailable):
        cli.main(['--run-mode','paper','--account','default','--account-equity','100000'])


@pytest.mark.parametrize('mode,dry,expected',[('paper',False,'paper'),('live',False,'live'),
    ('simulate',False,'paper'),('simulate',True,'shadow')])
def test_pipeline_binds_risk_to_its_broker_mode(mode,dry,expected):
    from ihm.services.pipeline_runner import PipelineLaunchOptions,build_pipeline_command
    command=build_pipeline_command('risk_management',PipelineLaunchOptions(execution_mode=mode,risk_dry_run=dry))
    assert command[command.index('--run-mode')+1]==expected
