import pandas as pd

from modelFactory.oracle_balanced_universe import (
    CAP_TARGETS,
    VOL_TARGETS,
    allocation_matrix,
    is_excluded_security_name,
)


def test_allocation_matrix_has_exact_margins() -> None:
    matrix = allocation_matrix()
    assert sum(matrix.values()) == 400
    for cap, expected in CAP_TARGETS.items():
        assert sum(value for (bucket, _), value in matrix.items() if bucket == cap) == expected
    for quintile, expected in VOL_TARGETS.items():
        assert sum(value for (_, q), value in matrix.items() if q == quintile) == expected


def test_security_type_proxy_avoids_issuer_name_false_positives() -> None:
    names = pd.Series([
        "Preferred Bank Common Stock",
        "Example plc American Depositary Shares right to receive",
        "Energy Transfer LP Common Units",
    ])
    assert not is_excluded_security_name(names).any()


def test_security_type_proxy_excludes_non_common_instruments() -> None:
    names = pd.Series([
        "Example S&P 500 ETF",
        "Example Acquisition Corp. Units",
        "Example Depositary Shares 6% Preferred Stock",
        "Example Warrants",
        "Example Subscription Rights",
    ])
    assert is_excluded_security_name(names).all()
