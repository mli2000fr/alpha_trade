"""Reserved ticker directories remain included in portable backup/restore."""
import pytest

from common.symbol_artifact_paths import symbol_directory
from service.migration import engine, inventory, storage


@pytest.mark.parametrize('symbol', ['CON', 'con', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT9', 'CON.A'])
def test_reserved_ticker_names_are_portable(symbol, tmp_path):
    folder = symbol_directory(tmp_path / 'symbols', symbol)
    assert folder.name == 'symbol=' + symbol
    storage.validate_relative_name(folder.relative_to(tmp_path).as_posix())


@pytest.mark.parametrize('symbol', ['AAPL', 'CONX', 'BRK.B', 'BF-B', 'COM10'])
def test_ordinary_symbols_keep_existing_paths(symbol, tmp_path):
    assert symbol_directory(tmp_path, symbol) == tmp_path / symbol


@pytest.mark.parametrize('symbol', ['', '.', '..', '../CON', 'A/B', 'A\\B', 'A:', 'CON.', 'symbol=CON', 'A '])
def test_unsafe_names_and_alias_collisions_are_rejected(symbol, tmp_path):
    with pytest.raises(ValueError):
        symbol_directory(tmp_path, symbol)


def test_reserved_ticker_artifacts_round_trip_through_real_encrypted_package(tmp_path):
    root = tmp_path / 'source'
    folder = symbol_directory(root / 'artifacts/research/campaign/symbols', 'CON')
    folder.mkdir(parents=True)
    expected = {'result.json': b'{"symbol":"CON"}', 'parcours_h20-panel.parquet': b'PAR1-fixture-PAR1'}
    for name, raw in expected.items():
        (folder / name).write_bytes(raw)
    entries = inventory.scan(root)
    inventory.validate_portable_names(entries)
    records = entries['etats-et-archives']
    assert len(records) == len(expected)
    assert all('/symbol=CON/' in row['path'] for row in records)
    package_root = tmp_path / 'backup'
    package = engine.pack_files(root, package_root / 'files', 'research', records,
                                'synthetic-test-password', 1024 * 1024, None)
    package['folder'] = 'files'
    target = tmp_path / 'restored'
    engine.extract_files(package_root, {'packages': [package]}, target, 'synthetic-test-password')
    for name, raw in expected.items():
        restored = target / folder.relative_to(root) / name
        assert restored.read_bytes() == raw
        assert storage.sha_file(restored) == storage.sha_file(folder / name)
    assert not (target / 'artifacts/research/campaign/symbols/CON').exists()
