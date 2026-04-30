"""Tests pour le cache LRU du predictor (Phase 4.2.d)."""
from __future__ import annotations

import pickle
import time
from pathlib import Path

import numpy as np

from modelFactory import predictor


class _FakeTabularModel:
    def __init__(self) -> None:
        self.calls = 0

    def predict_proba(self, X):
        self.calls += 1
        return np.array([[0.4, 0.6]])


def _write_pickle_model(path: Path, model: object) -> None:
    with open(path, "wb") as fh:
        pickle.dump(model, fh)


def test_load_tabular_model_cached_loads_each_path_once(tmp_path: Path) -> None:
    predictor.clear_model_cache()
    model_a = _FakeTabularModel()
    model_b = _FakeTabularModel()
    path_a = tmp_path / "a_model.pkl"
    path_b = tmp_path / "b_model.pkl"
    _write_pickle_model(path_a, model_a)
    _write_pickle_model(path_b, model_b)

    obj_a1 = predictor.load_tabular_model_cached(path_a, selected_model="lightgbm")
    obj_a2 = predictor.load_tabular_model_cached(path_a, selected_model="lightgbm")
    obj_b1 = predictor.load_tabular_model_cached(path_b, selected_model="lightgbm")

    # Même chemin → même instance (cache hit).
    assert obj_a1 is obj_a2
    # Chemin différent → autre instance.
    assert obj_b1 is not obj_a1


def test_cache_invalidates_on_mtime_change(tmp_path: Path) -> None:
    predictor.clear_model_cache()
    path = tmp_path / "model.pkl"
    _write_pickle_model(path, _FakeTabularModel())

    obj1 = predictor.load_tabular_model_cached(path, selected_model="lightgbm")

    # Avancer le mtime puis réécrire un nouveau modèle.
    time.sleep(0.01)
    new_mtime = path.stat().st_mtime + 5.0
    _write_pickle_model(path, _FakeTabularModel())
    import os
    os.utime(path, (new_mtime, new_mtime))

    obj2 = predictor.load_tabular_model_cached(path, selected_model="lightgbm")
    assert obj1 is not obj2  # mtime changé → nouvelle entrée cache


def test_clear_model_cache_drops_all_entries(tmp_path: Path) -> None:
    predictor.clear_model_cache()
    path = tmp_path / "m.pkl"
    _write_pickle_model(path, _FakeTabularModel())
    obj1 = predictor.load_tabular_model_cached(path, selected_model="lightgbm")
    predictor.clear_model_cache()
    obj2 = predictor.load_tabular_model_cached(path, selected_model="lightgbm")
    assert obj1 is not obj2

