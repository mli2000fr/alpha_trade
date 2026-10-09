import json

import pytest

from service.fr.trading212_demo_17b import DemoReader, SafeReadError, match_instruments, run, ENDPOINTS


class Response:
    status_code = 200
    def iter_content(self, chunk_size):
        yield b'{}'
    def close(self):
        pass


class Session:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or Response()
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response
    def close(self):
        pass


def test_only_demo_allowlist_get_once():
    session = Session()
    client = DemoReader('private-key', 'private-secret', session)
    client.get('account')
    url, params = session.calls[0]
    assert url.startswith('https://demo.trading212.com/api/v0/')
    assert params['allow_redirects'] is False
    with pytest.raises(SafeReadError):
        client.get('account')
    for name in ('https://live.trading212.com', 'submit', '../orders'):
        with pytest.raises(SafeReadError):
            client.get(name)
    assert len(session.calls) == 1


@pytest.mark.parametrize('code', [301, 401, 403, 429, 500])
def test_provider_body_never_used(code):
    response = Response()
    response.status_code = code
    with pytest.raises(SafeReadError, match=f'^HTTP_{code}$'):
        DemoReader('key', 'secret', Session(response)).get('account')


def test_transport_error_redacted():
    class Broken(Session):
        def get(self, *args, **kwargs):
            raise RuntimeError('private-key private-secret')
    with pytest.raises(SafeReadError, match='^TRANSPORT_ERROR$'):
        DemoReader('private-key', 'private-secret', Broken()).get('account')


def test_schedule_join_and_ambiguous_matches():
    matrix = [{'isin': 'FRTEST', 'symbol': 'TEST.PA', 'mic': 'XPAR'}]
    instruments = [{'isin': 'FRTEST', 'currencyCode': 'EUR', 'type': 'STOCK',
                    'ticker': 'TEST', 'workingScheduleId': 99}]
    exchanges = [{'id': 99, 'name': 'Wrong', 'workingSchedules': []},
                 {'id': 5, 'name': 'Paris', 'workingSchedules': [{'id': 99}]}]
    row = match_instruments(matrix, instruments, exchanges)[0]
    assert row['matches'][0]['schedule_exchange_names'] == ['Paris']
    assert row['execution_mic_qualified'] is False
    assert match_instruments(matrix, instruments * 2, exchanges)[0]['state'] == 'AMBIGUOUS'


@pytest.mark.parametrize('currency,status', [
    ('EUR', 'READONLY_REACHABLE_NOT_RELEASED'),
    ('USD', 'BLOCKED_ACCOUNT_CURRENCY_NOT_EUR')])
def test_run_private_archive_and_sanitized_summary(tmp_path, currency, status):
    packet = tmp_path / 'artifacts/fr/packet.json'
    packet.parent.mkdir(parents=True)
    packet.write_text(json.dumps({'market_code': 'FR_EQ', 'matrix': []}))
    class Reader:
        def get(self, name):
            payload = {'currency': currency, 'id': 'private-account'} if name == 'account' else (
                {'items': [], 'nextPagePath': '/unfollowed'} if name == 'history' else [])
            return payload, json.dumps(payload).encode()
    report = run(root=tmp_path, packet='artifacts/fr/packet.json',
                 output_dir='artifacts/fr/result', reader=Reader())
    assert report['status'] == status
    assert 'private-account' not in json.dumps(report)
    assert report['history_truncated'] is True
    assert report['orders_sent'] == 0 and report['sql_writes'] is False
    assert len(report['endpoint_receipts']) == len(ENDPOINTS)


def test_response_size_bound():
    class Big(Response):
        def iter_content(self, chunk_size):
            yield b'x' * (32 * 1024 * 1024 + 1)
    with pytest.raises(SafeReadError, match='RESPONSE_TOO_LARGE'):
        DemoReader('key', 'secret', Session(Big())).get('account')


def test_history_forbidden_is_unknown_not_empty(tmp_path):
    packet = tmp_path / 'artifacts/fr/packet.json'
    packet.parent.mkdir(parents=True)
    packet.write_text(json.dumps({'market_code': 'FR_EQ', 'matrix': []}))
    class Reader:
        def get(self, name):
            if name == 'history':
                raise SafeReadError('HTTP_403')
            payload = {'currency': 'EUR'} if name == 'account' else []
            return payload, json.dumps(payload).encode()
    report = run(root=tmp_path, packet='artifacts/fr/packet.json',
                 output_dir='artifacts/fr/result', reader=Reader())
    assert report['status'] == 'PARTIAL_READONLY_NOT_RELEASED'
    assert report['history_first_page_count'] is None
    assert report['history_truncated'] is None
