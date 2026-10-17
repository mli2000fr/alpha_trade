from datetime import UTC, date, datetime
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, UniqueConstraint
from service.eodhd import ipo_calendar as mod


def item(**changes):
    return dict(code='ABC.US',name='ABC',start_date='2016-05-01',filing_date=None,
        amended_date=None,deal_type='Expected',price_from=0,price_to=12,offer_price=0,shares=0) | changes


def parsed(*items):
    return mod.normalize({'ipos':list(items)},['ABC'],datetime(2026,10,11,12,tzinfo=UTC),'test')


def test_monthly_windows_and_dates():
    assert list(mod.windows(date(2024,1,20),date(2024,3,2))) == [
        (date(2024,1,20),date(2024,1,31)),(date(2024,2,1),date(2024,2,29)),
        (date(2024,3,1),date(2024,3,2))]


def test_scope_zero_unknown_and_no_false_pit():
    row=parsed(item(),item(code='OUT.US'))[0]
    assert row['start_date']==date(2016,5,1)
    assert row['snapshot_date']==date(2026,10,11)
    assert row['available_at']==datetime(2026,10,11,12)
    assert row['offer_price'] is None and row['offered_shares'] is None
    assert not row['historical_pit_qualified']
    assert len(parsed(item(),item(code='OUT.US')))==1


@pytest.mark.parametrize('bad',[{'ipos':None},[],{'ipos':[{}]}])
def test_bad_schema_rejected(bad):
    with pytest.raises(ValueError):
        mod.normalize(bad,['ABC'],datetime.now(UTC),'test')


def test_append_versions_no_overwrite():
    rows=parsed(item(),item(deal_type='Priced',offer_price=10))
    metadata=MetaData()
    Table(mod.TABLE,metadata,*[Column(k,String) for k in rows[0]],
        UniqueConstraint('symbol','snapshot_date','raw_hash'))
    engine=create_engine('sqlite:///:memory:')
    metadata.create_all(engine)
    with engine.begin() as conn:
        assert mod.insert_rows(conn,rows)==2
        assert mod.insert_rows(conn,rows)==0
        assert conn.execute(text(f'SELECT COUNT(*) FROM {mod.TABLE}')).scalar()==2


def test_empty_calendar_success_and_counters(monkeypatch):
    from service.forward_pit import batch
    monkeypatch.setattr(batch,'_collection_symbols',lambda cfg:['ABC'])
    monkeypatch.setattr(mod,'verified_session',MagicMock)
    monkeypatch.setattr(mod,'_do_request',lambda **kwargs:{'ipos':[]})
    monkeypatch.setattr(mod,'get_default_tracker',lambda:None)
    monkeypatch.setattr(mod,'_get_token',lambda:'fake')
    monkeypatch.setattr(mod.time,'sleep',lambda _:None)
    engine=MagicMock();engine.url.database='alpha_trade'
    result=mod.collect(engine,{'start_date':'2016-01-01','end_date':'2016-01-31'},'test',True)
    assert result.requested==result.received==result.empty==1
    assert result.failed==result.persisted==0
    engine.connect.assert_not_called()


def test_catalog_schedule_and_universe():
    from ihm.services.batch_management import load_batch_specs,build_run_command
    spec=next(s for s in load_batch_specs() if s.name==mod.BATCH)
    assert spec.enabled
    assert spec.symbols_file=='config/univers_batch/univers_filtred_tradable.txt'
    assert spec.raw_config['symbol_source']=='universe-file'
    assert spec.universe_scope==spec.symbols_file
    assert spec.raw_config['run_hours']=='1'
    assert spec.raw_config['recovery_run_hours']=='5'
    assert 'forward_pit_launcher.ps1' in ' '.join(build_run_command(spec))
