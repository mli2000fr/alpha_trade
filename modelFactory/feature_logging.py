"""modelFactory/feature_logging.py — Logs d'audit des features (poids + valeurs).

Objectif : vérifier que toutes les features utilisées par le modèle sont bien
alimentées (pas de null / vide / inf) et tracer les poids (importances) de
chaque feature.

- ``log_feature_values``  : résumé compact des valeurs (une ligne PAR feature,
  pas une ligne par jour d'entraînement). Une seule passe suffit.
- ``log_feature_weights`` : importances (gain) de toutes les features, triées
  par importance décroissante.

Compatible LightGBM (sklearn wrapper / Booster), XGBoost et CatBoost.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)


def log_feature_values(df: pd.DataFrame, feature_columns: list[str], *, label: str) -> None:
    """Log un résumé compact des valeurs de chaque feature (une ligne par feature).

    Le résumé indique pour chaque feature : nombre de lignes renseignées, nombre
    de nulls, nombre d'inf, min/mean/max. Une feature non alimentée (colonne
    absente, 100 % null ou 100 % non-fini) est signalée par ⚠️.
    """
    try:
        rows = int(len(df))
        LOGGER.info("feature_values %s: rows=%d features=%d", label, rows, len(feature_columns))
        for col in feature_columns:
            if col not in df.columns:
                LOGGER.warning("feature_values %s: column %s MISSING (not fed)", label, col)
                continue
            s = df[col]
            n_null = int(s.isna().sum())
            n = int(len(s) - n_null)
            num = pd.to_numeric(s, errors="coerce")
            n_inf = int(np.isinf(num).sum()) if num.dtype.kind in "fc" else 0
            finite = num[np.isfinite(num)]
            if len(finite):
                mean = float(finite.mean())
                mn = float(finite.min())
                mx = float(finite.max())
            else:
                mean = mn = mx = float("nan")
            flag = "" if (n_null == 0 and n_inf == 0 and len(finite) > 0) else " ⚠️"
            LOGGER.info(
                "feature_values %s: %-40s n=%d null=%d inf=%d min=%.6g mean=%.6g max=%.6g%s",
                label, col, n, n_null, n_inf, mn, mean, mx, flag,
            )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("feature_values %s failed: %s", label, exc)


def log_feature_weights(model: Any, feature_columns: list[str], *, label: str) -> None:
    """Log les poids/importances de chaque feature, triés par importance décroissante."""
    try:
        importance = _extract_importance(model)
        if importance is None:
            LOGGER.warning("feature_weights %s: backend without importance API", label)
            return
        importance = np.asarray(importance, dtype=float).reshape(-1)
        n = min(len(importance), len(feature_columns))
        if n == 0:
            LOGGER.warning("feature_weights %s: no importance values", label)
            return
        pairs = sorted(
            zip(feature_columns[:n], importance[:n]),
            key=lambda t: float(t[1]),
            reverse=True,
        )
        total = float(np.sum(importance[:n])) or 1.0
        LOGGER.info(
            "feature_weights %s: n_features=%d sum=%g :: %s",
            label, n, total,
            ", ".join(f"{f}={g:.3g}" for f, g in pairs),
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("feature_weights %s failed: %s", label, exc)


def _extract_importance(model: Any) -> np.ndarray | None:
    """Extrait l'importance des features depuis les principaux backends.

    - LightGBM (sklearn wrapper → ``booster_.feature_importance``, ou Booster)
    - XGBoost (``feature_importances_`` ou ``get_booster().get_score``)
    - CatBoost (``get_feature_importance()``)
    """
    # LightGBM sklearn wrapper (LGBMRanker / LGBMClassifier / ...)
    booster = getattr(model, "booster_", None)
    if booster is not None and hasattr(booster, "feature_importance"):
        return booster.feature_importance(importance_type="gain")
    if hasattr(model, "feature_importance"):
        try:
            return model.feature_importance(importance_type="gain")
        except TypeError:
            return model.feature_importance()
    # XGBoost sklearn wrapper
    if hasattr(model, "feature_importances_"):
        return model.feature_importances_
    if hasattr(model, "get_booster"):
        _b = model.get_booster()
        if _b is not None and hasattr(_b, "get_score"):
            _score = _b.get_score(importance_type="gain")
            if isinstance(_score, dict) and _score:
                # Clés XGBoost = "f0", "f1", ... → reconstruire un vecteur dense
                _idx: dict[int, float] = {}
                for _k, _v in _score.items():
                    _m = re.match(r"^f(\d+)$", str(_k))
                    if _m:
                        _idx[int(_m.group(1))] = float(_v)
                if _idx:
                    return np.asarray(
                        [_idx.get(i, 0.0) for i in range(max(_idx) + 1)], dtype=float,
                    )
                return np.asarray(list(_score.values()), dtype=float)
    # CatBoost
    if hasattr(model, "get_feature_importance"):
        return model.get_feature_importance()
    return None
