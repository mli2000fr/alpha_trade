"""Tests unitaires pour modelFactory/batch_diagnostics.py.

Couvre :
- Constantes (RANK_TYPE_*, EXCLUDE_*, PREFER_*)
- BatchFilters dataclass
- _load_config_defaults
- persist_batch_diagnostics (mock DB)
- _get_latest_completed_batch_id (mock DB)
- get_batch_filters (mock DB)
- filter_predictions (pure logique)
"""
from __future__ import annotations

import logging
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import text as sa_text

from modelFactory.batch_diagnostics import (
    EXCLUDE_LONG_RANK_TYPES,
    EXCLUDE_SHORT_RANK_TYPES,
    PREFER_RANK_TYPES,
    RANK_TYPE_BOTTOM,
    RANK_TYPE_TOP,
    RANK_TYPE_WEAK_LONG,
    RANK_TYPE_WEAK_SHORT,
    RANK_TYPE_ZERO_SHORT,
    BatchFilters,
    _get_latest_completed_batch_id,
    _load_config_defaults,
    filter_predictions,
    get_batch_filters,
    persist_batch_diagnostics,
)

LOGGER = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# Constantes
# ═══════════════════════════════════════════════════════════════════


class TestConstants:
    def test_rank_types_are_strings(self):
        for val in (
            RANK_TYPE_TOP, RANK_TYPE_BOTTOM, RANK_TYPE_ZERO_SHORT,
            RANK_TYPE_WEAK_LONG, RANK_TYPE_WEAK_SHORT,
        ):
            assert isinstance(val, str)
            assert val  # non vide

    def test_exclude_long_set(self):
        assert EXCLUDE_LONG_RANK_TYPES == frozenset({RANK_TYPE_BOTTOM, RANK_TYPE_WEAK_LONG})

    def test_exclude_short_set(self):
        assert EXCLUDE_SHORT_RANK_TYPES == frozenset(
            {RANK_TYPE_BOTTOM, RANK_TYPE_ZERO_SHORT, RANK_TYPE_WEAK_SHORT}
        )

    def test_prefer_set(self):
        assert PREFER_RANK_TYPES == frozenset({RANK_TYPE_TOP})

    def test_exclude_long_and_short_share_bottom(self):
        assert RANK_TYPE_BOTTOM in EXCLUDE_LONG_RANK_TYPES
        assert RANK_TYPE_BOTTOM in EXCLUDE_SHORT_RANK_TYPES

    def test_zero_short_only_in_exclude_short(self):
        assert RANK_TYPE_ZERO_SHORT not in EXCLUDE_LONG_RANK_TYPES
        assert RANK_TYPE_ZERO_SHORT in EXCLUDE_SHORT_RANK_TYPES

    def test_top_not_in_any_exclude(self):
        assert RANK_TYPE_TOP not in EXCLUDE_LONG_RANK_TYPES
        assert RANK_TYPE_TOP not in EXCLUDE_SHORT_RANK_TYPES


# ═══════════════════════════════════════════════════════════════════
# BatchFilters dataclass
# ═══════════════════════════════════════════════════════════════════


class TestBatchFilters:
    def test_construction_defaults(self):
        bf = BatchFilters(
            batch_id="b1",
            batch_started_at=None,
            prefer=frozenset(),
            exclude_long=frozenset(),
            exclude_short=frozenset(),
            all_diagnostics=pd.DataFrame(),
        )
        assert bf.batch_id == "b1"
        assert bf.batch_started_at is None
        assert bf.prefer == frozenset()
        assert bf.exclude_long == frozenset()
        assert bf.exclude_short == frozenset()
        assert bf.all_diagnostics.empty

    def test_construction_with_data(self):
        now = datetime(2026, 7, 23, 12, 0)
        bf = BatchFilters(
            batch_id="batch-abc",
            batch_started_at=now,
            prefer=frozenset({"AAPL", "MSFT"}),
            exclude_long=frozenset({"TSLA"}),
            exclude_short=frozenset({"TSLA", "GME"}),
            all_diagnostics=pd.DataFrame({"symbol": ["AAPL", "MSFT", "TSLA"]}),
        )
        assert bf.batch_id == "batch-abc"
        assert bf.batch_started_at == now
        assert bf.prefer == frozenset({"AAPL", "MSFT"})
        assert bf.exclude_long == frozenset({"TSLA"})
        assert bf.exclude_short == frozenset({"TSLA", "GME"})

    def test_is_frozen(self):
        bf = BatchFilters(
            batch_id="b1", batch_started_at=None,
            prefer=frozenset({"AAPL"}),
            exclude_long=frozenset(),
            exclude_short=frozenset(),
            all_diagnostics=pd.DataFrame(),
        )
        with pytest.raises(Exception):
            bf.batch_id = "b2"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════
