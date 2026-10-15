from pathlib import Path

import pytest

from scripts.research import us_news_event_pilot_collect as pilot


def test_http_budget_counts_every_attempt_and_disallows_other_hosts_and_redirects():
    class Session:
        def request(self, method, url, **kwargs):
            assert kwargs['allow_redirects'] is False
            return 200
    budget = pilot.Transport(2)
    proxy = budget.proxy(Session())
    for _ in range(2):
        assert proxy.request('GET','https://eodhd.com/api/news') == 200
    with pytest.raises(pilot.AttemptLimit):
        proxy.request('GET','https://eodhd.com/api/news')
    assert budget.attempts == 2
    with pytest.raises(RuntimeError):
        proxy.request('GET','https://other.example/api/news')
    with pytest.raises(RuntimeError):
        proxy.request('POST','https://eodhd.com/api/news')


def test_checkpoints_disabled_without_constructing_database_repository():
    repo = object.__new__(pilot.PilotRepository)
    assert repo.get_checkpoint('eodhd_news','FIXTURE') is None
    assert repo.upsert_checkpoint('eodhd_news','FIXTURE',None,None,'success') is None


def test_symbol_selection_is_fixed_bounded_without_prices():
    symbols = [f'FIXTURE{i}' for i in range(30)]
    assert pilot.shortlist(symbols) == pilot.shortlist(list(reversed(symbols)))
    assert len(pilot.shortlist(symbols)) == 12
    assert len(pilot.shortlist(symbols+symbols)) == 12


def test_default_prepares_only_and_refuses_overwrite(tmp_path):
    universe = tmp_path/'universe.txt'
    universe.write_text('FIXTURE1,FIXTURE2',encoding='utf-8')
    result = pilot.run(tmp_path/'pilot',universe)
    assert result['status'] == 'PREPARED_NOT_COLLECTED'
    assert set(result['symbols']) == {'FIXTURE1','FIXTURE2'}
    with pytest.raises(FileExistsError):
        pilot.run(tmp_path/'pilot',universe)


def test_system_trust_retains_tls_verification_without_modifying_global_factory():
    import ssl
    from requests import Request
    from scripts.research.us_news_event_windows_trust import SystemTrustAdapter
    adapter=SystemTrustAdapter()
    try:
        assert adapter.context.check_hostname
        assert adapter.context.verify_mode == ssl.CERT_REQUIRED
        request=Request('GET','https://eodhd.com/api/news').prepare()
        _,attrs=adapter.build_connection_pool_key_attributes(request,True)
        assert attrs['ssl_context'] is adapter.context
        assert attrs['cert_reqs']=='CERT_REQUIRED'
        with pytest.raises(RuntimeError,match='forbidden'):
            adapter.build_connection_pool_key_attributes(request,False)
    finally:
        adapter.close()
