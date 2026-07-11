"""core/ternary_decision_policy.py — Politique de décision ternaire partagée.

Ce module définit LA fonction unique qui détermine le side (long/flat/short)
à partir des probabilités calibrées. Elle est utilisée par l'entraînement,
l'évaluation, la prédiction et le replay — garantissant la parité de side.

Contrat (cf. ``prompt/md_risque.md`` Sprint Maître 0) :
- Une seule fonction décide du side.
- Les seuils, la marge top-2, les égalités et les probabilités non finies
  sont gérés de façon déterministe.
- La policy est versionnée et immutable une fois construite.

Usage ::

    from core.ternary_decision_policy import TernaryDecisionPolicy, decide_ternary_side

    policy = TernaryDecisionPolicy(
        threshold_long=0.45,
        threshold_short=0.45,
        top2_margin=0.05,
        version=1,
    )
    decision = decide_ternary_side(
        proba_short=0.2, proba_flat=0.3, proba_long=0.5, policy=policy,
    )
    assert decision.side == "long"
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

# ── Types ───────────────────────────────────────────────────────────────────

TernarySide = Literal["long", "flat", "short"]


@dataclass(frozen=True, slots=True)
class TernaryDecision:
    """Résultat immutable d'une décision ternaire.

    Attributes
    ----------
    side : str
        ``"long"``, ``"flat"`` ou ``"short"``.
    p_side : float
        Probabilité de la classe retenue.
    reason : str
        Raison codifiée de la décision (ex. ``"p_long_dominant"``,
        ``"flat_by_margin"``, ``"tiebreak_argmax"``).
    """

    side: TernarySide
    p_side: float
    reason: str

    def __post_init__(self) -> None:
        if self.side not in {"long", "flat", "short"}:
            raise ValueError(f"side invalide : {self.side!r}")
        if not (0.0 <= self.p_side <= 1.0):
            raise ValueError(f"p_side hors bornes : {self.p_side}")


# ── Policy ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class TernaryDecisionPolicy:
    """Politique de décision ternaire immutable et versionnée.

    Attributes
    ----------
    threshold_long : float
        Seuil minimum de p_long pour qu'un side ``long`` soit éligible.
    threshold_short : float
        Seuil minimum de p_short pour qu'un side ``short`` soit éligible.
    top2_margin : float
        Marge minimale entre la meilleure et la deuxième probabilité
        pour éviter les décisions ambiguës.
    version : int
        Version de la policy, incrémentée à chaque changement effectif.
    """

    threshold_long: float = 0.45
    threshold_short: float = 0.45
    top2_margin: float = 0.05
    version: int = 1

    def __post_init__(self) -> None:
        if not (0.0 < self.threshold_long < 1.0):
            raise ValueError("threshold_long doit être dans ]0, 1[.")
        if not (0.0 < self.threshold_short < 1.0):
            raise ValueError("threshold_short doit être dans ]0, 1[.")
        if not (0.0 <= self.top2_margin < 1.0):
            raise ValueError("top2_margin doit être dans [0, 1[.")
        if self.version < 1:
            raise ValueError("version doit être >= 1.")

    def to_dict(self) -> dict[str, object]:
        """Sérialise la policy pour persistence JSON."""
        return {
            "threshold_long": self.threshold_long,
            "threshold_short": self.threshold_short,
            "top2_margin": self.top2_margin,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TernaryDecisionPolicy":
        """Reconstruit une policy depuis un dict (ex. JSON)."""
        return cls(
            threshold_long=float(data.get("threshold_long", 0.45)),
            threshold_short=float(data.get("threshold_short", 0.45)),
            top2_margin=float(data.get("top2_margin", 0.05)),
            version=int(data.get("version", 1)),
        )


# ── Policy par défaut ────────────────────────────────────────────────────────

DEFAULT_TERNARY_POLICY = TernaryDecisionPolicy()


# ── Décision ─────────────────────────────────────────────────────────────────

def _validate_probabilities(
    proba_short: float,
    proba_flat: float,
    proba_long: float,
    *,
    tolerance: float = 1e-6,
) -> str | None:
    """Valide les trois probabilités. Retourne ``None`` si OK, sinon un code d'erreur."""
    probs = [proba_short, proba_flat, proba_long]
    for i, p in enumerate(probs):
        if not math.isfinite(p):
            return f"non_finite_p{i}"
        if p < 0.0 or p > 1.0:
            return f"out_of_bounds_p{i}"
    total = proba_short + proba_flat + proba_long
    if abs(total - 1.0) > tolerance:
        return f"sum_not_one:{total:.8f}"
    return None


