"""Sprint S8 — Tests des feature flags ML / sentiment et de la propagation
du kill-switch ML côté risk_management.

Couvre :

- ``core.feature_flags.FeatureFlags`` (parsing env, export, run_summary).
- ``risk_management.ml_gate.resolve_ml_gate_state`` (CLI flag + drift policy).
- Intégration ``RiskRepository.load_predictions_asof`` : retourne ``{}``
  quand le gate est fermé.
- ``run_execution._apply_feature_flags`` : flags CLI propagés dans os.environ.
- ``SentimentSignalAggregator.merge`` : skip fusion si sentiment désactivé.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest


# --------------------------------------------------------------------------
# core.feature_flags
# --------------------------------------------------------------------------


def test_feature_flags_parses_env_truthy(monkeypatch):
    from core.feature_flags import FeatureFlags

    monkeypatch.setenv("ALPHA_TRADE_DISABLE_SENTIMENT", "1")
    monkeypatch.setenv("ALPHA_TRADE_DISABLE_ML", "true")
    flags = FeatureFlags.from_env()
    assert flags.disable_sentiment is True
    assert flags.disable_ml is True


def test_feature_flags_default_false(monkeypatch):
    from core.feature_flags import FeatureFlags

    monkeypatch.delenv("ALPHA_TRADE_DISABLE_SENTIMENT", raising=False)
    monkeypatch.delenv("ALPHA_TRADE_DISABLE_ML", raising=False)
    flags = FeatureFlags.from_env()
    assert flags.disable_sentiment is False
    assert flags.disable_ml is False


def test_feature_flags_export_env_round_trip():
    from core.feature_flags import FeatureFlags

    env: dict = {"ALPHA_TRADE_DISABLE_ML": "stale-should-be-removed"}
    FeatureFlags(disable_sentiment=True, disable_ml=False).export_env(env)
    assert env["ALPHA_TRADE_DISABLE_SENTIMENT"] == "1"
    # disable_ml=False -> la clé existante doit être supprimée
    assert "ALPHA_TRADE_DISABLE_ML" not in env


def test_feature_flags_to_run_summary():
    from core.feature_flags import FeatureFlags

    payload = FeatureFlags(disable_sentiment=True, disable_ml=True).to_run_summary()
    assert payload == {"disable_sentiment": True, "disable_ml": True}


# --------------------------------------------------------------------------
# risk_management.ml_gate
# --------------------------------------------------------------------------


def test_ml_gate_disabled_by_feature_flag(monkeypatch):
    from risk_management.ml_gate import resolve_ml_gate_state

    monkeypatch.setenv("ALPHA_TRADE_DISABLE_ML", "1")
    state = resolve_ml_gate_state(engine=object())  # engine non interrogé
    assert state.enabled is False
    assert state.reason == "feature_flag_disable_ml"


def test_ml_gate_enabled_when_no_decision(monkeypatch):
    from risk_management import ml_gate

    monkeypatch.delenv("ALPHA_TRADE_DISABLE_ML", raising=False)
    monkeypatch.setattr(ml_gate, "load_latest_ml_gate_decision", lambda engine: None)
    state = ml_gate.resolve_ml_gate_state(engine=object())
    assert state.enabled is True
    assert state.reason == "no_decision_default_enabled"


def test_ml_gate_disabled_by_drift_policy(monkeypatch):
    from risk_management import ml_gate

    monkeypatch.delenv("ALPHA_TRADE_DISABLE_ML", raising=False)
    payload = {
        "kind": "drift_policy_decision",
        "decision": {"gate": "disabled", "drift_status": "ALERT", "action": "kill_switch_ml"},
        "gate_action": "kill_switch_ml",
        "run_id": "mdr-policy-42",
    }
    monkeypatch.setattr(ml_gate, "load_latest_ml_gate_decision", lambda engine: payload)
    state = ml_gate.resolve_ml_gate_state(engine=object())
    assert state.enabled is False
    assert state.reason == "drift_policy_kill_switch"
    assert state.decision_id == "mdr-policy-42"
    assert state.drift_status == "ALERT"


def test_ml_gate_enabled_when_drift_policy_allows(monkeypatch):
    from risk_management import ml_gate

    monkeypatch.delenv("ALPHA_TRADE_DISABLE_ML", raising=False)
    payload = {
        "kind": "drift_policy_decision",
        "decision": {"gate": "enabled", "drift_status": "WARN", "action": "allow"},
        "gate_action": "allow",
    }
    monkeypatch.setattr(ml_gate, "load_latest_ml_gate_decision", lambda engine: payload)
    state = ml_gate.resolve_ml_gate_state(engine=object())
    assert state.enabled is True
    assert state.reason == "drift_policy_enabled"


# --------------------------------------------------------------------------
# RiskRepository : kill-switch propagé
# --------------------------------------------------------------------------


def test_load_predictions_asof_returns_empty_when_ml_disabled(monkeypatch):
    """Si le gate ML est fermé, ``load_predictions_asof`` ne lit pas la DB."""
    from datetime import date as _date

    from risk_management import db_io as risk_db_io
    from risk_management.db_io import RiskRepository
    from risk_management.ml_gate import MlGateState

    # Bypass DB engine init (le constructeur tente get_sqlalchemy_engine).
    repo = RiskRepository.__new__(RiskRepository)
    repo.engine = SimpleNamespace()  # objet bidon, ne sera pas appelé

    monkeypatch.setattr(
        risk_db_io,
        "resolve_ml_gate_state",
        lambda engine: MlGateState(enabled=False, reason="feature_flag_disable_ml"),
    )

    # Si la fonction tentait quand même la requête, elle planterait sur engine.connect()
    out = repo.load_predictions_asof(["AAPL", "MSFT"], _date(2026, 5, 1))
    assert out == {}


# --------------------------------------------------------------------------
# run_execution.py : flags CLI -> os.environ
# --------------------------------------------------------------------------


def test_run_execution_apply_feature_flags_sets_env(monkeypatch):
    monkeypatch.delenv("ALPHA_TRADE_DISABLE_SENTIMENT", raising=False)
    monkeypatch.delenv("ALPHA_TRADE_DISABLE_ML", raising=False)
    import os

    import run_execution

    args = SimpleNamespace(disable_sentiment=True, disable_ml=False)
    run_execution._apply_feature_flags(args)
    try:
        assert os.environ["ALPHA_TRADE_DISABLE_SENTIMENT"] == "1"
        assert "ALPHA_TRADE_DISABLE_ML" not in os.environ
    finally:
        os.environ.pop("ALPHA_TRADE_DISABLE_SENTIMENT", None)
        os.environ.pop("ALPHA_TRADE_DISABLE_ML", None)


def test_run_execution_parser_accepts_disable_flags():
    import run_execution

    parser = run_execution.build_parser()
    args = parser.parse_args(["check", "--disable-ml", "--disable-sentiment"])
    assert args.disable_ml is True
    assert args.disable_sentiment is True


# --------------------------------------------------------------------------
# SentimentSignalAggregator.merge : skip fusion
# --------------------------------------------------------------------------


def test_signal_aggregator_merge_skips_when_sentiment_disabled(monkeypatch):
    """Avec le flag actif, ``final_score_sentiment == final_score`` (pure quant)."""
    monkeypatch.setenv("ALPHA_TRADE_DISABLE_SENTIMENT", "1")

    from event_sentiment.signal_aggregator import SentimentSignalAggregator

    # Bypass __init__ (évite d'instancier un Engine SQLAlchemy)
    agg = SentimentSignalAggregator.__new__(SentimentSignalAggregator)
    df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "NVDA"],
            "final_score": [0.8, 0.4, 0.6],
            "sector": ["Tech", "Tech", "Tech"],
        }
    )
    out = agg.merge(df)
    assert "final_score_sentiment" in out.columns
    assert (out["final_score_sentiment"].to_numpy() == out["final_score"].to_numpy()).all()
    assert out["sentiment_disabled"].all()


# --------------------------------------------------------------------------
# Intégration end-to-end : drift policy ALERT seedée -> gate fermé
# --------------------------------------------------------------------------


def test_ml_kill_switch_propagation_end_to_end(monkeypatch):
    """Simule un payload ml_drift_runs(payload.kind=drift_policy_decision) et
    vérifie que ``RiskRepository.load_predictions_asof`` court-circuite."""
    from datetime import date as _date

    from risk_management import db_io as risk_db_io, ml_gate
    from risk_management.db_io import RiskRepository

    monkeypatch.delenv("ALPHA_TRADE_DISABLE_ML", raising=False)

    payload = {
        "kind": "drift_policy_decision",
        "decision": {"gate": "disabled", "drift_status": "ALERT", "action": "kill_switch_ml"},
        "gate_action": "kill_switch_ml",
        "run_id": "mdr-policy-test",
    }
    monkeypatch.setattr(ml_gate, "load_latest_ml_gate_decision", lambda engine: payload)

    # Sanity : la fonction ml_gate retourne bien enabled=False
    state = ml_gate.resolve_ml_gate_state(engine=object())
    assert state.enabled is False

    repo = RiskRepository.__new__(RiskRepository)
    repo.engine = SimpleNamespace()
    out = repo.load_predictions_asof(["AAPL"], _date(2026, 5, 1))
    assert out == {}


# --------------------------------------------------------------------------
# Sanity : payload JSON parsing dans load_latest_ml_gate_decision
# --------------------------------------------------------------------------


def test_load_latest_ml_gate_decision_parses_json_string():
    """Vérifie la robustesse du parsing payload (str JSON ou dict natif)."""
    from risk_management.ml_gate import load_latest_ml_gate_decision

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, _stmt):
            class _R:
                def mappings(self_inner):
                    return self_inner

                def all(self_inner):
                    return [
                        {
                            "run_id": "mdr-policy-1",
                            "status": "ALERT",
                            "payload": json.dumps(
                                {"kind": "drift_policy_decision", "decision": {"gate": "disabled"}}
                            ),
                        }
                    ]
            return _R()

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    out = load_latest_ml_gate_decision(_FakeEngine())
    assert out is not None
    assert out["kind"] == "drift_policy_decision"
    assert out["decision"]["gate"] == "disabled"



