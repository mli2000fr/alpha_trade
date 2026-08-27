"""Tests unitaires pour selector/dip_filter.py (Persistent Rank DIP filter).

Couvre :
- load_dip_filter_config() : clés prod_*/backtest_* distinctes + défauts
- _rank_column() : mapping horizon → colonne global_rank_{H}
- evaluate_dip_filter() : logique pure (persistance + dip + non-DIP)
- filter_day_candidates() : filtre DB réel (si données dispo) sinon skip
"""
from __future__ import annotations

import pandas as pd
import pytest

from selector.dip_filter import (
    _rank_column,
    evaluate_dip_filter,
    filter_day_candidates,
    load_dip_filter_config,
)


# ═══════════════════════════════════════════════════════════════════
# load_dip_filter_config — clés prod_*/backtest_* distinctes
# ═══════════════════════════════════════════════════════════════════

class TestLoadDipFilterConfig:
    def test_prod_and_backtest_defaults_disabled(self, monkeypatch):
        # Indépendant de l'état réel de config.yaml : on mocke la source.
        monkeypatch.setattr(
            "selector.dip_filter._load_yaml_config",
            lambda: {
                "prod_enabled": False,
                "prod_rank_horizon": 20,
                "backtest_enabled": False,
                "backtest_rank_horizon": 20,
            },
        )
        prod = load_dip_filter_config("prod")
        backtest = load_dip_filter_config("backtest")
        assert prod["enabled"] is False
        assert backtest["enabled"] is False
        # Défauts N4/X2 gelés
        assert prod["persist_days"] == 4
        assert prod["dip_pct"] == 0.02
        assert prod["rank_threshold"] == 0.90
        assert prod["rank_horizon"] == 20
        # Reclaim désactivé par défaut (vide → R off)
        assert prod["reclaim_ratio"] is None
        assert prod["reclaim_max_wait"] == 10

    def test_prod_backtest_independent(self, monkeypatch):
        # Simule une config où prod activé mais backtest désactivé
        monkeypatch.setattr(
            "selector.dip_filter._load_yaml_config",
            lambda: {
                "prod_enabled": True,
                "prod_rank_horizon": 10,
                "backtest_enabled": False,
                "backtest_rank_horizon": 20,
            },
        )
        prod = load_dip_filter_config("prod")
        backtest = load_dip_filter_config("backtest")
        assert prod["enabled"] is True
        assert prod["rank_horizon"] == 10
        assert backtest["enabled"] is False
        assert backtest["rank_horizon"] == 20


# ═══════════════════════════════════════════════════════════════════
# _rank_column — mapping horizon → colonne
# ═══════════════════════════════════════════════════════════════════

class TestRankColumn:
    def test_explicit_horizons(self):
        for h, col in [(3, "global_rank_3"), (10, "global_rank_10"), (20, "global_rank_20")]:
            assert _rank_column({"rank_horizon": h}) == col

    def test_none_uses_best_h(self):
        assert _rank_column({"rank_horizon": None}, best_h=10) == "global_rank_10"
        assert _rank_column({"rank_horizon": None}) == "global_rank_20"

    def test_invalid_horizon_falls_back(self):
        assert _rank_column({"rank_horizon": 999}) == "global_rank_20"


# ═══════════════════════════════════════════════════════════════════
# evaluate_dip_filter — logique pure (PIT)
# ═══════════════════════════════════════════════════════════════════

def _mk_config(**overrides) -> dict:
    cfg = {
        "enabled": True,
        "rank_horizon": 20,
        "rank_threshold": 0.90,
        "persist_days": 4,
        "dip_pct": 0.02,
    }
    cfg.update(overrides)
    return cfg


def _mk_rank(dates, values, rank_col="global_rank_20") -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "symbol": "AAA", rank_col: values})


def _mk_price(dates, closes) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "symbol": "AAA", "close": closes})


