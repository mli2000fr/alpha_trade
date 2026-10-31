"""Reserved ticker names must not break a portable backup after database export."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from service import _finnhub_cache as cache
from service.migration import engine,inventory,storage


@pytest.mark.parametrize('symbol',['CON','NUL','PRN','AUX','COM1','LPT9','CON.A'])
def test_reserved_ticker_cache_is_portable_and_round_trips(tmp_path,monkeypatch,symbol):
    monkeypatch.setenv('FINNHUB_CACHE_DIR',str(tmp_path))
    path=cache._cache_path(symbol)
    assert path.name=='symbol='+symbol+'.json'
    storage.validate_relative_name(path.name)
    cache.store_profile(symbol,{'ticker':symbol,'name':'Synthetic company'})
    assert cache.get_cached_profile(symbol)['ticker']==symbol
    cache.invalidate(symbol)
    assert not path.exists()


def test_ordinary_cache_names_are_unchanged(tmp_path,monkeypatch):
    monkeypatch.setenv('FINNHUB_CACHE_DIR',str(tmp_path))
    assert cache._cache_path('AAPL').name=='AAPL.json'
    assert cache._cache_path('CONX').name=='CONX.json'


def test_inventory_reports_exact_nonportable_name_before_any_database_export(tmp_path,monkeypatch):
    root=tmp_path/'source';root.mkdir()
    bad='artifacts/finnhub_cache/CON.json'
    monkeypatch.setattr(inventory,'scan',lambda *a,**k:{'etats-et-archives':[
        dict(path=bad,size=539,mtime_ns=0)]})
    db=Mock()
    with pytest.raises(ValueError,match='artifacts/finnhub_cache/CON.json'):
        engine.export(root,tmp_path/'backup','synthetic-test-password',db,
            guard=False,captured=dict(values={},variables=[]))
    db.inspect.assert_not_called();db.dump.assert_not_called()
    assert not (tmp_path/'backup/manifest.json').exists()


def test_inventory_preview_also_reports_portability_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(inventory,'scan',lambda *a,**k:{'application':[
        dict(path='data/NUL.json',size=1,mtime_ns=0)]})
    with pytest.raises(ValueError,match='data/NUL.json'):
        inventory.preview(tmp_path)
