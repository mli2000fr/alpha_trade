"""Local consensus consultation: scope, dates, units, descriptions and UI."""
from datetime import date,datetime
from types import SimpleNamespace

import pytest
import pandas as pd
from sqlalchemy import create_engine,event,text
from sqlalchemy.pool import StaticPool

from ihm.services import consensus_review as review
from ihm.components import symbol_consensus_panel as panel


@pytest.fixture
def engine():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    strings={'provider','symbol','snapshot_date','fiscal_period_end','horizon_raw',
             'observed_at','available_at','currency','run_id','raw_hash','qualification_status',
             'parser_version','ingestion_at'}
    with engine.begin() as conn:
        conn.execute(text(f'CREATE TABLE {review.TABLE} ('+', '.join(
            f'`{f}` '+('TEXT' if f in strings else 'FLOAT') for f in review.FIELDS)+')'))
        base=dict(provider='eodhd',symbol='FUN',snapshot_date='2026-10-16',
            fiscal_period_end='2026-12-31',horizon_raw='0q',observed_at='2026-10-16 23:00:00',
            available_at='2026-10-16 23:00:00',eps_current=1.2,eps_avg=1.1,eps_30d_ago=1.,
            eps_analyst_count=0,units_qualified=0,historical_pit_qualified=0,
            fiscal_identity_qualified=0,qualification_status='RESEARCH_ONLY',id=1)
        samples=[base,
            dict(base,id=2,snapshot_date='2026-10-15',available_at='2026-10-15 23:00:00',observed_at='2026-10-15 23:00:00'),
            dict(base,id=3,symbol='OTHER'),dict(base,id=4,provider='yahoo'),
            dict(base,id=5,snapshot_date='2026-10-17'),
            # Midnight NY on Oct 17 is 04:00 UTC: equal cutoff is excluded.
            dict(base,id=6,fiscal_period_end='2030-12-31',available_at='2026-10-17 04:00:00'),
            dict(base,id=7,fiscal_period_end='2031-12-31',available_at=None),
            # Old fiscal date is NOT a past snapshot: allowed as received Oct 16.
            dict(base,id=8,fiscal_period_end='2023-12-31',horizon_raw='0y'),
            dict(base,id=9,fiscal_period_end='2032-12-31',observed_at='2026-10-17 05:00:00')]
        for row in samples:
            conn.execute(text(f'INSERT INTO {review.TABLE} ('+','.join(row)+') VALUES ('+
                ','.join(':'+key for key in row)+')'),row)
    return engine


def test_reads_only_symbol_provider_received_before_ny_cutoff(engine):
    statements=[]
    event.listen(engine,'before_cursor_execute',lambda c,cu,s,p,ctx,m:statements.append(s))
    assert review.load_snapshot_days(engine,'FUN','2026-10-16')==['2026-10-16','2026-10-15']
    rows=review.load_snapshot(engine,'FUN','2026-10-16','2026-10-16')
    assert {r['id'] for r in rows}=={1,8}
    history=review.load_period_history(engine,'FUN','2026-10-16','2026-10-15','2026-12-31','0q')
    assert [r['snapshot_date'] for r in history]==['2026-10-15']
    assert all(s.lstrip().upper().startswith('SELECT') for s in statements)


def test_no_backdating_or_foreign_scope(engine):
    assert not review.load_snapshot_days(engine,'FUN','2023-12-31')
    assert not review.load_snapshot(engine,'FUN','2026-10-15','2026-10-16')
    assert not review.load_snapshot_days(engine,"FUN'",'2026-10-16')
    with pytest.raises(ValueError,match='Symbole invalide'):
        review.load_snapshot_days(engine,"FUN' OR 1=1--",'2026-10-16')
    assert not review.load_period_history(engine,'FUN','2026-10-16','2026-10-16','2026-12-31','+1q')
    wrong=SimpleNamespace(dialect=SimpleNamespace(name='mysql'),url=SimpleNamespace(database='alpha_trade_fr'))
    with pytest.raises(ValueError,match='US'):
        review.load_snapshot_days(wrong,'FUN','2026-10-16')


@pytest.mark.parametrize('day,cutoff',[
    ('2026-10-16',datetime(2026,10,17,4)),('2026-12-16',datetime(2026,12,17,5))])
def test_dst_cutoff_is_ny_day_not_paris_or_utc(engine,day,cutoff):
    assert review.scope(engine,'FUN',day)['cutoff']==cutoff


