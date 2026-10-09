import pytest

from service.fr.trading212_mapping_17c import qualify


def air_row():
    return {'symbol': 'AIR.PA', 'isin': 'NL0000235190', 'expected_mic': 'XPAR',
            'matches': [
                {'ticker': 'AIRp_EQ', 'currency': 'EUR', 'schedule_exchange_names': ['Euronext Paris']},
                {'ticker': 'AIRd_EQ', 'currency': 'EUR', 'schedule_exchange_names': ['Deutsche Börse Xetra']}]}


def test_paris_listing_resolution_never_qualifies_execution():
    mapped, excluded = qualify([air_row()])
    assert not excluded
    assert mapped[0]['broker_ticker'] == 'AIRp_EQ'
    assert mapped[0]['execution_mic_qualified'] is False
    assert mapped[0]['orders_allowed'] is False


@pytest.mark.parametrize('mutation', ['ambiguous', 'missing', 'wrong_currency', 'unknown_schedule'])
def test_fail_closed_matching(mutation):
    row = air_row()
    if mutation == 'ambiguous':
        row['matches'].append(row['matches'][0].copy())
    elif mutation == 'missing':
        row['matches'] = []
    elif mutation == 'wrong_currency':
        row['matches'][0]['currency'] = 'USD'
    else:
        row['matches'][0]['schedule_exchange_names'] = []
    mapped, excluded = qualify([row])
    assert not mapped and len(excluded) == 1


def test_duplicate_isin_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        qualify([air_row(), air_row()])


def test_other_mic_rejected():
    row = air_row()
    row['expected_mic'] = 'XETR'
    mapped, excluded = qualify([row])
    assert not mapped
    assert excluded[0]['reason'] == 'MIC_OUTSIDE_INITIAL_XPAR_PILOT'


def test_bad_isin_rejected():
    row = air_row()
    row['isin'] = 'NL0000235191'
    with pytest.raises(ValueError, match='ISIN'):
        qualify([row])
