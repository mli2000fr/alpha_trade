"""modelFactory/oracle/leakage.py — Garde-fous anti-leakage (§27).

L'Oracle est un **TARGET**, jamais une **FEATURE**. Ces fonctions sont des
assertions **bloquantes** : toute violation lève une exception (le run échoue).

Tests couverts (spec §27) :
- T1 : ``oracle_available_date > prediction_date`` pour toutes les observations ;
- T2 : cutoff d'entraînement ≥ max(oracle_available_date) — câblé en S4 ;
- T3 : aucune feature issue de D+1 ou plus — garde structurelle en S0, durcie en S4 ;
- T4 : ``oracle_rank/decile/future_return/...`` jamais dans les features ;
- T5 : la prod ne lit jamais une ligne Oracle avec ``oracle_available_date > today``
  — câblé en S4.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

# Colonnes Oracle qui ne doivent JAMAIS apparaître dans les features (T4).
FORBIDDEN_ORACLE_FEATURES: frozenset[str] = frozenset({
    "oracle_rank",
    "oracle_decile",
    "oracle_pct_rank",
    "oracle_top10",
    "oracle_bottom10",
    "oracle_exit_date",
    "oracle_available_date",
    "future_return",
    "future_return_20",
    "future_volatility",
    "future_price",
    "future_volume",
})

# Préfixes/patterns indiquant une information future (T3, garde structurelle S0).
_FUTURE_PREFIXES = ("future_", "oracle_", "next_", "forward_")
_FUTURE_SUFFIXES = ("_fwd", "_t_plus", "_tplus", "_forward")


def assert_availability_after_prediction(
    df: pd.DataFrame,
    *,
    prediction_col: str = "prediction_date",
    exit_col: str = "oracle_exit_date",
    available_col: str = "oracle_available_date",
) -> None:
    """T1 — vérifie que le label Oracle n'est disponible qu'après sa prédiction.

    Lève ``ValueError`` si une ligne viole :
    ``oracle_available_date > prediction_date`` (et ``oracle_exit_date >= prediction_date``).
    """
    if df is None or df.empty:
        return

    missing = [c for c in (prediction_col, available_col) if c not in df.columns]
    if missing:
        raise ValueError(f"T1: colonnes requises absentes: {missing}")

    pred = pd.to_datetime(df[prediction_col], errors="coerce")
    avail = pd.to_datetime(df[available_col], errors="coerce")

    bad = df.loc[avail <= pred]
    if not bad.empty:
        raise ValueError(
            f"T1: {len(bad)} ligne(s) avec {available_col} <= {prediction_col} "
            "(le label n'est pas encore disponible)"
        )

    if exit_col in df.columns:
        exit_dt = pd.to_datetime(df[exit_col], errors="coerce")
        bad_exit = df.loc[exit_dt < pred]
        if not bad_exit.empty:
            raise ValueError(
                f"T1: {len(bad_exit)} ligne(s) avec {exit_col} < {prediction_col}"
            )


def assert_no_forbidden_features(feature_columns: Iterable[str]) -> None:
    """T4 — interdit les colonnes Oracle (labels/targets) dans les features."""
    cols = {str(c).strip() for c in feature_columns if str(c).strip()}
    forbidden = sorted(cols & FORBIDDEN_ORACLE_FEATURES)
    if forbidden:
        raise ValueError(f"T4: colonnes Oracle interdites en features: {forbidden}")


def assert_no_future_features(feature_columns: Iterable[str]) -> None:
    """T3 — garde structurelle contre les features issues de D+1 (S0).

    En S0, la vérification est **structurelle** (nommage). Le durcissement
    temporel (timestamp de chaque feature ≤ D) sera câblé en S4.
    """
    cols = {str(c).strip() for c in feature_columns if str(c).strip()}
    future_like = {
        c for c in cols
        if c.lower().startswith(_FUTURE_PREFIXES) or c.lower().endswith(_FUTURE_SUFFIXES)
    }
    if future_like:
        raise ValueError(
            f"T3: features potentiellement futures (D+1) détectées: {sorted(future_like)}"
        )


def assert_training_cutoff_valid(
    *,
    training_cutoff: Any,
    max_oracle_available_date: Any,
) -> None:
    """T2 — le cutoff d'entraînement doit couvrir toutes les labels utilisées.

    Vérifie ``max(oracle_available_date) <= training_cutoff`` : aucun fold
    d'entraînement ne peut « voir » une ligne Oracle dont l'horizon n'était pas
    encore réalisé au moment du cutoff.
    """
    if max_oracle_available_date is None:
        return
    cutoff = pd.Timestamp(training_cutoff)
    max_available = pd.Timestamp(max_oracle_available_date)
    if max_available > cutoff:
        raise ValueError(
            f"T2: leakage — max(oracle_available_date)={max_available.date()} "
            f"> training_cutoff={cutoff.date()}"
        )


def assert_no_future_oracle_read(*, today: Any, oracle_available_date: Any) -> None:
    """T5 — la prod ne lit jamais une ligne Oracle pas encore disponible.

    Vérifie ``oracle_available_date <= today`` : interdiction de consommer un
    label dont l'horizon n'est pas encore réalisé.
    """
    if oracle_available_date is None:
        return
    today_ts = pd.Timestamp(today)
    available_ts = pd.Timestamp(oracle_available_date)
    if available_ts > today_ts:
        raise ValueError(
            f"T5: lecture Oracle future — oracle_available_date={available_ts.date()} "
            f"> today={today_ts.date()}"
        )
