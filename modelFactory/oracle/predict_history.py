"""modelFactory/oracle/predict_history.py — Prédiction Oracle Extreme sur période arbitraire.

Même logique que ``predict_global_rank_history`` (Global Rank) : on charge les
CHAMPIONS déjà entraînés (persistés par le walk-forward) et on PRÉDIT SANS RETRAIN
sur n'importe quelle période, en écrivant dans ``oracle_extreme_predictions``.

- Champions : ``artifacts/models/oracle/champions/<batch_id>/oracle_champions.json``
  (liste de folds : ``t_start``, ``model_file``, ``feature_columns``) + fichiers
  ``.txt`` (LightGBM Booster).
- Pour chaque date D : on utilise le champion du fold avec le plus grand
  ``t_start <= D`` (PIT au niveau fold). Si D < premier ``t_start``, on utilise le
  premier fold (entraîné sur données < premier t_start → PIT pour D antérieur).
- La table ``oracle_extreme_predictions`` est REMPLIE ICI (pas à l'entraînement),
  avec ``run_id = oracle-pred-<timestamp>`` et filtre batch strict.

Usage CLI (via walk_forward) :
    python -m modelFactory.oracle.walk_forward --batch-id <batch> \
        --predict-range 2020-01-01:2021-12-31
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

LOGGER = logging.getLogger(__name__)

_CHAMPIONS_ROOT = Path("artifacts/models/oracle/champions")


def has_oracle_champions(batch_id: str | None) -> bool:
    """True si le batch a des champions Oracle persistés (predict standard possible)."""
    if not batch_id:
        return False
    return (_CHAMPIONS_ROOT / str(batch_id) / "oracle_champions.json").exists()


def _load_champions_meta(batch_id: str) -> list[dict[str, Any]]:
    """Charge la metadata des champions persistés pour un batch."""
    champ_root = _CHAMPIONS_ROOT / str(batch_id)
    meta_path = champ_root / "oracle_champions.json"
    if not meta_path.exists():
        return []
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("oracle champions meta unreadable: %s", exc)
        return []
    meta = [m for m in meta if m.get("t_start") and m.get("model_file")]
    return sorted(meta, key=lambda m: str(m["t_start"]))


def predict_oracle_extreme_history(
    engine: Any,
    batch_id: str,
    start_date: str,
    end_date: str,
    *,
    horizon: int = 20,
    run_id: str | None = None,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Prédit ``proba_extreme`` sur [start_date, end_date] avec les champions, sans retrain.

    Écrit les prédictions dans ``oracle_extreme_predictions`` (filtre batch strict).
    """
    if not (batch_id or "").strip():
        return {"status": "error", "reason": "no_batch_id"}
    _champ_root = _CHAMPIONS_ROOT / str(batch_id)

    # 1. Champions persistés
    _meta = _load_champions_meta(batch_id)
    if not _meta:
        return {
            "status": "error",
            "reason": "no_champions",
            "batch_id": batch_id,
            "dir": str(_champ_root),
            "hint": "Lancer d'abord le walk-forward pour ce batch (persiste les champions).",
        }
    _feature_columns = list(_meta[0].get("feature_columns") or [])
    _t_starts = [str(m["t_start"]) for m in _meta]

    # 2. Dataset + univers
    from modelFactory.oracle.dataset import build_dataset
    from modelFactory.oracle.train import get_universe_symbols

    _syms = symbols or get_universe_symbols(engine, batch_id, horizon)
    # Si le champion O0 (oracle-only) n'utilise PAS global_rank_20, on ne le
    # fusionne pas (sinon dataset vide pour un batch sans global_rank_history).
    _needs_gr = "global_rank_20" in _feature_columns
    dataset, feature_columns = build_dataset(
        engine, batch_id, _syms,
        start_date=str(start_date), end_date=str(end_date), horizon=horizon,
        require_global_rank=_needs_gr,
        need_targets=False,  # prédiction : labels optionnels (NULL si non réalisés)
    )
    if dataset.empty:
        return {"status": "error", "reason": "empty_dataset", "batch_id": batch_id}
    if not _feature_columns:
        _feature_columns = [c for c in feature_columns if c in dataset.columns]
    _cols = [c for c in _feature_columns if c in dataset.columns]
    if not _cols:
        return {
            "status": "error", "reason": "no_feature_columns", "batch_id": batch_id,
            "available": [c for c in dataset.columns if c not in ("date", "symbol")][:10],
        }

    # 3. Charger les boosters (cache)
    import lightgbm as lgb

    _model_cache: dict[str, Any] = {}

    def _get_model(t_start: str):
        if t_start not in _model_cache:
            _file = next((m["model_file"] for m in _meta if str(m["t_start"]) == t_start), None)
            if not _file:
                return None
            _model_cache[t_start] = lgb.Booster(model_file=str(_champ_root / _file))
        return _model_cache[t_start]

    # 4. Prédire par date avec le champion PIT le plus récent (t_start <= D)
    _start = pd.Timestamp(start_date)
    _end = pd.Timestamp(end_date)
    _date_col = pd.to_datetime(dataset["date"])
    _day_dates = sorted(_date_col.dropna().unique())
    _day_dates = [d for d in _day_dates if _start <= d <= _end]

    _rows: list[dict[str, Any]] = []
    for _d in _day_dates:
        _d_iso = str(_d.date())
        _sel = [ts for ts in _t_starts if ts <= _d_iso]
        _t_sel = _sel[-1] if _sel else _t_starts[0]
        _model = _get_model(_t_sel)
        if _model is None:
            LOGGER.warning("oracle predict: champion introuvable pour %s", _t_sel)
            continue
        _mask = _date_col.dt.date == _d.date()
        _day = dataset.loc[_mask]
        if _day.empty:
            continue
        try:
            _proba = _model.predict(_day[_cols].astype(float))
        except Exception as _pred_exc:  # noqa: BLE001
            LOGGER.warning("oracle predict date=%s failed: %s", _d_iso, _pred_exc)
            continue
        for (_sym, _fr, _lab), _p in zip(
            _day[["symbol", "future_return", "oracle_extreme10"]].itertuples(index=False, name=None),
            _proba,
        ):
            _rows.append({
                "date": _d_iso,
                "symbol": str(_sym).upper(),
                "proba_extreme": float(_p),
                "future_return": _fr if pd.notna(_fr) else None,
                "oracle_extreme10": int(_lab) if pd.notna(_lab) else None,
                "fold_start": _t_sel,
            })

    if not _rows:
        return {"status": "error", "reason": "no_predictions", "batch_id": batch_id}

    _oos = pd.DataFrame(_rows)
    _pred_run = run_id or f"oracle-pred-{datetime.now():%Y%m%d%H%M%S}"

    # 5. Écrire dans la table (filtre batch strict, idempotent par run)
    from modelFactory.oracle.predictions_store import write_oracle_predictions

    _n = write_oracle_predictions(engine, _oos, run_id=_pred_run, batch_id=batch_id)
    LOGGER.info(
        "predict_oracle_extreme_history batch=%s range=[%s,%s] rows=%d run=%s",
        batch_id, start_date, end_date, _n, _pred_run,
    )
    return {
        "status": "completed",
        "batch_id": batch_id,
        "run_id": _pred_run,
        "n_rows": _n,
        "range": [str(start_date), str(end_date)],
        "n_dates": len(_day_dates),
        "n_symbols": int(_oos["symbol"].nunique()),
        "n_folds_used": len(_t_starts),
    }
