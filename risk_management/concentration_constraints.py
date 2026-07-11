"""risk_management/concentration_constraints.py — Contraintes de concentration (Sprint Maître 11).

Ajoute les dimensions de concentration manquantes :
- Industrie, thème, pays, devise
- Gap single-name (poids max par symbole individuel)
- Herfindahl-Hirschman (HHI) portefeuille

Usage ::

    from risk_management.concentration_constraints import (
        ConcentrationChecker, ConcentrationConfig, ConcentrationResult,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── ConcentrationConfig ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConcentrationConfig:
    """Configuration des contraintes de concentration (Sprint Maître 11).

    Tous les poids sont en fraction de l'equity (0.10 = 10%).
    """

    # Single-name
    max_single_name_weight: float = 0.10
    max_single_name_gap_pct: float = 0.50  # Le 2e plus gros poids ≤ 50% du 1er

    # Sector
    max_sector_weight: float = 0.30

    # Industry (sous-secteur)
    max_industry_weight: float = 0.20

    # Theme
    max_theme_weight: float = 0.25

    # Country
    max_country_weight: float = 0.50
    max_single_country_concentration: int = 3  # Max 3 positions par pays

    # Currency
    max_currency_weight: float = 0.80
    max_non_usd_weight: float = 0.30  # Max exposition devises non-USD

    # HHI
    max_hhi: float = 0.20  # Herfindahl-Hirschman max (0.10 = modérément concentré, 0.20 = concentré)

    def __post_init__(self) -> None:
        for name in (
            "max_single_name_weight", "max_sector_weight", "max_industry_weight",
            "max_theme_weight", "max_country_weight", "max_currency_weight",
            "max_non_usd_weight", "max_hhi",
        ):
            val = getattr(self, name)
            if not (0 < val <= 1):
                raise ValueError(f"{name} doit être dans ]0, 1] : {val}")
        if not (0 < self.max_single_name_gap_pct <= 1):
            raise ValueError(f"max_single_name_gap_pct doit être dans ]0, 1] : {self.max_single_name_gap_pct}")


# ── ConcentrationResult ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConcentrationResult:
    """Résultat d'une vérification de concentration (Sprint Maître 11).

    Attributes
    ----------
    passed : bool
        True si toutes les contraintes sont satisfaites.
    violations : tuple[str, ...]
        Liste des violations détectées.
    hhi : float | None
        Indice Herfindahl-Hirschman calculé.
    single_name_gap_violation : str | None
        Symbole violant la contrainte de gap.
    worst_dimension : str | None
        Dimension la plus concentrée.
    worst_concentration_pct : float | None
        Pourcentage de concentration de la pire dimension.
    """

    passed: bool = True
    violations: tuple[str, ...] = ()
    hhi: float | None = None
    single_name_gap_violation: str | None = None
    worst_dimension: str | None = None
    worst_concentration_pct: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "violations": list(self.violations),
            "hhi": round(self.hhi, 6) if self.hhi is not None else None,
            "single_name_gap_violation": self.single_name_gap_violation,
            "worst_dimension": self.worst_dimension,
            "worst_concentration_pct": (
                round(self.worst_concentration_pct, 4)
                if self.worst_concentration_pct is not None
                else None
            ),
        }


# ── ConcentrationChecker ────────────────────────────────────────────────────


@dataclass
class ConcentrationChecker:
    """Vérifie les contraintes de concentration multi-dimensionnelles (Sprint Maître 11).

    Évalue :
    1. Single-name : poids max + gap entre 1er et 2e
    2. Secteur, industrie, thème : poids max par groupe
    3. Pays : poids max + nombre de positions
    4. Devise : poids max + exposition non-USD
    5. HHI : indice de concentration globale
    """

    config: ConcentrationConfig = field(default_factory=ConcentrationConfig)

    def check(
        self,
        weights: dict[str, float],
        *,
        sectors: dict[str, str] | None = None,
        industries: dict[str, str] | None = None,
        themes: dict[str, str] | None = None,
        countries: dict[str, str] | None = None,
        currencies: dict[str, str] | None = None,
    ) -> ConcentrationResult:
        """Vérifie toutes les contraintes de concentration.

        Parameters
        ----------
        weights : dict[str, float]
            Poids par symbole (valeurs absolues, 0.05 = 5% de l'equity).
        sectors : dict[str, str] | None
            Mapping symbole → secteur.
        industries : dict[str, str] | None
            Mapping symbole → industrie.
        themes : dict[str, str] | None
            Mapping symbole → thème.
        countries : dict[str, str] | None
            Mapping symbole → pays.
        currencies : dict[str, str] | None
            Mapping symbole → devise.

        Returns
        -------
        ConcentrationResult
        """
        violations: list[str] = []
        cfg = self.config

        if not weights:
            return ConcentrationResult(passed=True, hhi=0.0)

        # ── 1. Single-name ──────────────────────────────────────────────
        sorted_weights = sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True)
        max_sym, max_w = sorted_weights[0]
        max_w_abs = abs(max_w)

        if max_w_abs > cfg.max_single_name_weight:
            violations.append(
                f"single_name:{max_sym}={max_w_abs:.2%} > max={cfg.max_single_name_weight:.0%}"
            )

        # Gap 1er vs 2e — seulement si le 1er est significatif (> min_weight)
        gap_violation = None
        min_weight_for_gap = 0.03  # 3% minimum pour déclencher le gap check
        if max_w_abs > min_weight_for_gap and len(sorted_weights) >= 2:
            second_w = abs(sorted_weights[1][1])
            if second_w > max_w_abs * cfg.max_single_name_gap_pct:
                gap_violation = sorted_weights[1][0]
                violations.append(
                    f"single_name_gap: {sorted_weights[1][0]}={second_w:.2%} > "
                    f"{cfg.max_single_name_gap_pct:.0%} × {max_sym}={max_w_abs:.2%}"
                )

        # ── 2. Sector ───────────────────────────────────────────────────
        worst_dim = "single_name"
        worst_conc = max_w_abs

        if sectors:
            sector_weights: dict[str, float] = {}
            for sym, w in weights.items():
                sec = sectors.get(sym, "UNKNOWN")
                sector_weights[sec] = sector_weights.get(sec, 0.0) + abs(w)
            max_sec, max_sec_w = max(sector_weights.items(), key=lambda x: x[1])
            if max_sec_w > cfg.max_sector_weight:
                violations.append(
                    f"sector:{max_sec}={max_sec_w:.2%} > max={cfg.max_sector_weight:.0%}"
                )
            if max_sec_w > worst_conc:
                worst_dim = f"sector:{max_sec}"
                worst_conc = max_sec_w

        # ── 3. Industry ─────────────────────────────────────────────────
        if industries:
            ind_weights: dict[str, float] = {}
            for sym, w in weights.items():
                ind = industries.get(sym, "UNKNOWN")
                ind_weights[ind] = ind_weights.get(ind, 0.0) + abs(w)
            max_ind, max_ind_w = max(ind_weights.items(), key=lambda x: x[1])
            if max_ind_w > cfg.max_industry_weight:
                violations.append(
                    f"industry:{max_ind}={max_ind_w:.2%} > max={cfg.max_industry_weight:.0%}"
                )
            if max_ind_w > worst_conc:
                worst_dim = f"industry:{max_ind}"
                worst_conc = max_ind_w

        # ── 4. Theme ────────────────────────────────────────────────────
        if themes:
            theme_weights: dict[str, float] = {}
            for sym, w in weights.items():
                thm = themes.get(sym, "UNKNOWN")
                theme_weights[thm] = theme_weights.get(thm, 0.0) + abs(w)
            max_thm, max_thm_w = max(theme_weights.items(), key=lambda x: x[1])
            if max_thm_w > cfg.max_theme_weight:
                violations.append(
                    f"theme:{max_thm}={max_thm_w:.2%} > max={cfg.max_theme_weight:.0%}"
                )
            if max_thm_w > worst_conc:
                worst_dim = f"theme:{max_thm}"
                worst_conc = max_thm_w

        # ── 5. Country ──────────────────────────────────────────────────
        if countries:
            country_weights: dict[str, float] = {}
            country_counts: dict[str, int] = {}
            for sym, w in weights.items():
                ctry = countries.get(sym, "UNKNOWN")
                country_weights[ctry] = country_weights.get(ctry, 0.0) + abs(w)
                country_counts[ctry] = country_counts.get(ctry, 0) + 1
            for ctry, cnt in country_counts.items():
                if cnt > cfg.max_single_country_concentration:
                    violations.append(
                        f"country:{ctry}={cnt} positions > max={cfg.max_single_country_concentration}"
                    )
            max_ctry, max_ctry_w = max(country_weights.items(), key=lambda x: x[1])
            if max_ctry_w > cfg.max_country_weight:
                violations.append(
                    f"country_weight:{max_ctry}={max_ctry_w:.2%} > max={cfg.max_country_weight:.0%}"
                )
            if max_ctry_w > worst_conc:
                worst_dim = f"country:{max_ctry}"
                worst_conc = max_ctry_w

        # ── 6. Currency ─────────────────────────────────────────────────
        non_usd_weight = 0.0
        if currencies:
            curr_weights: dict[str, float] = {}
            for sym, w in weights.items():
                curr = currencies.get(sym, "USD")
                curr_weights[curr] = curr_weights.get(curr, 0.0) + abs(w)
                if curr != "USD":
                    non_usd_weight += abs(w)
            max_curr, max_curr_w = max(curr_weights.items(), key=lambda x: x[1])
            if max_curr_w > cfg.max_currency_weight:
                violations.append(
                    f"currency:{max_curr}={max_curr_w:.2%} > max={cfg.max_currency_weight:.0%}"
                )
            if non_usd_weight > cfg.max_non_usd_weight:
                violations.append(
                    f"non_usd_exposure={non_usd_weight:.2%} > max={cfg.max_non_usd_weight:.0%}"
                )

        # ── 7. HHI ──────────────────────────────────────────────────────
        total_weight = sum(abs(w) for w in weights.values())
        hhi = 0.0
        if total_weight > 0:
            for w in weights.values():
                share = abs(w) / total_weight
                hhi += share ** 2
        if hhi > cfg.max_hhi:
            violations.append(f"HHI={hhi:.4f} > max={cfg.max_hhi}")

        return ConcentrationResult(
            passed=len(violations) == 0,
            violations=tuple(violations),
            hhi=hhi,
            single_name_gap_violation=gap_violation,
            worst_dimension=worst_dim,
            worst_concentration_pct=worst_conc,
        )


# ── Helpers ─────────────────────────────────────────────────────────────────


def check_concentration(
    weights: dict[str, float],
    sectors: dict[str, str] | None = None,
    industries: dict[str, str] | None = None,
    themes: dict[str, str] | None = None,
    countries: dict[str, str] | None = None,
    currencies: dict[str, str] | None = None,
) -> ConcentrationResult:
    """Fonction pure de vérification de concentration."""
    checker = ConcentrationChecker()
    return checker.check(
        weights,
        sectors=sectors,
        industries=industries,
        themes=themes,
        countries=countries,
        currencies=currencies,
    )


def compute_portfolio_hhi(weights: dict[str, float]) -> float:
    """Calcule l'indice Herfindahl-Hirschman du portefeuille.

    HHI = Σ (w_i / Σ|w|)²  — varie de 1/N (égal-répartition) à 1 (concentré).
    """
    if not weights:
        return 0.0
    total = sum(abs(w) for w in weights.values())
    if total <= 0:
        return 0.0
    return sum((abs(w) / total) ** 2 for w in weights.values())