def test_unknown_is_not_zero_and_units_not_invented():
    row=dict(eps_current=1.2,eps_7d_ago=None,eps_30d_ago=1.,eps_60d_ago=0,eps_90d_ago=-1)
    changes=review.change_rows(row)
    assert changes[0]['Variation (%)']=='Non calculée'
    assert changes[1]['Variation (%)']=='20'
    assert changes[2]['Variation (%)']==changes[3]['Variation (%)']=='Non calculée'
    assert review.format_value(0)=='0' and review.format_value(None)=='Non fourni / inconnu'
    values={r['Colonne']:r for r in review.field_rows({'units_qualified':0},'Qualification et traçabilité')}
    assert values['units_qualified']['Valeur']=='Non'
    numeric=[f for fields in review.GROUPS.values() for f,_,_ in fields]
    assert len(numeric)==len(set(numeric))


def test_bounded_days_and_history(engine):
    with engine.begin() as conn:
        for i,day in enumerate(pd.date_range('2026-01-01',periods=100)):
            conn.execute(text(f'''INSERT INTO {review.TABLE}
                (id,provider,symbol,snapshot_date,fiscal_period_end,horizon_raw,available_at,observed_at)
                VALUES (:i,'eodhd','MANY',:day,'2026-12-31','0q',:stamp,:stamp)'''),
                dict(i=i+20,day=str(day.date()),stamp=str(day.date())+' 12:00:00'))
    assert len(review.load_snapshot_days(engine,'MANY','2026-10-16'))==90
    assert len(review.load_period_history(engine,'MANY','2026-10-16','2026-10-16','2026-12-31','0q'))==30


def test_ui_all_values_explained_and_selectors_reload(engine,monkeypatch,tmp_path):
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    from streamlit.testing.v1 import AppTest
    import streamlit.testing.v1.app_test as app_module
    monkeypatch.setattr(app_module,'TMP_DIR',SimpleNamespace(name=str(tmp_path)))
    monkeypatch.setattr(panel,'_days',lambda s,d:review.load_snapshot_days(engine,s,d))
    calls=[]
    def snapshot(s,d,day):
        calls.append(day)
        return review.load_snapshot(engine,s,d,day)
    monkeypatch.setattr(panel,'_snapshot',snapshot)
    monkeypatch.setattr(panel,'_history',lambda *a:review.load_period_history(engine,*a))
    app=AppTest.from_string('''
from ihm.components.symbol_consensus_panel import render_symbol_consensus_panel
render_symbol_consensus_panel('FUN','2026-10-16')
''').run(timeout=20)
    assert not app.exception and calls[-1]=='2026-10-16'
    assert len(app.table)==len(review.GROUPS) and len(app.dataframe)==2
    all_fields={field for grid in app.table for field in grid.value['Colonne']}
    assert all_fields==set(review.FIELDS)
    assert all(grid.value['Explication'].str.len().gt(15).all() for grid in app.table)
    app.selectbox[1].select(1).run(timeout=20)
    assert not app.exception
    identity=app.table[4].value
    assert identity.loc[identity['Colonne']=='fiscal_period_end','Valeur'].iloc[0]=='2023-12-31'
    app.selectbox[0].select('2026-10-15').run(timeout=20)
    assert not app.exception and calls[-1]=='2026-10-15'
    assert any('RESEARCH_ONLY' in w.value for w in app.warning)


@pytest.mark.parametrize('failure',[False,True])
def test_ui_missing_data_or_sql_error_is_not_neutral_or_secret(monkeypatch,tmp_path,failure):
    import tempfile
    monkeypatch.setattr(tempfile,'tempdir',str(tmp_path))
    from streamlit.testing.v1 import AppTest
    import streamlit.testing.v1.app_test as app_module
    monkeypatch.setattr(app_module,'TMP_DIR',SimpleNamespace(name=str(tmp_path)))
    def days(*a):
        if failure:
            raise RuntimeError('secret password')
        return []
    monkeypatch.setattr(panel,'_days',days)
    app=AppTest.from_string('''
from ihm.components.symbol_consensus_panel import render_symbol_consensus_panel
render_symbol_consensus_panel('FUN','2026-10-16')
''').run(timeout=20)
    assert not app.exception and not app.dataframe
    assert 'secret password' not in str(app)
    if failure:
        assert any('indisponible' in w.value for w in app.warning)
    else:
        assert any('Aucun consensus' in i.value for i in app.info)
