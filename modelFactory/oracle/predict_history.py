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
  avec filtre batch strict. PK = ``(prediction_date, symbol, batch_id)`` : toute
  re-prédiction d'une même plage ÉCRASE les lignes existantes (pas de doublons).

Usage CLI (via walk_forward) :
    python -m modelFactory.oracle.walk_forward --batch-id <batch> \
        --predict-range 2020-01-01:2021-12-31
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

LOGGER = logging.getLogger(__name__)

_CHAMPIONS_ROOT = Path("artifacts/models/oracle/champions")
DEFAULT_PERSIST_CHUNK_DATES = 20


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
    symbols: list[str] | None = None,
    persist_chunk_dates: int = DEFAULT_PERSIST_CHUNK_DATES,
) -> dict[str, Any]:
    """Prédit ``proba_extreme`` sur [start_date, end_date] avec les champions, sans retrain.

    Écrit les prédictions dans ``oracle_extreme_predictions`` (filtre batch strict)
    par lots de dates. Chaque lot est transactionnel et immédiatement visible :
    un diagnostic concurrent peut donc suivre la progression et une interruption ne
    perd pas les lots déjà validés. L'upsert rend la reprise idempotente.
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
    _generator_options: dict[str, Any] = {}
    _profile_path = _champ_root / "feature_profile.json"
    if _profile_path.is_file():
        try:
            _profile = json.loads(_profile_path.read_text(encoding="utf-8"))
            _generator_options = {
                **dict(_profile.get("generator_options") or {}),
                "feature_set": str(_profile.get("feature_set", "expert")),
            }
        except Exception as _profile_exc:  # noqa: BLE001
            return {
                "status": "error", "reason": "invalid_oracle_feature_profile",
                "batch_id": batch_id, "detail": str(_profile_exc),
            }

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
        # Les anciens champions O0/O1 n'avaient pas de contrat de générateur
        # persisté. On conserve leur résolution tolérante historique ; les
        # nouveaux profils, eux, sont stricts et doivent être reproduits bit à bit.
        feature_whitelist=(_feature_columns or None) if _profile_path.is_file() else None,
        generator_options=_generator_options,
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
    # ``build_dataset`` charge une longue fenêtre de warm-up pour calculer les
    # indicateurs. Elle est utile au calcul mais ne doit pas rester dans la
    # matrice servie pendant toute la prédiction historique.
    _in_requested_range = (_date_col >= _start) & (_date_col <= _end)
    dataset = dataset.loc[_in_requested_range].copy()
    _date_col = pd.to_datetime(dataset["date"])
    _day_dates = sorted(_date_col.dropna().unique())

    # Import avant la boucle : chaque flush ouvre sa propre transaction courte.
    from modelFactory.oracle.predictions_store import write_oracle_predictions

    _chunk_dates = max(1, int(persist_chunk_dates or DEFAULT_PERSIST_CHUNK_DATES))
    _pending_rows: list[dict[str, Any]] = []
    _persisted_rows = 0
    _predicted_symbols: set[str] = set()

    def _flush_pending(*, processed_dates: int) -> None:
        nonlocal _persisted_rows
        if not _pending_rows:
            return
        _chunk = pd.DataFrame(_pending_rows)
        _written = write_oracle_predictions(engine, _chunk, batch_id=batch_id)
        _persisted_rows += int(_written)
        _pending_rows.clear()
        LOGGER.info(
            "oracle predict progress batch=%s dates=%d/%d rows_persisted=%d",
            batch_id, processed_dates, len(_day_dates), _persisted_rows,
        )

    for _date_index, _d in enumerate(_day_dates, start=1):
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
            _symbol = str(_sym).upper()
            _predicted_symbols.add(_symbol)
            _pending_rows.append({
                "date": _d_iso,
                "symbol": _symbol,
                "proba_extreme": float(_p),
                "future_return": _fr if pd.notna(_fr) else None,
                "oracle_extreme10": int(_lab) if pd.notna(_lab) else None,
                "fold_start": _t_sel,
            })

        if _date_index % _chunk_dates == 0:
            _flush_pending(processed_dates=_date_index)

    _flush_pending(processed_dates=len(_day_dates))

    if _persisted_rows <= 0:
        return {"status": "error", "reason": "no_predictions", "batch_id": batch_id}
    LOGGER.info(
        "predict_oracle_extreme_history batch=%s range=[%s,%s] rows=%d",
        batch_id, start_date, end_date, _persisted_rows,
    )
    return {
        "status": "completed",
        "batch_id": batch_id,
        "n_rows": _persisted_rows,
        "range": [str(start_date), str(end_date)],
        "n_dates": len(_day_dates),
        "n_symbols": len(_predicted_symbols),
        "n_folds_used": len(_t_starts),
        "persist_chunk_dates": _chunk_dates,
    }