# _load_config_defaults
# ═══════════════════════════════════════════════════════════════════


class TestLoadConfigDefaults:
    def test_returns_dict_with_defaults(self):
        cfg = _load_config_defaults()
        assert isinstance(cfg, dict)

    def test_missing_file_returns_empty_dict(self, monkeypatch):
        import builtins
        monkeypatch.setattr(builtins, "open", MagicMock(side_effect=FileNotFoundError))
        cfg = _load_config_defaults()
        assert cfg == {}

    def test_missing_key_returns_empty_dict(self, monkeypatch, tmp_path):
        import yaml
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("other_key: 42", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        cfg = _load_config_defaults()
        # batch_diagnostics key is missing → returns {}
        assert cfg == {}

    def test_partial_config(self, monkeypatch, tmp_path):
        import yaml
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "batch_diagnostics:\n  top_n: 20\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        cfg = _load_config_defaults()
        assert cfg == {"top_n": 20}

    def test_full_config(self, monkeypatch, tmp_path):
        import yaml
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            """batch_diagnostics:
  top_n: 10
  bottom_n: 10
  weak_long_threshold: 0.2
  weak_short_threshold: 0.2
  prefer_top_n: 8
  prefer_sizing_multiplier: 1.5
""",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        cfg = _load_config_defaults()
        assert cfg["top_n"] == 10
        assert cfg["bottom_n"] == 10
        assert cfg["weak_long_threshold"] == 0.2
        assert cfg["weak_short_threshold"] == 0.2
        assert cfg["prefer_top_n"] == 8
        assert cfg["prefer_sizing_multiplier"] == 1.5


# ═══════════════════════════════════════════════════════════════════
# persist_batch_diagnostics
# ═══════════════════════════════════════════════════════════════════

_MOCK_WF_DF = pd.DataFrame({
    "symbol": ["SYM_A", "SYM_B", "SYM_C", "SYM_D", "SYM_E",
                "SYM_F", "SYM_G", "SYM_H", "SYM_I", "SYM_J",
                "SYM_K", "SYM_L"],
    "f1_macro_wf": [0.40, 0.39, 0.38, 0.37, 0.36,
                    0.35, 0.30, 0.25, 0.24, 0.23,
                    0.22, 0.21],
    "f1_long_wf":  [0.20, 0.10, 0.20, 0.20, 0.20,
                    0.20, 0.20, 0.20, 0.20, 0.20,
                    0.20, 0.20],
    "f1_short_wf": [0.20, 0.20, 0.00, 0.20, 0.20,
                    0.10, 0.20, 0.20, 0.20, 0.20,
                    0.20, 0.20],
    "f1_flat_wf":  [0.10] * 12,
})
_MOCK_STARTED_AT = datetime(2026, 7, 23, 10, 0, 0)


def _mock_engine_for_persist(monkeypatch, mock_wf_df=None, started_at=None):
    """Construit un mock engine pour persist_batch_diagnostics."""
    if mock_wf_df is None:
        mock_wf_df = _MOCK_WF_DF
    if started_at is None:
        started_at = _MOCK_STARTED_AT

    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
    engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    # Premier connect() → BATCH_STARTED_QUERY
    calls_connect: list = []

    def fake_connect():
        c = MagicMock()
        calls_connect.append(c)
        return c

    # engine.begin() pour le DELETE/INSERT
    begin_conn = MagicMock()
    engine.begin.return_value.__enter__ = MagicMock(return_value=begin_conn)
    engine.begin.return_value.__exit__ = MagicMock(return_value=False)

    # Injecter les retours SQL
    def _connect_side_effect():
        c = MagicMock()
        # Premier connect lit batch_started_at
        fake_row = MagicMock()
        fake_row.__getitem__ = lambda self, idx: started_at
        c.execute.return_value.fetchone.return_value = fake_row
        # read_sql_query retourne le DF via __enter__
        c.__enter__.return_value = c
        c.__exit__.return_value = False
        return c

    # On simplifie : un seul mock connect
    engine.connect.side_effect = _connect_side_effect

    # Pour que pd.read_sql_query fonctionne avec le mock engine.connect()
    monkeypatch.setattr(
        "modelFactory.batch_diagnostics.pd.read_sql_query",
        lambda query, conn, params: mock_wf_df.copy(),
    )

    # Mock du config.yaml
    monkeypatch.setattr(
        "modelFactory.batch_diagnostics._load_config_defaults",
        lambda: {"top_n": 3, "bottom_n": 3, "weak_long_threshold": 0.15, "weak_short_threshold": 0.15},
    )

    return engine, begin_conn


class TestPersistBatchDiagnostics:

    def test_returns_zero_on_empty_wf(self, monkeypatch):
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False
        conn.execute.return_value.fetchone.return_value = MagicMock()
        conn.execute.return_value.fetchone.return_value.__getitem__ = lambda self, i: _MOCK_STARTED_AT

        monkeypatch.setattr(
            "modelFactory.batch_diagnostics.pd.read_sql_query",
            lambda query, conn, params: pd.DataFrame(),
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {},
        )

        result = persist_batch_diagnostics(engine, "batch-empty")
        assert result == 0

    def test_returns_zero_on_query_exception(self, monkeypatch):
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False
        conn.execute.return_value.fetchone.return_value = MagicMock()
        conn.execute.return_value.fetchone.return_value.__getitem__ = lambda self, i: _MOCK_STARTED_AT

        monkeypatch.setattr(
            "modelFactory.batch_diagnostics.pd.read_sql_query",
            MagicMock(side_effect=RuntimeError("DB down")),
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {},
        )

        result = persist_batch_diagnostics(engine, "batch-err")
        assert result == 0

    def test_top_n_applied(self, monkeypatch):
        """Vérifie que seuls les top_n symboles sont marqués top."""
        engine, begin_conn = _mock_engine_for_persist(monkeypatch)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"top_n": 2, "bottom_n": 2, "weak_long_threshold": 0.15, "weak_short_threshold": 0.15},
        )

        rows_inserted: list = []

        def fake_execute(sql, params):
            if isinstance(params, list):
                rows_inserted.extend(params)
            return MagicMock()

        begin_conn.execute.side_effect = fake_execute

        result = persist_batch_diagnostics(engine, "batch-top2")
        assert result > 0

        top_rows = [r for r in rows_inserted if r["rank_type"] == RANK_TYPE_TOP]
        assert len(top_rows) == 2
        # Les 2 premiers dans le DF trié par f1_macro DESC
        assert {r["symbol"] for r in top_rows} == {"SYM_A", "SYM_B"}

    def test_bottom_n_applied(self, monkeypatch):
        """Vérifie que seuls les bottom_n symboles sont marqués bottom."""
        engine, begin_conn = _mock_engine_for_persist(monkeypatch)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"top_n": 2, "bottom_n": 2, "weak_long_threshold": 0.15, "weak_short_threshold": 0.15},
        )

        rows_inserted: list = []

        def fake_execute(sql, params):
            if isinstance(params, list):
                rows_inserted.extend(params)
            return MagicMock()

        begin_conn.execute.side_effect = fake_execute

        result = persist_batch_diagnostics(engine, "batch-bottom2")
        assert result > 0

        bottom_rows = [r for r in rows_inserted if r["rank_type"] == RANK_TYPE_BOTTOM]
        assert len(bottom_rows) == 2
        assert {r["symbol"] for r in bottom_rows} == {"SYM_K", "SYM_L"}

    def test_zero_short_detected(self, monkeypatch):
        """SYM_C a f1_short=0 → doit être marqué zero_short."""
        engine, begin_conn = _mock_engine_for_persist(monkeypatch)

        rows_inserted: list = []

        def fake_execute(sql, params):
            if isinstance(params, list):
                rows_inserted.extend(params)
            return MagicMock()

        begin_conn.execute.side_effect = fake_execute

        result = persist_batch_diagnostics(engine, "batch-zero")
        assert result > 0

        zero_short_rows = [r for r in rows_inserted if r["rank_type"] == RANK_TYPE_ZERO_SHORT]
        syms_zero = {r["symbol"] for r in zero_short_rows}
        assert "SYM_C" in syms_zero

        for r in zero_short_rows:
            assert r["rank_position"] is None
            assert r["threshold_used"] is None

    def test_weak_long_detected(self, monkeypatch):
        """SYM_B a f1_long=0.10 < 0.15 → weak_long."""
        engine, begin_conn = _mock_engine_for_persist(monkeypatch)

        rows_inserted: list = []

        def fake_execute(sql, params):
            if isinstance(params, list):
                rows_inserted.extend(params)
            return MagicMock()

        begin_conn.execute.side_effect = fake_execute

        result = persist_batch_diagnostics(engine, "batch-weak")
        assert result > 0

        weak_long_rows = [r for r in rows_inserted if r["rank_type"] == RANK_TYPE_WEAK_LONG]
        syms = {r["symbol"] for r in weak_long_rows}
        assert "SYM_B" in syms

        for r in weak_long_rows:
            assert r["threshold_used"] == 0.15

    def test_weak_short_detected(self, monkeypatch):
        """SYM_F a f1_short=0.10 < 0.15 → weak_short."""
        engine, begin_conn = _mock_engine_for_persist(monkeypatch)

        rows_inserted: list = []

        def fake_execute(sql, params):
            if isinstance(params, list):
                rows_inserted.extend(params)
            return MagicMock()

        begin_conn.execute.side_effect = fake_execute

        result = persist_batch_diagnostics(engine, "batch-weak-short")
        assert result > 0

        weak_short_rows = [r for r in rows_inserted if r["rank_type"] == RANK_TYPE_WEAK_SHORT]
        syms = {r["symbol"] for r in weak_short_rows}
        assert "SYM_F" in syms

    def test_idempotent_delete_before_insert(self, monkeypatch):
        """Vérifie que le DELETE est exécuté avant l'INSERT."""
        engine, begin_conn = _mock_engine_for_persist(monkeypatch)

        executed_queries: list[str] = []

        def fake_execute(sql, params):
            executed_queries.append(str(sql))
            return MagicMock()

        begin_conn.execute.side_effect = fake_execute

        persist_batch_diagnostics(engine, "batch-idem")

        # Le premier appel doit être DELETE
        assert any("DELETE" in q.upper() for q in executed_queries)
        assert any("INSERT" in q.upper() for q in executed_queries)
        # DELETE doit apparaître avant INSERT
        delete_idx = next(i for i, q in enumerate(executed_queries) if "DELETE" in q.upper())
        insert_idx = next(i for i, q in enumerate(executed_queries) if "INSERT" in q.upper())
        assert delete_idx < insert_idx

    def test_effective_top_n_capped_at_total(self, monkeypatch):
        """Si top_n > nb symboles, effective_top_n = nb symboles."""
        small_df = pd.DataFrame({
            "symbol": ["A", "B"],
            "f1_macro_wf": [0.5, 0.4],
            "f1_long_wf": [0.3, 0.3],
            "f1_short_wf": [0.3, 0.3],
            "f1_flat_wf": [0.1, 0.1],
        })
        engine, begin_conn = _mock_engine_for_persist(monkeypatch, mock_wf_df=small_df)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"top_n": 50, "bottom_n": 50, "weak_long_threshold": 0.15, "weak_short_threshold": 0.15},
        )

        rows_inserted: list = []

        def fake_execute(sql, params):
            if isinstance(params, list):
                rows_inserted.extend(params)
            return MagicMock()

        begin_conn.execute.side_effect = fake_execute

        result = persist_batch_diagnostics(engine, "batch-small")
        assert result > 0

        top_rows = [r for r in rows_inserted if r["rank_type"] == RANK_TYPE_TOP]
        # 2 symboles → top_n effectif = 2 même si config dit 50
        assert len(top_rows) == 2

    def test_fallback_started_at_when_query_fails(self, monkeypatch):
        """Si BATCH_STARTED_QUERY échoue, utilise datetime.now()."""
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False
        conn.execute.side_effect = RuntimeError("no table")  # échec de BATCH_STARTED_QUERY

        monkeypatch.setattr(
            "modelFactory.batch_diagnostics.pd.read_sql_query",
            lambda query, conn, params: _MOCK_WF_DF.copy(),
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"top_n": 2, "bottom_n": 2, "weak_long_threshold": 0.15, "weak_short_threshold": 0.15},
        )

        begin_conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = begin_conn
        engine.begin.return_value.__exit__.return_value = False

        rows_inserted: list = []

        def fake_execute(sql, params):
            if isinstance(params, list):
                rows_inserted.extend(params)
            return MagicMock()

        begin_conn.execute.side_effect = fake_execute

        result = persist_batch_diagnostics(engine, "batch-no-started-at")
        assert result > 0
        # batch_started_at doit être un datetime (fallback to utcnow)
        for r in rows_inserted:
            assert isinstance(r["batch_started_at"], datetime)


