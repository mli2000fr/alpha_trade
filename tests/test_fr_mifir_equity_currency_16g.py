import csv
import io
import zipfile

import pytest

from service.fr.mifir_equity_currency_16g import REQUIRED, analyze, select_rows


def trade(**changes):
    row = {key: '-' for key in REQUIRED}
    row.update(TradingDateTime='2026-10-07T12:00:00Z', PublicationDateTime='2026-10-07T12:00:01Z',
               MifidInstrumentID='FR0000120321', Venue='XPAR', VenueOfPublication='XPAR',
               TradeUniqueIdentifier='one', MifidPrice='350', MifidQuantity='3',
               MifidPriceNotation='MONE', MifidCurrency='EUR', NumberOfTransactions='1')
    return dict(row, **changes)


def result(rows):
    return analyze(rows, '2026-10-08T20:00:00Z')


def test_point_not_interval_or_release():
    row = result([trade()])['matrix'][1]
    assert row['currencies'] == {'EUR': 1}
    assert row['point_observation_status'] == 'DATED_TRADE_CURRENCY_OBSERVED'
    assert not row['trading_currency_interval_qualified'] and not row['servable']


def test_duplicate_not_second_trade():
    r = result([trade(), trade()])
    assert r['accepted_rows'] == 1 and r['exact_duplicates_removed'] == 1


@pytest.mark.parametrize('changes', [
    {'MmtModificationIndicator': 'CANC'}, {'MmtModificationIndicator': 'AMND'},
    {'Venue': 'XAMS'}, {'MifidPriceNotation': 'PERC'}, {'MifidPrice': 'NaN'},
    {'PublicationDateTime': '2026-10-08T19:55:00Z'}, {'MmtPostTradeDeferral': 'LRGS'},
])
def test_unqualified_rows_rejected(changes):
    assert result([trade(**changes)])['accepted_rows'] == 0


def test_conflicting_trade_id_rejects_both():
    assert result([trade(), trade(MifidPrice='351')])['accepted_rows'] == 0


def test_currency_conflict_not_eur_assumption():
    row = result([trade(), trade(TradeUniqueIdentifier='two', MifidCurrency='USD')])['matrix'][1]
    assert row['point_observation_status'] == 'CURRENCY_CONFLICT'


def test_cash_schema_does_not_require_derivative_columns():
    row = trade()
    row.pop('NumberOfTransactions')
    assert 'MmtPostTradeDeferral' not in row
    assert result([row])['accepted_rows'] == 1
    assert result([row])['counts_are_publication_rows_not_certified_trade_count']


def test_publication_mode_not_assumed_regular():
    assert result([trade(MmtPublicationMode='LRGS')])['accepted_rows'] == 0


def test_parser_selects_only_pilot():
    fields = ['TradingDateTime'] + sorted(set(trade()) - {'TradingDateTime'})
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerows([trade(), trade(MifidInstrumentID='FR0000000000')])
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as archive:
        archive.writestr('trades.csv', 'Copyright Euronext\n' + text.getvalue())
    rows, count, notice = select_rows(raw.getvalue())
    assert len(rows) == 1 and count == 2 and notice == 'Copyright Euronext'
