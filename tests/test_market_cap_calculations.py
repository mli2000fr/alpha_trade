from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text, select

from common.market_cap import compute_sec_market_cap
from database.market_cap_snapshots import install_schema, metadata, snapshots
from service.forward_pit import market_cap_calculations as calc

NOW=datetime(2026,10,18,14,tzinfo=UTC)
PRICE=date(2026,10,16)
ASOF=date(2026,10,19)


@pytest.fixture
def engine():
    engine=create_engine('sqlite:///:memory:')
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text('''CREATE TABLE stock_fundamentals_daily (
            id INTEGER PRIMARY KEY, symbol TEXT, trade_date DATE,available_date DATE,fetched_at DATETIME,
            source TEXT,shares_outstanding FLOAT,market_cap FLOAT,fiscal_period_end DATE,accession_number TEXT)'''))
        conn.execute(text('''CREATE TABLE stock_bars_daily (
            symbol TEXT, date DATE,close FLOAT,adj_close FLOAT,is_filled INTEGER,data_source TEXT)'''))
        conn.execute(text('CREATE TABLE stock_metadata (symbol TEXT,company_name TEXT)'))
        conn.execute(text('''CREATE TABLE corporate_actions_events (
            symbol TEXT,ca_type TEXT,ex_date DATE,provider TEXT,ingested_at DATETIME)'''))
        conn.execute(text("INSERT INTO stock_metadata VALUES ('A','Example Inc'),('B','Other Inc')"))
        conn.execute(text("INSERT INTO stock_bars_daily VALUES ('A','2026-10-16',12,999,0,'alpaca_sip')"))
        conn.execute(text('''INSERT INTO stock_fundamentals_daily VALUES
            (1,'A','2026-09-01','2026-09-02','2026-09-01 12:00:00','SEC_EDGAR',100,999999,'2026-06-30','accession-1'),
            (2,'B','2026-09-01','2026-09-02','2026-09-01 12:00:00','SEC_EDGAR',200,NULL,'2026-06-30','accession-2'),
            (3,'B','2026-10-17','2026-10-18','2026-10-17 12:00:00','Finnhub',NULL,500,NULL,NULL)
            '''))
    return engine


def run_sec(engine, **kw):
    return calc.calculate_sec(engine,['A','B'],as_of=ASOF,max_age_days=365,price_date=PRICE,
                              now=kw.get('now',NOW),run_id=kw.get('run_id','one'))


def test_product_is_persisted_with_input_lineage_not_backdated(engine):
    result=run_sec(engine)
    assert result['symbols']=={'A'} and result['persisted']==1
    with engine.connect() as conn:
        row=conn.execute(select(snapshots)).mappings().one()
        assert row['market_cap']==1200 and row['reference_close']==12
        assert row['shares_outstanding']==100 and row['source']=='SEC_X_CLOSE'
        assert row['source_record_id']==1 and row['source_trade_date']==date(2026,9,1)
        assert row['observation_date']==NOW.date() and row['available_date']==ASOF
        assert row['price_date']==PRICE and row['accession_number']=='accession-1'
        # Existing filing fact is untouched, including its old ratio-enrichment value.
        assert conn.execute(text('SELECT market_cap FROM stock_fundamentals_daily WHERE id=1')).scalar()==999999
    assert result['details']['rejected_symbols']['B']=='MISSING_REFERENCE_CLOSE'


def test_repeated_same_inputs_do_not_duplicate_or_rewrite_first_observation(engine):
    run_sec(engine)
    result=run_sec(engine,now=NOW+timedelta(minutes=1),run_id='two')
    assert result['persisted']==0 and result['symbols']=={'A'}
    with engine.connect() as conn:
        rows=conn.execute(select(snapshots)).mappings().all()
    assert len(rows)==1 and rows[0]['run_id']=='one'


def test_changed_input_creates_a_traceable_new_observation(engine):
    run_sec(engine)
    with engine.begin() as conn:
        conn.execute(text('UPDATE stock_bars_daily SET close=13 WHERE symbol=\'A\''))
    assert run_sec(engine,run_id='two')['persisted']==1
    with engine.connect() as conn:
        assert len(conn.execute(select(snapshots)).all())==2


def test_finnhub_fallback_is_saved_without_fabricating_sec_shares(engine):
    sec=run_sec(engine)
    fh=calc.calculate_finnhub(engine,['B'],as_of=ASOF,max_age_days=365,now=NOW,run_id='one')
    assert sec['symbols']|fh['symbols']=={'A','B'} and fh['persisted']==1
    with engine.connect() as conn:
        row=conn.execute(select(snapshots).where(snapshots.c.symbol=='B')).mappings().one()
    assert row['source']=='FINNHUB' and row['market_cap']==500
    assert row['reference_close'] is None and row['shares_outstanding'] is None


