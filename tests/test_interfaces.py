"""
Tests unitaires pour core/interfaces.py
"""
import pytest
import pandas as pd
from datetime import date
from typing import Sequence, Optional
from core import interfaces

# Mocks pour chaque interface
class DummyPriceRepository:
    def load_prices(self, symbols: Sequence[str], start: Optional[date] = None, end: Optional[date] = None) -> pd.DataFrame:
        return pd.DataFrame({
            'symbol': ['A', 'B'],
            'date': [date(2023,1,1), date(2023,1,1)],
            'open': [1,2], 'high': [2,3], 'low': [0,1], 'close': [1.5,2.5], 'volume': [100,200], 'adj_close': [1.5,2.5]
        })
    def load_latest_close(self, symbols: Sequence[str]) -> pd.Series:
        return pd.Series({'A': 1.5, 'B': 2.5})

class DummyScoreRepository:
    def load_scores(self, symbols: Sequence[str]) -> pd.DataFrame:
        return pd.DataFrame({'symbol': ['A'], 'liquidity_val': [1], 'relative_strength_index': [50], 'total_score': [0.5], 'sector': ['Tech']})
    def upsert_scores(self, scores: pd.DataFrame) -> int:
        return len(scores)

class DummyFactorEngine:
    def compute(self, prices: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({'symbol': prices['symbol'], 'trend_score': [1]*len(prices)})

class DummyScoringEngine:
    def score(self, factors: pd.DataFrame, aux_scores: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({'symbol': factors['symbol'], 'raw_final_score': [1]*len(factors), 'final_score': [1]*len(factors)})

class DummySentimentProvider:
    def get_sentiment_scores(self, symbols: Sequence[str], as_of: Optional[date] = None) -> pd.DataFrame:
        return pd.DataFrame({'symbol': ['A'], 'sentiment_net_score': [0.1], 'macro_impact_score': [0.2], 'event_count': [3]})

class DummyRiskChecker:
    def check_position_size(self, symbol: str, proposed_shares: float, price: float) -> float:
        return min(proposed_shares, 10)
    def is_circuit_breaker_active(self) -> bool:
        return False

class DummyOrderManager:
    def submit_market_order(self, symbol: str, qty: float, side: str) -> str:
        return 'order123'
    def cancel_order(self, order_id: str) -> bool:
        return True

class DummyBrokerPort:
    def submit_order(self, symbol: str, qty: float, side: str, type_: str = "market", **kwargs) -> str:
        return 'broker_order123'
    def cancel_order(self, order_id: str) -> bool:
        return True
    def get_order_status(self, order_id: str) -> str:
        return 'FILLED'
    def get_positions(self) -> list:
        return [{'symbol': 'A', 'qty': 10}]

def test_price_repository_protocol():
    repo = DummyPriceRepository()
    assert isinstance(repo, interfaces.PriceRepository)
    df = repo.load_prices(['A','B'])
    assert 'symbol' in df.columns
    s = repo.load_latest_close(['A','B'])
    assert s['A'] == 1.5

def test_score_repository_protocol():
    repo = DummyScoreRepository()
    assert isinstance(repo, interfaces.ScoreRepository)
    df = repo.load_scores(['A'])
    assert 'liquidity_val' in df.columns
    n = repo.upsert_scores(df)
    assert n == 1

def test_factor_engine_protocol():
    engine = DummyFactorEngine()
    assert isinstance(engine, interfaces.FactorEngine)
    df = engine.compute(pd.DataFrame({'symbol':['A']}))
    assert 'trend_score' in df.columns

def test_scoring_engine_protocol():
    engine = DummyScoringEngine()
    assert isinstance(engine, interfaces.ScoringEngine)
    df = engine.score(pd.DataFrame({'symbol':['A']}), pd.DataFrame({'symbol':['A']}))
    assert 'final_score' in df.columns

def test_sentiment_provider_protocol():
    provider = DummySentimentProvider()
    assert isinstance(provider, interfaces.SentimentProvider)
    df = provider.get_sentiment_scores(['A'])
    assert 'sentiment_net_score' in df.columns

def test_risk_checker_protocol():
    checker = DummyRiskChecker()
    assert isinstance(checker, interfaces.RiskChecker)
    assert checker.check_position_size('A', 20, 1.5) == 10
    assert not checker.is_circuit_breaker_active()

def test_order_manager_protocol():
    manager = DummyOrderManager()
    assert isinstance(manager, interfaces.OrderManager)
    assert manager.submit_market_order('A', 1, 'buy') == 'order123'
    assert manager.cancel_order('order123')

def test_broker_port_protocol():
    port = DummyBrokerPort()
    assert isinstance(port, interfaces.BrokerPort)
    assert port.submit_order('A', 1, 'buy') == 'broker_order123'
    assert port.cancel_order('id')
    assert port.get_order_status('id') == 'FILLED'
    positions = port.get_positions()
    assert isinstance(positions, list)
    assert positions[0]['symbol'] == 'A'