class TestEvaluateDipFilter:
    def test_disabled_returns_true(self):
        cfg = _mk_config(enabled=False)
        assert evaluate_dip_filter("AAA", "2024-06-14", pd.DataFrame(), pd.DataFrame(), cfg) is True

    def test_passes_persistence_and_dip(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        rh = _mk_rank(dates, [0.95, 0.92, 0.91, 0.93])
        # prix : close[J] = 100, close[J-4] = 110 → ret = -9.1% ≤ -2%
        ph = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [110.0, 108.0, 105.0, 102.0, 100.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config()) is True

    def test_rejects_non_persistent(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        # Un jour sous le seuil 0.90 → persistance cassée
        rh = _mk_rank(dates, [0.95, 0.92, 0.89, 0.93])
        ph = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [110.0, 108.0, 105.0, 102.0, 100.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config()) is False

    def test_rejects_no_dip(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        rh = _mk_rank(dates, [0.95, 0.92, 0.91, 0.93])
        # Prix en hausse → pas de DIP
        ph = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [100.0, 102.0, 104.0, 106.0, 108.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config()) is False

    def test_rejects_insufficient_history(self):
        dates = ["2024-06-13", "2024-06-14"]  # seulement 2 séances < N=4
        rh = _mk_rank(dates, [0.95, 0.93])
        ph = _mk_price(["2024-06-14"], [100.0])
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config()) is False

    def test_uses_rank_col_override(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        rh = _mk_rank(dates, [0.95, 0.92, 0.91, 0.93], rank_col="global_rank_10")
        ph = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [110.0, 108.0, 105.0, 102.0, 100.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, _mk_config(), rank_col="global_rank_10") is True


# ═══════════════════════════════════════════════════════════════════
# evaluate_dip_filter — reclaim_ratio (R) configurable
# ═══════════════════════════════════════════════════════════════════

# Scénario : N=4, seuil 0.90, dip 2%. DIP à J=D4 (close 90 vs 100 pré-DIP).
#   dates : 03/04/05/06/07 juin puis 10/11/12/13/14 juin (10 séances).
_RC_DATES = [
    "2024-06-03", "2024-06-04", "2024-06-05", "2024-06-06", "2024-06-07",
    "2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14",
]
_RC_CLOSES = [100.0, 99.0, 97.0, 94.0, 90.0, 92.0, 96.0, 97.0, 98.0, 99.0]
_RC_RANKS = [0.80, 0.95, 0.94, 0.92, 0.91, 0.90, 0.91, 0.92, 0.93, 0.94]


class TestEvaluateDipFilterReclaim:
    def _rh(self, ranks=None):
        return _mk_rank(_RC_DATES, list(ranks or _RC_RANKS))

    def _ph(self, closes=None):
        return _mk_price(_RC_DATES, list(closes or _RC_CLOSES))

    def test_reclaim_zero_behaves_like_d0(self):
        # reclaim_ratio=0 (ou vide) → R désactivé : entrée directe dès le DIP à J.
        cfg = _mk_config(reclaim_ratio=0)
        assert evaluate_dip_filter("AAA", "2024-06-07", self._rh(), self._ph(), cfg) is True
        # D0 re-signale tant que la baisse persiste (06-10, encore -7% vs J-4).
        assert evaluate_dip_filter("AAA", "2024-06-10", self._rh(), self._ph(), cfg) is True
        # R activé (0.95) attend le rebond : pas d'entrée au jour du DIP (90 < 95).
        cfg_r = _mk_config(reclaim_ratio=0.95)
        assert evaluate_dip_filter("AAA", "2024-06-07", self._rh(), self._ph(), cfg_r) is False

    def test_no_entry_before_rebound_then_entry(self):
        cfg = _mk_config(reclaim_ratio=0.95)
        # T=D5 (06-10) : close 92 < 0.95*100=95 → pas encore d'entrée.
        assert evaluate_dip_filter("AAA", "2024-06-10", self._rh(), self._ph(), cfg) is False
        # T=D6 (06-11) : close 96 >= 95 ET rank 0.91 >= 0.90 → entrée.
        assert evaluate_dip_filter("AAA", "2024-06-11", self._rh(), self._ph(), cfg) is True

    def test_reclaim_ratio_1p0_requires_full_recovery(self):
        # Récupération lente non-DIP jusqu'au prix pré-DIP (100). ratio 1.0 :
        # entrée uniquement quand close revient au prix d'origine (>= 100).
        closes = [100.0, 99.0, 97.0, 94.0, 90.0, 97.5, 98.0, 98.5, 99.0, 100.0]
        ranks = [0.80, 0.95, 0.94, 0.92, 0.91, 0.90, 0.91, 0.92, 0.93, 0.91]
        rh, ph = self._rh(ranks), self._ph(closes)
        cfg = _mk_config(reclaim_ratio=1.0)
        # À 99 (06-13) : 99 < 1.0*100 → pas encore (ratio 1.0 = prix pré-DIP).
        assert evaluate_dip_filter("AAA", "2024-06-13", rh, ph, cfg) is False
        # Retour au prix d'origine (100) en 06-14 → entrée.
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, cfg) is True

    def test_reclaim_requires_rank_at_t(self):
        # Rebond atteint à T mais rang < 0.90 → pas d'entrée.
        ranks = list(_RC_RANKS)
        ranks[6] = 0.85  # 06-11 : rang sous le seuil
        cfg = _mk_config(reclaim_ratio=0.95)
        assert evaluate_dip_filter("AAA", "2024-06-11", self._rh(ranks), self._ph(), cfg) is False

    def test_reclaim_max_wait_bounds_dip_age(self):
        # Récupération LENTE vers le prix pré-DIP : DIP unique à D4 (90 vs 100),
        # puis hausse graduelle non-DIP jusqu'à 100 en D9. ratio 1.0 → entrée
        # seulement si le DIP D4 est encore dans la fenêtre de scan.
        closes = [100.0, 99.0, 97.0, 94.0, 90.0, 97.5, 98.0, 98.5, 99.0, 100.0]
        ranks = [0.80, 0.95, 0.94, 0.92, 0.91, 0.90, 0.91, 0.92, 0.93, 0.91]
        rh, ph = self._rh(ranks), self._ph(closes)
        # max_wait=4 : DIP D4 (06-07) hors fenêtre à 06-14 → pas d'entrée.
        cfg4 = _mk_config(reclaim_ratio=1.0, reclaim_max_wait=4)
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, cfg4) is False
        # max_wait=6 : DIP D4 dans la fenêtre → entrée au retour au prix pré-DIP.
        cfg6 = _mk_config(reclaim_ratio=1.0, reclaim_max_wait=6)
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph, cfg6) is True


