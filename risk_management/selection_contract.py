"""risk_management/selection_contract.py — Contrat ML → Risque (Sprint Maître 5).

Fige la frontière entre l'alpha ML et le moteur de risque.
Le ML est la SEULE autorité sur le side et le ranking nominal.
Le selector ne peut que poser des vetos, jamais changer side ou rank.

Types canoniques :
- ``MLRankedCandidate`` : DTO immutable produit par le pipeline ML.
- ``SelectorVetoContext`` : contexte de veto SANS autorité side/ranking.
- ``RiskDecisionInput`` : input complet pour le PortfolioBuilder.

Séquence nominale : ML → vetos → régime → portefeuille.

Usage ::

    from risk_management.selection_contract import (
        MLRankedCandidate, SelectorVetoContext, build_rankings,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace as _dc_replace
from datetime import date, datetime
from typing import Any

from core.ml_selection_contract import MLFirstSelectionContract


# ── MLRankedCandidate ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class MLRankedCandidate:
    """Candidat classé produit par le pipeline ML (Sprint Maître 5).

    C'est LE contrat entre ML et risque. Le side et le ranking sont
    déterminés UNIQUEMENT par le ML. Le risque peut rejeter ou réduire
    mais pas changer le side ni le rang.

    Attributes
    ----------
    symbol : str
    trade_date : date
        Date de trading (jour J de la décision).
    side : str
        ``"long"``, ``"short"`` ou ``"flat"``. Flat = pas de trade.
    p_long, p_flat, p_short : float
        Probabilités calibrées.
    p_side : float
        Probabilité de la classe retenue par la policy.
    side_rank : int | None
        Rang du candidat dans son side (1 = meilleur long, etc.).
    expected_edge : float | None
        Edge net estimé (rendement net attendu).
    model_run_id : str
        Identifiant du run modèle ayant produit cette prédiction.
    policy_version : int
        Version de la TernaryDecisionPolicy utilisée.
    universe_run_id : str | None
        Identifiant du run d'univers tradable.
    feature_cutoff : datetime | None
        Timestamp de disponibilité des features (doit être <= decision_cutoff).
    decision_cutoff : datetime | None
        Timestamp de la décision.
    lineage : dict | None
        Métadonnées additionnelles (config fingerprint, etc.).
    """

    symbol: str
    trade_date: date
    side: str  # "long", "short", "flat"
    p_long: float = 0.0
    p_flat: float = 0.0
    p_short: float = 0.0
    p_side: float = 0.0
    side_rank: int | None = None
    expected_edge: float | None = None
    model_run_id: str = ""
    policy_version: int = 1
    universe_run_id: str | None = None
    feature_cutoff: datetime | None = None
    decision_cutoff: datetime | None = None
    lineage: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol est obligatoire.")
        if self.side not in ("long", "short", "flat"):
            raise ValueError(f"side invalide : {self.side!r}")
        if not self.model_run_id.strip():
            raise ValueError("model_run_id est obligatoire.")
        if self.policy_version < 1:
            raise ValueError("policy_version doit être >= 1.")
        # Cohérence : side=long → p_side == p_long
        if self.side == "long" and abs(self.p_side - self.p_long) > 1e-6 and self.p_long > 0:
            raise ValueError(
                f"Incohérence side/p_side : side={self.side} p_side={self.p_side} p_long={self.p_long}"
            )
        if self.side == "short" and abs(self.p_side - self.p_short) > 1e-6 and self.p_short > 0:
            raise ValueError(
                f"Incohérence side/p_side : side={self.side} p_side={self.p_side} p_short={self.p_short}"
            )

    def is_actionable(self) -> bool:
        """Un candidat flat n'est jamais actionable."""
        return self.side in ("long", "short")

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "trade_date": self.trade_date.isoformat(),
            "side": self.side,
            "p_long": self.p_long,
            "p_flat": self.p_flat,
            "p_short": self.p_short,
            "p_side": self.p_side,
            "side_rank": self.side_rank,
            "expected_edge": self.expected_edge,
            "model_run_id": self.model_run_id,
            "policy_version": self.policy_version,
            "universe_run_id": self.universe_run_id,
            "feature_cutoff": self.feature_cutoff.isoformat() if self.feature_cutoff else None,
            "decision_cutoff": self.decision_cutoff.isoformat() if self.decision_cutoff else None,
        }


# ── SelectorVetoContext ─────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SelectorVetoContext:
    """Contexte de veto produit par le selector (Sprint Maître 5).

    Le selector N'A PAS l'autorité de changer le side ou le ranking.
    Il peut seulement fournir un contexte informatif et poser des vetos
    explicites avec raison documentée.

    Attributes
    ----------
    symbol : str
    sector : str | None
    quality_grade : str | None
        Note de qualité des données.
    earnings_blackout : bool
        True si le symbole est en période de blackout earnings.
    veto : bool
        True si le selector recommande un veto.
    veto_reason : str | None
        Raison codifiée du veto.
    score_available : float | None
        Score technique informatif (NE DÉTERMINE PAS le ranking).
    explanation : str | None
        Explication humaine du contexte.
    """

    symbol: str
    sector: str | None = None
    quality_grade: str | None = None
    earnings_blackout: bool = False
    veto: bool = False
    veto_reason: str | None = None
    score_available: float | None = None
    explanation: str | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol est obligatoire.")
        # Le selector ne doit PAS avoir de champ side ou rank
        # (vérifié par construction : pas de tels champs dans la dataclass)


