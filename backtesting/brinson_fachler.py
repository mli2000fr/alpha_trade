"""Phase C / S16.2 — Attribution Brinson-Fachler par secteur.

Décompose l'alpha total en trois effets :

* **Allocation** : (w_p - w_b) * (R_b_sector - R_b_total)
* **Sélection** : w_b * (R_p_sector - R_b_sector)
* **Interaction** : (w_p - w_b) * (R_p_sector - R_b_sector)

avec :
* w_p = poids portfolio dans le secteur,
* w_b = poids benchmark dans le secteur,
* R_p_sector = rendement portfolio dans le secteur,
* R_b_sector = rendement benchmark dans le secteur,
* R_b_total = rendement benchmark global.

Identité vérifiée : Σ (allocation + selection + interaction) = R_p - R_b.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SectorBucket:
    sector: str
    portfolio_weight: float
    benchmark_weight: float
    portfolio_return: float
    benchmark_return: float


@dataclass(frozen=True, slots=True)
class SectorAttribution:
    sector: str
    allocation: float
    selection: float
    interaction: float

    @property
    def total(self) -> float:
        return self.allocation + self.selection + self.interaction


@dataclass(frozen=True, slots=True)
class BrinsonFachlerResult:
    sectors: list[SectorAttribution]
    total_allocation: float
    total_selection: float
    total_interaction: float
    portfolio_return: float
    benchmark_return: float

    @property
    def total_active_return(self) -> float:
        return self.portfolio_return - self.benchmark_return


def compute_brinson_fachler(buckets: list[SectorBucket]) -> BrinsonFachlerResult:
    """Calcule la décomposition Brinson-Fachler.

    Précondition : la somme des ``portfolio_weight`` (resp.
    ``benchmark_weight``) doit valoir 1.0 ± 1e-6. Aucune normalisation
    automatique n'est faite (on lève ``ValueError``).
    """
    if not buckets:
        raise ValueError("Aucun secteur fourni.")

    total_pw = sum(b.portfolio_weight for b in buckets)
    total_bw = sum(b.benchmark_weight for b in buckets)
    if abs(total_pw - 1.0) > 1e-6:
        raise ValueError(f"portfolio_weight total = {total_pw}, attendu 1.0")
    if abs(total_bw - 1.0) > 1e-6:
        raise ValueError(f"benchmark_weight total = {total_bw}, attendu 1.0")

    benchmark_return = sum(b.benchmark_weight * b.benchmark_return for b in buckets)
    portfolio_return = sum(b.portfolio_weight * b.portfolio_return for b in buckets)

    attributions = []
    total_alloc = total_sel = total_inter = 0.0
    for b in buckets:
        wp_minus_wb = b.portfolio_weight - b.benchmark_weight
        rp_minus_rb = b.portfolio_return - b.benchmark_return
        rb_minus_rb_total = b.benchmark_return - benchmark_return

        allocation = wp_minus_wb * rb_minus_rb_total
        selection = b.benchmark_weight * rp_minus_rb
        interaction = wp_minus_wb * rp_minus_rb

        attributions.append(SectorAttribution(
            sector=b.sector,
            allocation=allocation,
            selection=selection,
            interaction=interaction,
        ))
        total_alloc += allocation
        total_sel += selection
        total_inter += interaction

    return BrinsonFachlerResult(
        sectors=attributions,
        total_allocation=total_alloc,
        total_selection=total_sel,
        total_interaction=total_inter,
        portfolio_return=portfolio_return,
        benchmark_return=benchmark_return,
    )