# ═══════════════════════════════════════════════════════════════════# evaluate_dip_filter — dip_pct SIGNÉ (anti-DIP si négatif)
# ═══════════════════════════════════════════════════════════════════════

class TestEvaluateDipFilterSigned:
    def test_dip_pct_negative_requires_rise(self):
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        rh = _mk_rank(dates, [0.95, 0.92, 0.91, 0.93])
        # dip_pct=-0.02 → exige une HAUSSE >= 2% (anti-DIP / breakout)
        cfg = _mk_config(dip_pct=-0.02)
        # +5% sur 4 séances → passe
        ph_up = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [100.0, 101.0, 102.0, 103.0, 105.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph_up, cfg) is True
        # +1% (< 2%) → ne passe pas
        ph_low = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [100.0, 100.5, 100.8, 101.0, 101.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph_low, cfg) is False
        # -2% (baisse) → ne passe pas (anti-DIP)
        ph_dn = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [100.0, 99.0, 98.5, 98.0, 98.0],
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph_dn, cfg) is False

    def test_dip_pct_positive_still_drop(self):
        # Régression : dip_pct > 0 conserve le DIP classique (baisse >= X).
        dates = ["2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"]
        rh = _mk_rank(dates, [0.95, 0.92, 0.91, 0.93])
        cfg = _mk_config(dip_pct=0.02)
        ph_dn = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [100.0, 99.0, 98.0, 97.0, 96.0],  # -4% → passe
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph_dn, cfg) is True
        ph_up = _mk_price(
            ["2024-06-10", "2024-06-11", "2024-06-12", "2024-06-13", "2024-06-14"],
            [100.0, 101.0, 102.0, 103.0, 104.0],  # +4% → ne passe PAS en DIP
        )
        assert evaluate_dip_filter("AAA", "2024-06-14", rh, ph_up, cfg) is False


# ═══════════════════════════════════════════════════════════════════════# filter_day_candidates — filtre réel (DB), skip si données absentes
# ═══════════════════════════════════════════════════════════════════

class TestFilterDayCandidates:
    def test_disabled_returns_unchanged(self):
        day = pd.DataFrame({"symbol": ["AAA", "BBB"], "global_rank_20": [0.95, 0.50]})
        cfg = _mk_config(enabled=False)
        out = filter_day_candidates(day, None, "batch-x", "2024-06-14", cfg)
        assert len(out) == 2

    def test_empty_input(self):
        day = pd.DataFrame()
        out = filter_day_candidates(day, None, "batch-x", "2024-06-14", _mk_config())
        assert out.empty

    def test_filters_when_db_available(self):
        # Skip si pas de DB réelle dispo (environnement de test).
        try:
            from database.connection import get_sqlalchemy_engine
            engine = get_sqlalchemy_engine()
            # probe rapide
            import pandas as pd
            n = pd.read_sql(
                "SELECT COUNT(*) c FROM global_rank_history WHERE batch_id='model-factory-20260811223551-ef2cd0' AND date='2024-06-14'",
                engine,
            ).iloc[0]["c"]
            if n == 0:
                pytest.skip("données batch absentes — skip")
        except Exception:
            pytest.skip("pas de DB — skip")

        from database.connection import get_sqlalchemy_engine
        engine = get_sqlalchemy_engine()
        day = pd.read_sql(
            "SELECT symbol, global_rank_20 FROM global_rank_history "
            "WHERE batch_id='model-factory-20260811223551-ef2cd0' AND date='2024-06-14'",
            engine,
        )
        cfg = _mk_config()
        out = filter_day_candidates(day.copy(), engine, "model-factory-20260811223551-ef2cd0", "2024-06-14", cfg)
        # Le DIP doit réduire le nombre de candidats (top10 > dip)
        assert len(out) <= len(day)
        assert set(out["symbol"]).issubset(set(day["symbol"]))