# ── RiskDecisionInput ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class RiskDecisionInput:
    """Input complet pour le PortfolioBuilder (Sprint Maître 5).

    Combine le candidat ML, les vetos selector et le contexte régime.
    """

    candidate: MLRankedCandidate
    veto_context: SelectorVetoContext | None = None
    contract: MLFirstSelectionContract = field(
        default_factory=MLFirstSelectionContract,
    )

    @property
    def symbol(self) -> str:
        return self.candidate.symbol

    @property
    def side(self) -> str:
        return self.candidate.side

    @property
    def is_vetoed(self) -> bool:
        return self.veto_context is not None and self.veto_context.veto

    @property
    def veto_reason(self) -> str | None:
        if self.veto_context is None:
            return None
        return self.veto_context.veto_reason


# ── Helpers ─────────────────────────────────────────────────────────────────

def build_rankings(
    candidates: list[MLRankedCandidate],
) -> tuple[list[MLRankedCandidate], list[MLRankedCandidate]]:
    """Construit les deux rankings séparés long et short.

    Les candidats flat sont exclus. Le ranking est déterminé par
    ``p_side`` décroissant (le ML est la seule autorité).

    Parameters
    ----------
    candidates : list[MLRankedCandidate]

    Returns
    -------
    (long_ranked, short_ranked)
        Chaque liste est triée par p_side décroissant, avec side_rank peuplé.
    """
    longs = [c for c in candidates if c.side == "long"]
    shorts = [c for c in candidates if c.side == "short"]

    longs = sorted(longs, key=lambda c: c.p_side, reverse=True)
    shorts = sorted(shorts, key=lambda c: c.p_side, reverse=True)

    # Peupler side_rank (reconstruire car frozen+slots)
    longs = [_dc_replace(c, side_rank=i + 1) for i, c in enumerate(longs)]
    shorts = [_dc_replace(s, side_rank=i + 1) for i, s in enumerate(shorts)]

    return longs, shorts


def filter_actionable(candidates: list[MLRankedCandidate]) -> list[MLRankedCandidate]:
    """Filtre les candidats actionables (non-flat).

    Le flat n'atteint jamais le sizing — c'est un gate strict.
    """
    return [c for c in candidates if c.is_actionable()]


def validate_candidate_consistency(candidate: MLRankedCandidate) -> list[str]:
    """Valide la cohérence interne d'un candidat ML.

    Returns
    -------
    list[str]
        Liste des violations (vide = OK).
    """
    violations: list[str] = []
    if not candidate.symbol.strip():
        violations.append("empty_symbol")
    if candidate.side not in ("long", "short", "flat"):
        violations.append(f"invalid_side:{candidate.side}")
    if not candidate.model_run_id.strip():
        violations.append("missing_model_run_id")
    if candidate.policy_version < 1:
        violations.append("invalid_policy_version")

    # Probabilités finies
    for name, val in [("p_long", candidate.p_long), ("p_flat", candidate.p_flat), ("p_short", candidate.p_short)]:
        if not (0.0 <= val <= 1.0):
            violations.append(f"{name}_out_of_bounds:{val}")

    # Somme ≈ 1
    total = candidate.p_long + candidate.p_flat + candidate.p_short
    if abs(total - 1.0) > 1e-4:
        violations.append(f"prob_sum_not_one:{total:.6f}")

    # Cohérence side/p_side
    if candidate.side == "long" and abs(candidate.p_side - candidate.p_long) > 1e-4:
        violations.append(f"long_side_mismatch:p_side={candidate.p_side}_p_long={candidate.p_long}")
    if candidate.side == "short" and abs(candidate.p_side - candidate.p_short) > 1e-4:
        violations.append(f"short_side_mismatch:p_side={candidate.p_side}_p_short={candidate.p_short}")

    # Trade date obligatoire
    if candidate.trade_date is None:
        violations.append("missing_trade_date")

    return violations


def build_candidate_from_prediction(
    *,
    symbol: str,
    trade_date: date,
    predicted_side: str | None,
    proba_long: float | None,
    proba_flat: float | None,
    proba_short: float | None,
    proba: float,
    model_run_id: str,
    policy_version: int = 1,
    universe_run_id: str | None = None,
    feature_cutoff: datetime | None = None,
    decision_cutoff: datetime | None = None,
) -> MLRankedCandidate:
    """Construit un MLRankedCandidate depuis une prédiction (Sprint Maître 5).

    Parameters
    ----------
    symbol, trade_date, predicted_side, proba_long, proba_flat, proba_short,
    proba, model_run_id, policy_version, universe_run_id, feature_cutoff,
    decision_cutoff

    Returns
    -------
    MLRankedCandidate
    """
    side = str(predicted_side or "flat").strip().lower()
    if side not in ("long", "short", "flat"):
        side = "flat"

    p_long_val = float(proba_long or 0.0)
    p_flat_val = float(proba_flat or 0.0)
    p_short_val = float(proba_short or 0.0)

    # Déterminer p_side
    if side == "long":
        p_side_val = p_long_val
    elif side == "short":
        p_side_val = p_short_val
    else:
        p_side_val = p_flat_val

    return MLRankedCandidate(
        symbol=symbol.strip().upper(),
        trade_date=trade_date,
        side=side,
        p_long=p_long_val,
        p_flat=p_flat_val,
        p_short=p_short_val,
        p_side=p_side_val,
        model_run_id=str(model_run_id or ""),
        policy_version=policy_version,
        universe_run_id=universe_run_id,
        feature_cutoff=feature_cutoff,
        decision_cutoff=decision_cutoff,
    )