# ═══════════════════════════════════════════════════════════════════
# _get_latest_completed_batch_id
# ═══════════════════════════════════════════════════════════════════


class TestGetLatestCompletedBatchId:
    def test_returns_batch_id_when_found(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        fake_row = MagicMock()
        fake_row.__getitem__ = lambda self, idx: "batch-20260723-abc"
        conn.execute.return_value.fetchone.return_value = fake_row

        result = _get_latest_completed_batch_id(engine)
        assert result == "batch-20260723-abc"

    def test_returns_none_when_no_rows(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False
        conn.execute.return_value.fetchone.return_value = None

        result = _get_latest_completed_batch_id(engine)
        assert result is None

    def test_returns_none_on_exception(self):
        engine = MagicMock()
        engine.connect.side_effect = RuntimeError("DB down")

        result = _get_latest_completed_batch_id(engine)
        assert result is None

    def test_converts_batch_id_to_str(self):
        """S'assure que le batch_id est casté en str."""
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        fake_row = MagicMock()
        fake_row.__getitem__ = lambda self, idx: 12345  # un int, pas un str
        conn.execute.return_value.fetchone.return_value = fake_row

        result = _get_latest_completed_batch_id(engine)
        assert result == "12345"
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════
# get_batch_filters
# ═══════════════════════════════════════════════════════════════════

def _diag_df(symbols_rank_types: list[tuple[str, str, int | None]]):
    """Helper: construit un DataFrame simulé de model_batch_diagnostics."""
    rows = []
    for sym, rank_type, rank_pos in symbols_rank_types:
        rows.append({
            "symbol": sym,
            "rank_type": rank_type,
            "rank_position": rank_pos,
            "f1_macro_wf": 0.3,
            "f1_long_wf": 0.2,
            "f1_short_wf": 0.2,
            "f1_flat_wf": 0.1,
        })
    return pd.DataFrame(rows)


def _mock_engine_for_filters(monkeypatch, df, batch_started_at=None):
    """Construit un mock engine pour get_batch_filters."""
    if batch_started_at is None:
        batch_started_at = datetime(2026, 7, 23, 12, 0)

    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False

    # pd.read_sql_query retourne df
    monkeypatch.setattr(
        "modelFactory.batch_diagnostics.pd.read_sql_query",
        lambda query, conn, params: df.copy(),
    )

    # La deuxième requête (batch_started_at) retourne le datetime
    fake_row = MagicMock()
    fake_row.__getitem__ = lambda self, idx: batch_started_at
    conn.execute.return_value.fetchone.return_value = fake_row

    return engine


class TestGetBatchFilters:

    def test_empty_when_no_batch(self, monkeypatch):
        """Si _get_latest_completed_batch_id retourne None → BatchFilters vide."""
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: None,
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 10},
        )

        engine = MagicMock()
        result = get_batch_filters(engine)
        assert result.batch_id == ""
        assert result.prefer == frozenset()
        assert result.exclude_long == frozenset()
        assert result.exclude_short == frozenset()
        assert result.all_diagnostics.empty

    def test_prefer_set_built_correctly(self, monkeypatch):
        df = _diag_df([
            ("AAPL", RANK_TYPE_TOP, 1),
            ("MSFT", RANK_TYPE_TOP, 2),
            ("GOOG", RANK_TYPE_TOP, 3),
            ("TSLA", RANK_TYPE_BOTTOM, 1),
        ])
        engine = _mock_engine_for_filters(monkeypatch, df)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: "batch-1",
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 10},
        )

        result = get_batch_filters(engine)
        assert result.prefer == frozenset({"AAPL", "MSFT", "GOOG"})

    def test_prefer_top_n_respected(self, monkeypatch):
        """Seuls les top prefer_top_n symboles sont dans prefer."""
        df = _diag_df([
            ("A", RANK_TYPE_TOP, 1),
            ("B", RANK_TYPE_TOP, 2),
            ("C", RANK_TYPE_TOP, 3),
            ("D", RANK_TYPE_TOP, 4),
            ("E", RANK_TYPE_TOP, 5),
        ])
        engine = _mock_engine_for_filters(monkeypatch, df)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: "batch-1",
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 3},
        )

        result = get_batch_filters(engine)
        assert result.prefer == frozenset({"A", "B", "C"})

    def test_prefer_top_n_default_50(self, monkeypatch):
        """Sans config, prefer_top_n = 50."""
        df = _diag_df([
            ("A", RANK_TYPE_TOP, 1),
            ("B", RANK_TYPE_TOP, 2),
        ])
        engine = _mock_engine_for_filters(monkeypatch, df)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: "batch-1",
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {},  # pas de prefer_top_n
        )

        result = get_batch_filters(engine)
        # prefer_top_n=50 → les 2 symboles top sont inclus
        assert result.prefer == frozenset({"A", "B"})

    def test_exclude_long_built_correctly(self, monkeypatch):
        df = _diag_df([
            ("AAPL", RANK_TYPE_TOP, 1),
            ("TSLA", RANK_TYPE_BOTTOM, 1),
            ("GME", RANK_TYPE_WEAK_LONG, None),
            ("AMC", RANK_TYPE_WEAK_SHORT, None),
        ])
        engine = _mock_engine_for_filters(monkeypatch, df)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: "batch-1",
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 10},
        )

        result = get_batch_filters(engine)
        assert result.exclude_long == frozenset({"TSLA", "GME"})
        # AMC est weak_short → pas dans exclude_long
        assert "AMC" not in result.exclude_long

    def test_exclude_short_built_correctly(self, monkeypatch):
        df = _diag_df([
            ("AAPL", RANK_TYPE_TOP, 1),
            ("TSLA", RANK_TYPE_BOTTOM, 1),
            ("GME", RANK_TYPE_ZERO_SHORT, None),
            ("AMC", RANK_TYPE_WEAK_SHORT, None),
        ])
        engine = _mock_engine_for_filters(monkeypatch, df)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: "batch-1",
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 10},
        )

        result = get_batch_filters(engine)
        assert result.exclude_short == frozenset({"TSLA", "GME", "AMC"})
        # AAPL est top → pas dans exclude_short
        assert "AAPL" not in result.exclude_short

    def test_empty_df_returns_empty_filters(self, monkeypatch):
        engine = _mock_engine_for_filters(monkeypatch, pd.DataFrame())
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: "batch-empty",
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 10},
        )

        result = get_batch_filters(engine)
        assert result.batch_id == "batch-empty"
        assert result.prefer == frozenset()
        assert result.exclude_long == frozenset()
        assert result.exclude_short == frozenset()

    def test_exception_returns_empty(self, monkeypatch):
        """Si la query échoue, on retourne un BatchFilters vide."""
        engine = MagicMock()
        engine.connect.side_effect = RuntimeError("DB down")
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: "batch-err",
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 10},
        )

        result = get_batch_filters(engine)
        assert result.prefer == frozenset()
        assert result.exclude_long == frozenset()
        assert result.exclude_short == frozenset()

    def test_explicit_batch_id_used(self, monkeypatch):
        """Si batch_id est fourni explicitement, ne passe pas par _get_latest."""
        df = _diag_df([
            ("AAPL", RANK_TYPE_TOP, 1),
        ])
        engine = _mock_engine_for_filters(monkeypatch, df)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 10},
        )

        # batch_id explicite, sans passer par _get_latest
        result = get_batch_filters(engine, batch_id="explicit-batch")
        assert result.batch_id == "explicit-batch"
        assert result.prefer == frozenset({"AAPL"})

    def test_prefer_top_n_param_overrides_config(self, monkeypatch):
        """Le paramètre prefer_top_n écrase la config."""
        df = _diag_df([
            ("A", RANK_TYPE_TOP, 1),
            ("B", RANK_TYPE_TOP, 2),
            ("C", RANK_TYPE_TOP, 3),
        ])
        engine = _mock_engine_for_filters(monkeypatch, df)
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._get_latest_completed_batch_id",
            lambda engine: "batch-1",
        )
        monkeypatch.setattr(
            "modelFactory.batch_diagnostics._load_config_defaults",
            lambda: {"prefer_top_n": 10},  # config dit 10, mais paramètre dit 1
        )

        result = get_batch_filters(engine, prefer_top_n=1)
        assert result.prefer == frozenset({"A"})