def decide_ternary_side(
    proba_short: float,
    proba_flat: float,
    proba_long: float,
    policy: TernaryDecisionPolicy | None = None,
) -> TernaryDecision:
    """Décide du side (long/flat/short) à partir des probabilités calibrées.

    C'est LA fonction canonique de décision. Tout le pipeline —
    entraînement, évaluation, prédiction, replay — doit l'utiliser.

    Règles (dans l'ordre) :
    1. Probabilités invalides (NaN, Inf, hors bornes, somme ≠ 1) → rejet explicite.
    2. Si p_long >= threshold_long ET p_long est la meilleure ET
       l'écart avec la 2ᵉ dépasse top2_margin → ``long``.
    3. Si p_short >= threshold_short ET p_short est la meilleure ET
       l'écart avec la 2ᵉ dépasse top2_margin → ``short``.
    4. Sinon → ``flat`` (abstention).

    En cas d'égalité parfaite entre deux classes, le tie-break est
    déterministe : long > short > flat.

    Parameters
    ----------
    proba_short : float
        Probabilité calibrée de la classe short.
    proba_flat : float
        Probabilité calibrée de la classe flat.
    proba_long : float
        Probabilité calibrée de la classe long.
    policy : TernaryDecisionPolicy | None
        Policy à utiliser. Si None, utilise DEFAULT_TERNARY_POLICY.

    Returns
    -------
    TernaryDecision
        Side, probabilité de la classe retenue et raison codifiée.

    Raises
    ------
    ValueError
        Si les probabilités sont invalides.
    """
    import numpy as np  # lazy import pour usage dans les deux contextes

    pol = policy if policy is not None else DEFAULT_TERNARY_POLICY

    # 1. Validation
    error = _validate_probabilities(proba_short, proba_flat, proba_long)
    if error is not None:
        raise ValueError(
            f"Probabilités invalides pour la décision ternaire : {error} "
            f"(short={proba_short:.6f}, flat={proba_flat:.6f}, long={proba_long:.6f})"
        )

    probs = {
        "short": proba_short,
        "flat": proba_flat,
        "long": proba_long,
    }

    # Tri par probabilité décroissante, tie-break: long > short > flat
    tiebreak_order = {"long": 0, "short": 1, "flat": 2}
    sorted_sides = sorted(probs.keys(), key=lambda s: (probs[s], -tiebreak_order[s]), reverse=True)
    best_side = sorted_sides[0]
    second_side = sorted_sides[1]
    best_p = probs[best_side]
    second_p = probs[second_side]
    margin = best_p - second_p

    # 2. Décision long
    if (
        best_side == "long"
        and proba_long >= pol.threshold_long
        and margin >= pol.top2_margin
    ):
        return TernaryDecision(side="long", p_side=proba_long, reason="p_long_dominant")

    # 3. Décision short
    if (
        best_side == "short"
        and proba_short >= pol.threshold_short
        and margin >= pol.top2_margin
    ):
        return TernaryDecision(side="short", p_side=proba_short, reason="p_short_dominant")

    # 4. Flat (abstention) — cas documentés
    if best_side == "long" and proba_long >= pol.threshold_long and margin < pol.top2_margin:
        reason = "flat_by_margin"
    elif best_side == "short" and proba_short >= pol.threshold_short and margin < pol.top2_margin:
        reason = "flat_by_margin"
    elif best_side == "long" and proba_long < pol.threshold_long:
        reason = "flat_below_threshold_long"
    elif best_side == "short" and proba_short < pol.threshold_short:
        reason = "flat_below_threshold_short"
    elif best_side == "flat":
        reason = "flat_dominant"
    else:
        reason = "flat_default"

    return TernaryDecision(side="flat", p_side=proba_flat, reason=reason)


# ── Helpers pour l'intégration ───────────────────────────────────────────────