@pytest.mark.parametrize('source',['alpaca_iex','unknown','alpaca'])
def test_iex_or_unknown_price_provenance_never_used(engine,source):
    with engine.begin() as conn:
        conn.execute(text('UPDATE stock_bars_daily SET data_source=:s'),{'s':source})
    assert not run_sec(engine)['symbols']


@pytest.mark.parametrize('source',['eodhd','eodhd_eod','alpaca_sip'])
def test_canonical_qualified_source_aliases_are_accepted(engine,source):
    with engine.begin() as conn:
        conn.execute(text('UPDATE stock_bars_daily SET data_source=:s'),{'s':source})
    assert run_sec(engine)['symbols']=={'A'}


def test_additive_installer_is_idempotent_and_preserves_other_tables():
    engine=create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE alembic_version (version_num TEXT)'))
        conn.execute(text("INSERT INTO alembic_version VALUES ('existing-head')"))
    install_schema(engine)
    install_schema(engine)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar()=='existing-head'
        assert conn.execute(select(snapshots)).all()==[]


@pytest.mark.parametrize('value,filled',[(0,0),(-1,0),(12,1),(12,None)])
def test_no_filled_or_invalid_close_is_multiplied(engine,value,filled):
    with engine.begin() as conn:
        conn.execute(text('UPDATE stock_bars_daily SET close=:c,is_filled=:f'),{'c':value,'f':filled})
    assert not run_sec(engine)['symbols']


def test_future_unclosed_date_not_substituted_for_missing_reference(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_bars_daily SET date='2026-10-19'"))
    assert not run_sec(engine)['symbols']


def test_future_source_values_are_not_used(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_fundamentals_daily SET available_date='2026-10-20' WHERE id=1"))
    assert not run_sec(engine)['symbols']


def test_future_fetch_timestamp_is_not_a_known_input(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_fundamentals_daily SET fetched_at='2026-10-20 12:00:00' WHERE id=1"))
    assert not run_sec(engine)['symbols']


def test_stale_shares_do_not_count_as_capitalization(engine):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_fundamentals_daily SET trade_date='2024-01-01' WHERE id=1"))
    assert not run_sec(engine)['symbols']


def test_known_split_since_share_measurement_goes_to_fallback(engine):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO corporate_actions_events VALUES ('A','split','2026-08-01','alpaca','2026-08-01 12:00:00')"))
    result=run_sec(engine)
    assert not result['symbols']
    assert result['details']['rejected_symbols']['A']=='KNOWN_SPLIT_SINCE_SHARE_BASIS'


@pytest.mark.parametrize('name',['Example ADR','Example Depositary Shares','Example ETF'])
def test_ambiguous_share_identity_not_multiplied(engine,name):
    with engine.begin() as conn:
        conn.execute(text("UPDATE stock_metadata SET company_name=:n WHERE symbol='A'"),{'n':name})
    assert not run_sec(engine)['symbols']


def test_output_calculated_later_not_claimed_available_at_earlier_cutoff(engine):
    result=calc.calculate_sec(engine,['A'],as_of=date(2026,10,18),max_age_days=365,price_date=PRICE,now=NOW,run_id='now')
    assert result['persisted']==1 and not result['symbols']


def test_calendar_respects_half_day_and_confirmation_delay(monkeypatch):
    sessions=[SimpleNamespace(session_date=date(2026,11,25),is_open=True,close_at_utc=datetime(2026,11,25,21,tzinfo=UTC)),
              SimpleNamespace(session_date=date(2026,11,27),is_open=True,close_at_utc=datetime(2026,11,27,18,tzinfo=UTC))]
    def get(context,**kwargs):
        assert context=='US_EQ' and kwargs['allow_us_weekday_fallback'] is False
        return SimpleNamespace(sessions=lambda a,b:sessions)
    monkeypatch.setattr(calc,'get_market_calendar',get)
    assert calc.reference_session(datetime(2026,11,27,18,29,tzinfo=UTC))==date(2026,11,25)
    assert calc.reference_session(datetime(2026,11,27,18,30,tzinfo=UTC))==date(2026,11,27)


@pytest.mark.parametrize('close,shares',[(float('nan'),10),(10,float('inf')),(1e308,1e308),(-1,10),(1,0)])
def test_product_must_be_finite_positive(close,shares):
    assert compute_sec_market_cap(close,shares) is None


def test_missing_migration_fails_before_calculation():
    with pytest.raises(RuntimeError,match='0109'):
        calc.calculate_sec(create_engine('sqlite:///:memory:'),['A'],as_of=ASOF,max_age_days=365,price_date=PRICE,now=NOW,run_id='no')