# ═══════════════════════════════════════════════════════════════════
# filter_predictions
# ═══════════════════════════════════════════════════════════════════


def _basic_filters() -> BatchFilters:
    return BatchFilters(
        batch_id="b1",
        batch_started_at=None,
        prefer=frozenset({"AAPL", "MSFT"}),
        exclude_long=frozenset({"TSLA"}),
        exclude_short=frozenset({"GME", "TSLA"}),
        all_diagnostics=pd.DataFrame(),
    )


class TestFilterPredictions:

    def test_excludes_long_symbol(self):
        df = pd.DataFrame({
            "symbol": ["AAPL", "TSLA", "MSFT"],
            "predicted_side": ["long", "long", "short"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        # TSLA predicted long → exclu (dans exclude_long)
        assert "TSLA" not in result["symbol"].values
        assert len(result) == 2

    def test_excludes_short_symbol(self):
        df = pd.DataFrame({
            "symbol": ["AAPL", "GME", "MSFT"],
            "predicted_side": ["long", "short", "short"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        # GME predicted short → exclu (dans exclude_short)
        assert "GME" not in result["symbol"].values
        assert len(result) == 2

    def test_keeps_symbol_with_opposite_side(self):
        """TSLA est dans exclude_long et exclude_short. Un TSLA predicted short
        n'est PAS exclu par exclude_long (ne matche que si side=long)."""
        df = pd.DataFrame({
            "symbol": ["TSLA", "TSLA"],
            "predicted_side": ["short", "long"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        # TSLA short : pas exclu par exclude_long (qui ne cible que long)
        # TSLA long  : exclu par exclude_long
        # TSLA short : exclu par exclude_short (TSLA est aussi dans exclude_short)
        assert len(result) == 0  # les deux lignes TSLA sont exclues

    def test_keeps_symbol_not_in_any_list(self):
        df = pd.DataFrame({
            "symbol": ["GOOG", "AMZN"],
            "predicted_side": ["long", "short"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        assert len(result) == 2

    def test_empty_df_returns_empty(self):
        df = pd.DataFrame(columns=["symbol", "predicted_side"])
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        assert result.empty

    def test_missing_side_column_returns_unchanged(self):
        df = pd.DataFrame({"symbol": ["AAPL", "TSLA"]})
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        # Pas de colonne "predicted_side" → retour inchangé
        assert len(result) == 2

    def test_custom_side_and_symbol_columns(self):
        df = pd.DataFrame({
            "ticker": ["TSLA", "AAPL"],
            "side": ["long", "short"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters, side_column="side", symbol_column="ticker")
        # TSLA long → exclu
        assert len(result) == 1
        assert result.iloc[0]["ticker"] == "AAPL"

    def test_case_insensitive_side(self):
        df = pd.DataFrame({
            "symbol": ["TSLA"],
            "predicted_side": ["LONG"],  # uppercase
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        assert len(result) == 0  # exclu

    def test_case_insensitive_symbol(self):
        df = pd.DataFrame({
            "symbol": ["tsla"],  # lowercase
            "predicted_side": ["long"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        assert len(result) == 0  # exclu (comparaison .upper())

    def test_boost_prefer_sizing(self, monkeypatch):
        """Si boost_prefer_sizing=True, sizing_mult est multiplié."""
        df = pd.DataFrame({
            "symbol": ["AAPL", "TSLA", "MSFT"],
            "predicted_side": ["long", "short", "long"],
            "sizing_mult": [1.0, 1.0, 1.0],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters, boost_prefer_sizing=True, prefer_multiplier=1.5)
        # TSLA est exclu (exclude_short)
        assert len(result) == 2
        # AAPL et MSFT sont dans prefer → sizing_mult *= 1.5
        aapl_row = result[result["symbol"] == "AAPL"]
        msft_row = result[result["symbol"] == "MSFT"]
        assert aapl_row["sizing_mult"].values[0] == 1.5
        assert msft_row["sizing_mult"].values[0] == 1.5

    def test_boost_prefer_sizing_skips_non_prefer(self, monkeypatch):
        """Les symboles non-prefer ne sont pas boostés."""
        df = pd.DataFrame({
            "symbol": ["GOOG", "AAPL"],
            "predicted_side": ["long", "long"],
            "sizing_mult": [1.0, 1.0],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters, boost_prefer_sizing=True, prefer_multiplier=2.0)
        goog_row = result[result["symbol"] == "GOOG"]
        aapl_row = result[result["symbol"] == "AAPL"]
        assert goog_row["sizing_mult"].values[0] == 1.0  # non-prefer inchangé
        assert aapl_row["sizing_mult"].values[0] == 2.0  # prefer boosté

    def test_boost_prefer_no_sizing_mult_column(self):
        """Si sizing_mult n'existe pas, pas d'erreur."""
        df = pd.DataFrame({
            "symbol": ["AAPL", "TSLA"],
            "predicted_side": ["long", "short"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters, boost_prefer_sizing=True, prefer_multiplier=1.5)
        # TSLA short est exclu
        assert len(result) == 1

    def test_flat_side_not_affected(self):
        """Les prédictions 'flat' ne sont jamais filtrées."""
        df = pd.DataFrame({
            "symbol": ["TSLA", "GME"],
            "predicted_side": ["flat", "flat"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        # flat n'est ni long ni short → pas d'exclusion
        assert len(result) == 2

    def test_returns_new_copy_not_view(self):
        df = pd.DataFrame({
            "symbol": ["AAPL", "TSLA"],
            "predicted_side": ["long", "long"],
        })
        filters = _basic_filters()
        result = filter_predictions(df, filters)
        # Modifier le résultat ne doit pas affecter l'original
        result.iloc[0, result.columns.get_loc("symbol")] = "CHANGED"
        assert df.iloc[0]["symbol"] == "AAPL"
