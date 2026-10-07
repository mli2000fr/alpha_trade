from dataclasses import replace
from unittest.mock import patch

import pytest

from risk_management.models import PriceInfo
from risk_management.position_sizer import PositionSizer
from backtesting.oracle_portfolio_session import OraclePortfolioSession
from risk_management.portfolio_builder import PortfolioBuilder
from scripts.research.us_concentrated_contract_audit import frozen_configs
from scripts.research.us_top10_equal_sizing import EqualProposalSizer,EqualProposalSession


def config():
    risk,_ = frozen_configs()
    return replace(risk,account_equity=4000.,risk_multiplier=1.,allow_fractional_shares=True)


def test_equal_dollars_preserve_native_positive_proposal_sum():
    cfg = config()
    prices = {'A':PriceInfo('A',100.,5.),'B':PriceInfo('B',50.,4.)}
    native = PositionSizer(cfg)
    expected = sum(native.compute(p).proposed_shares*p.last_close for p in prices.values())
    sizer = EqualProposalSizer(cfg,prices)
    notionals = [sizer.compute(p).proposed_shares*p.last_close for p in prices.values()]
    assert notionals[0] == pytest.approx(notionals[1],abs=1e-6)
    assert sum(notionals) == pytest.approx(expected,abs=1e-6)


def test_original_minimum_rejection_is_not_revived():
    cfg = config()
    prices = {'A':PriceInfo('A',100.,5.),'B':PriceInfo('B',1.,50.)}
    sizer = EqualProposalSizer(cfg,prices)
    assert sizer.compute(prices['B']).proposed_shares == 0
    assert sizer.compute(prices['A']).proposed_shares == PositionSizer(cfg).compute(prices['A']).proposed_shares


def test_scoped_research_builder_restored_even_on_failure():
    session = object.__new__(EqualProposalSession)
    with patch.object(OraclePortfolioSession,'decide',side_effect=ValueError('fixture')):
        with pytest.raises(ValueError,match='fixture'):
            session.decide()
    import backtesting.oracle_portfolio_session as module
    assert module.PortfolioBuilder is PortfolioBuilder