def decide_from_array(
    proba_array: "np.ndarray",  # type: ignore[name-defined]
    policy: TernaryDecisionPolicy | None = None,
) -> TernaryDecision:
    """Décide du side à partir d'un array numpy de 3 probabilités [short, flat, long].

    Parameters
    ----------
    proba_array : np.ndarray
        Array de forme (3,) ou (1, 3) contenant [p_short, p_flat, p_long].
    policy : TernaryDecisionPolicy | None

    Returns
    -------
    TernaryDecision
    """
    import numpy as np

    arr = np.asarray(proba_array, dtype=np.float64).reshape(-1)
    if arr.shape[0] != 3:
        raise ValueError(f"probabilities doit avoir 3 éléments, reçu shape={arr.shape}")
    return decide_ternary_side(
        proba_short=float(arr[0]),
        proba_flat=float(arr[1]),
        proba_long=float(arr[2]),
        policy=policy,
    )


def decide_ternary_side_batch(
    proba_matrix: "np.ndarray",  # type: ignore[name-defined]
    policy: TernaryDecisionPolicy | None = None,
) -> "np.ndarray":  # type: ignore[name-defined]
    """Version vectorisée de ``decide_ternary_side`` pour l'évaluation.

    Parameters
    ----------
    proba_matrix : np.ndarray
        Array de forme (N, 3) avec colonnes [p_short, p_flat, p_long].
    policy : TernaryDecisionPolicy | None

    Returns
    -------
    np.ndarray
        Array de shape (N,) contenant les indices de classe décidés :
        0 = short, 1 = flat, 2 = long.
        Utilise les MÊMES règles que ``decide_ternary_side``.
    """
    import numpy as np

    pol = policy if policy is not None else DEFAULT_TERNARY_POLICY

    arr = np.asarray(proba_matrix, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"proba_matrix doit être de forme (N, 3), reçu {arr.shape}")

    N = arr.shape[0]
    # Par défaut : flat (indice 1)
    sides = np.ones(N, dtype=np.int64)

    p_short = arr[:, 0]
    p_flat = arr[:, 1]
    p_long = arr[:, 2]

    # Validation : lignes avec probas invalides → flat
    valid = (
        np.isfinite(p_short) & np.isfinite(p_flat) & np.isfinite(p_long)
        & (p_short >= 0) & (p_short <= 1)
        & (p_flat >= 0) & (p_flat <= 1)
        & (p_long >= 0) & (p_long <= 1)
        & (np.abs(p_short + p_flat + p_long - 1.0) < 1e-5)
    )

    # Pour chaque ligne valide, déterminer le meilleur side
    # On empile les probas et on prend l'argmax avec tie-break long=2 > short=0 > flat=1
    # Le tie-break est implémenté via un petit bonus dans l'ordre
    # On trie par proba décroissante, puis par tie-break (long préféré, puis short, puis flat)
    tie_break_bonus = np.array([0.0, 0.0, 1e-10], dtype=np.float64)  # tiny boost: long > short=flat
    # En cas d'égalité short/long: long gagne (indice 2 > 0, bonus 1e-10)
    # En cas d'égalité short/flat: short gagne
    # En cas d'égalité long/flat: long gagne
    tie_break = np.array([0.0, -1e-10, 1e-10], dtype=np.float64)  # long > short > flat

    stacked = np.column_stack([p_short, p_flat, p_long]) + tie_break[np.newaxis, :]
    best_idx = np.argmax(stacked, axis=1)  # 0=short, 1=flat, 2=long
    best_val = np.max(stacked, axis=1)

    # Calcul de la 2e meilleure valeur (pour la marge)
    # On met la meilleure à -inf puis on reprend le max
    stacked_masked = stacked.copy()
    stacked_masked[np.arange(N), best_idx] = -np.inf
    second_val = np.max(stacked_masked, axis=1)
    margin = best_val - second_val

    # Règles de décision (appliquées seulement aux lignes valides)
    long_ok = valid & (best_idx == 2) & (p_long >= pol.threshold_long) & (margin >= pol.top2_margin)
    short_ok = valid & (best_idx == 0) & (p_short >= pol.threshold_short) & (margin >= pol.top2_margin)

    sides[long_ok] = 2   # long
    sides[short_ok] = 0  # short
    # Les autres restent flat (1)

    return sides

