from datetime import date

import pytest

from service.fr.preanchor_replay_16g import check_chain, qualify


def evaluate(version):
    return qualify({('FR1', 'XPAR'): [version]} if version else {},
                   [{'symbol': 'TEST.PA', 'isin': 'FR1', 'mic': 'XPAR'}],
                   [date(2026, 9, 9)], [])


def version(**changes):
    return dict({'asof_from': '2026-09-05', 'asof_to': None, 'event': 'Full',
                 'first_trade_reported': '2000-01-01', 'currency': 'EUR'}, **changes)


def test_covered_is_not_released():
    report = evaluate(version())
    assert report['reference_covered_count'] == 1
    assert report['matrix'][0]['trading_currency_qualified'] is False
    assert report['serving_allowed'] is False
    assert report['historical_decision_release'] is False


def test_missing_reference():
    assert evaluate(None)['reference_covered_count'] == 0


def test_late_listing():
    assert evaluate(version(first_trade_reported='2026-09-10'))['reference_covered_count'] == 0


def test_terminated():
    assert evaluate(version(termination_reported='2026-09-09'))['reference_covered_count'] == 0


def test_terminal_event():
    assert evaluate(version(event='CancRcrd'))['reference_covered_count'] == 0


def test_future_version():
    assert evaluate(version(asof_from='2026-09-10'))['reference_covered_count'] == 0


def chain():
    rows = [{'file': f'FULINS_E_20260905_{n:02d}of02.zip', 'type': 'FULINS_E'} for n in (1, 2)]
    name = 'DLTINS_20260906_01of01.zip'
    return rows + [{'file': name, 'type': 'DLTINS', 'date': '2026-09-06',
                    'url': 'https://firds.esma.europa.eu/firds/' + name}]


def test_chain_accepts_fulls_and_daily_index_separately():
    assert check_chain(chain(), date(2026, 9, 5), date(2026, 9, 6)) == []


def test_chain_missing_daily_publication():
    with pytest.raises(ValueError):
        check_chain(chain()[:2], date(2026, 9, 5), date(2026, 9, 6))


def test_chain_duplicate_full():
    rows = chain()
    rows[1] = rows[0]
    with pytest.raises(ValueError):
        check_chain(rows, date(2026, 9, 5), date(2026, 9, 6))


def test_partial_window_does_not_certify_all_sessions():
    report = qualify({('FR1', 'XPAR'): [version(asof_from='2026-09-12')]},
        [{'symbol': 'TEST.PA', 'isin': 'FR1', 'mic': 'XPAR'}],
        [date(2026, 9, 9), date(2026, 9, 14)], [])
    assert report['matrix'][0]['covered_session_count'] == 1
    assert report['reference_covered_count'] == 0
    assert report['matrix'][0]['all_sessions_active'] is False
