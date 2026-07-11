"""risk_management/abstention.py — Politique d'abstention (Sprint Maître 8).

Décide si on tire (GO/NO-GO) sur un trade candidat avant sizing.
Les critères sont empilables : un seul NO-GO suffit à rejeter.

Gates empilables (tous optionnels, activables via config) :

1. **Qualité / data_availability** — PIT trop vieux/stale
2. **Confiance ML** — p_side < seuil
3. **Marge top-2** — p_side - p_second < seuil (ambiguïté)
4. **Incertitude** — edge uncertainty > seuil
5. **Edge minimum** — net_edge ≤ 0

Usage ::

    from risk_management.abstention import AbstentionPolicy, AbstentionDecision
    policy = AbstentionPolicy()
    decision = policy.evaluate(candidate, edge_estimate)
    if not decision.go:
        reject  # log decision.reason
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from risk_management.edge import DirectionalEdgeEstimate
from risk_management.selection_contract import MLRankedCandidate


# ── AbstentionDecision ──────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class AbstentionDecision:
    """Décision d'abstention (GO / NO-GO).

    Attributes
    ----------
    go : bool
        True si le trade passe toutes les gates.
    reason : str
        Raison du NO-GO (ou "all_gates_passed" si GO).
    gate_results : dict[str, bool]
        Résultat de chaque gate (nom → True=passé, False=échoué).
    """

    go: bool
    reason: str
    gate_results: dict[str, bool] = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        return not self.go


# ── AbstentionPolicy ────────────────────────────────────────────────────────

@dataclass
class AbstentionPolicy:
    """Politique d'abstention empilable (Sprint Maître 8).

    Parameters
    ----------
    min_p_side : float | None
        Seuil de confiance ML minimum. Si p_side < min_p_side → NO-GO.
    min_top2_margin : float | None
        Marge minimum entre p_side et le meilleur autre side.
        Si p_side - p_second < min_top2_margin → NO-GO (ambiguïté).
    max_uncertainty : float | None
        Incertitude maximum autorisée sur l'edge.
        Si edge.uncertainty > max_uncertainty → NO-GO.
    require_positive_edge : bool
        Si True, rejette si edge net ≤ 0.
    max_data_age_days : int | None
        Âge maximum des données PIT en jours.
        Si feature_cutoff est plus vieux que ce seuil → NO-GO.
    require_data_availability : bool
        Si True, vérifie que le candidate a bien feature_cutoff et decision_cutoff.
    """

    min_p_side: float | None = None
    min_top2_margin: float | None = None
    max_uncertainty: float | None = None
    require_positive_edge: bool = True
    max_data_age_days: int | None = None
    require_data_availability: bool = False

    def evaluate(
        self,
        candidate: MLRankedCandidate,
        edge: DirectionalEdgeEstimate | None = None,
        *,
        as_of_date: date | None = None,
    ) -> AbstentionDecision:
        """Évalue toutes les gates d'abstention.

        Parameters
        ----------
        candidate : MLRankedCandidate
        edge : DirectionalEdgeEstimate | None

        Returns
        -------
        AbstentionDecision
        """
        gate_results: dict[str, bool] = {}
        reasons: list[str] = []

        # ── Gate 1 : Data availability ─────────────────────────────────
        if self.require_data_availability:
            if candidate.feature_cutoff is None:
                gate_results["data_availability"] = False
                reasons.append("feature_cutoff manquant")
            elif candidate.decision_cutoff is None:
                gate_results["data_availability"] = False
                reasons.append("decision_cutoff manquant")
            else:
                gate_results["data_availability"] = True

        # ── Gate 2 : Data staleness ────────────────────────────────────
        if self.max_data_age_days is not None and candidate.feature_cutoff is not None:
            fc_date = (
                candidate.feature_cutoff.date()
                if isinstance(candidate.feature_cutoff, datetime)
                else candidate.feature_cutoff
            )
            if as_of_date is None:
                gate_results["data_freshness"] = False
                reasons.append("date as-of manquante pour la fraîcheur des données")
            else:
                age = (as_of_date - fc_date).days
                if age > self.max_data_age_days:
                    gate_results["data_freshness"] = False
                    reasons.append(f"données trop anciennes ({age}j > {self.max_data_age_days}j)")
                else:
                    gate_results["data_freshness"] = True

        # ── Gate 3 : Confiance ML (p_side) ─────────────────────────────
        if self.min_p_side is not None:
            p = candidate.p_side
            if p < self.min_p_side:
                gate_results["p_side"] = False
                reasons.append(f"p_side={p:.4f} < seuil={self.min_p_side:.4f}")
            else:
                gate_results["p_side"] = True

        # ── Gate 4 : Marge top-2 ───────────────────────────────────────
        if self.min_top2_margin is not None:
            # p_second = deuxième meilleure proba parmi les trois classes
            probs = [candidate.p_long, candidate.p_flat, candidate.p_short]
            probs_sorted = sorted(probs, reverse=True)
            top2_margin = probs_sorted[0] - probs_sorted[1] if len(probs_sorted) >= 2 else 0.0
            if top2_margin < self.min_top2_margin:
                gate_results["top2_margin"] = False
                reasons.append(
                    f"marge top-2={top2_margin:.4f} < seuil={self.min_top2_margin:.4f}"
                )
            else:
                gate_results["top2_margin"] = True

        # ── Gate 5 : Incertitude edge ──────────────────────────────────
        if self.max_uncertainty is not None and edge is not None:
            if edge.uncertainty > self.max_uncertainty:
                gate_results["uncertainty"] = False
                reasons.append(
                    f"incertitude edge={edge.uncertainty:.4f} > seuil={self.max_uncertainty:.4f}"
                )
            else:
                gate_results["uncertainty"] = True

        # ── Gate 6 : Edge net positif ──────────────────────────────────
        if self.require_positive_edge:
            if edge is None:
                gate_results["positive_edge"] = False
                reasons.append("edge estimate manquant")
            elif edge.net_edge <= 0:
                gate_results["positive_edge"] = False
                reasons.append(f"net_edge={edge.net_edge:.6f} ≤ 0")
            else:
                gate_results["positive_edge"] = True

        # ── Synthèse ───────────────────────────────────────────────────
        if reasons:
            return AbstentionDecision(
                go=False,
                reason="; ".join(reasons),
                gate_results=gate_results,
            )
        return AbstentionDecision(
            go=True,
            reason="all_gates_passed",
            gate_results=gate_results,
        )

    @classmethod
    def sensible_defaults(cls) -> AbstentionPolicy:
        """Créé une politique d'abstention avec des seuils raisonnables.

        Ces seuils sont volontairement conservateurs :
        - p_side ≥ 0.45 (un peu mieux que le hasard 1/3)
        - marge top-2 ≥ 0.05 (pas d'ambiguïté)
        - incertitude max ≤ 0.20
        - edge net > 0 obligatoire
        """
        return cls(
            min_p_side=0.45,
            min_top2_margin=0.05,
            max_uncertainty=0.20,
            require_positive_edge=True,
        )

    @classmethod
    def permissive(cls) -> AbstentionPolicy:
        """Politique permissive — edge net > 0 uniquement."""
        return cls(require_positive_edge=True)

    @classmethod
    def strict(cls) -> AbstentionPolicy:
        """Politique stricte — toutes les gates activées avec seuils élevés."""
        return cls(
            min_p_side=0.50,
            min_top2_margin=0.10,
            max_uncertainty=0.10,
            require_positive_edge=True,
            max_data_age_days=1,
            require_data_availability=True,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────

def evaluate_abstention_veto(
    candidate: MLRankedCandidate,
    edge: DirectionalEdgeEstimate | None,
    *,
    min_p_side: float = 0.40,
    min_top2_margin: float = 0.03,
    max_uncertainty: float = 0.25,
    require_positive_edge: bool = True,
) -> AbstentionDecision:
    """Fonction d'évaluation rapide avec les paramètres donnés.

    Retourne une AbstentionDecision. Utilisable en veto dans un pipeline.
    """
    policy = AbstentionPolicy(
        min_p_side=min_p_side,
        min_top2_margin=min_top2_margin,
        max_uncertainty=max_uncertainty,
        require_positive_edge=require_positive_edge,
    )
    return policy.evaluate(candidate, edge)
