"""E23 — Adaptive Drawdown Breaker : logique PURE des politiques B0-B3.

Une seule variable expérimentale : le drawdown breaker. Tout le reste est GELÉ
(signaux B25, trailing C2, sizing, coûts, max_positions, levier).

Politiques (protocol E23, 2026-08-21) :
    B0 = PROD actuel / contrôle        : recovery 92% peak + cap 25%
    B1 = recovery depuis trough        : paliers 10/25/50/75/100% sur RecoveryRatio
    B2 = régime-aware (sans trough)    : ramp rapide BULL/REB, lent CORR/SLIDE
    B3 = combined (trough + régime)    : tableau asymétrique + hystérésis 3 séances
    B4 = regime rearm + equity confirm : le régime AUTORISE, le RR PLAFONNE
        (jamais 100% sur simple REBOUND) + RELAPSE anti-rechute (peak figé)

Régime SPY (réutilisé EXACTEMENT d'E21-v2, réévalué chaque jour — contrairement
au trailing qui est gelé à l'entrée) :
    BULL       : SPY > SMA200 AND SPY > SMA50
    REBOUND    : SPY <= SMA200 AND SPY > SMA50
    CORRECTION : SPY > SMA200 AND SPY <= SMA50
    SLIDE      : SPY <= SMA200 AND SPY <= SMA50

Le module est PURE (aucune I/O, aucune dépendance) pour être testable unitairement.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Seuil de déclenchement GELÉ à 15% (on teste le RECOVERY, pas le trip).
TRIP_DD_PCT = 0.15

# Régimes favorables (réarmement rapide) vs défavorables (protection forte).
FAVORABLE_REGIMES = {"BULL", "REBOUND"}
DEFENSIVE_REGIMES = {"CORRECTION", "SLIDE"}

# Hystérésis : il faut N séances favorables CONSÉCUTIVES pour AUGMENTER
# l'allocation (lent pour faire confiance, rapide pour protéger).
HYSTERESIS_FAVORABLE_DAYS = 3

# B4 — le régime AUTORISE le réarmement, le RecoveryRatio (RR) détermine
# JUSQU'OÙ on peut aller (plafond de sécurité, PAS une condition de départ).
B4_FLOOR = 0.10
B4_RR_25 = 0.25
B4_RR_50 = 0.50
# RELAPSE B4 : DD qui se détériore de 3 pts depuis le début du réarmement.
RELAPSE_DD_PTS = 0.03
# BULL confirmé (streak >= 3 séances) : B4 -> 50%, B4a -> 75% (le 100% reste
# conditionné au RR >= 50% ; seule différence B4/B4a).
B4_BULL_STREAK_ALLOC = 0.50
B4A_BULL_STREAK_ALLOC = 0.75


@dataclass
class BreakerEpisode:
    """État d'un épisode de drawdown (peak → trough → recovery)."""

    peak: float = 0.0            # equity peak avant le trip
    trough: float = 0.0          # min equity depuis le trip
    allocation: float = 1.0      # allocation courante (0..1)
    favorable_streak: int = 0    # séances favorables consécutives (hystérésis)
    tripped: bool = False
    rearm_start_dd: float | None = None  # B4 : DD au début du réarmement en cours
    relapse_day: bool = False            # B4 : relapse détectée ce jour (force 10%)


def recovery_ratio(episode: BreakerEpisode, equity: float) -> float:
    """Fraction de la perte récupérée : 0.0=au trough, 1.0=ancien peak.

    RR = (equity - trough) / (peak - trough). Clampé [0,1].
    """
    span = episode.peak - episode.trough
    if span <= 0:
        return 1.0
    return max(0.0, min(1.0, (equity - episode.trough) / span))


def _tiers_from_ratio(rr: float, tiers: list[tuple[float, float]]) -> float:
    """Applique des paliers [seuil, allocation] sur RecoveryRatio."""
    alloc = tiers[0][1]
    for threshold, level in tiers:
        if rr >= threshold:
            alloc = level
    return alloc


# Paliers B1 / B3 (RecoveryRatio → allocation).
B1_TIERS = [(0.0, 0.10), (0.25, 0.25), (0.50, 0.50), (0.75, 0.75), (0.90, 1.00)]

# Tableau asymétrique B3 : {seuil RR: (allocation favorable, allocation défensive)}.
B3_TIERS = [
    (0.00, (0.25, 0.10)),
    (0.25, (0.50, 0.25)),
    (0.50, (0.75, 0.50)),
    (0.75, (1.00, 0.75)),
    (0.90, (1.00, 1.00)),
]


def is_favorable(regime: str | None) -> bool:
    return str(regime).strip().upper() in FAVORABLE_REGIMES


def b0_allocation(episode: BreakerEpisode, equity: float, recovery_pct: float, degraded: float, ramp_max: float, favorable: bool, per_day: float = 0.025) -> float:
    """Politique PROD : recovery à 92% du peak + cap ramp-up 25% (B0).

    Reproduit EXACTEMENT la logique existante de ``DrawdownCircuitBreaker`` :
    allocation = degraded + streak * per_day, plafonnée à ramp_max (cap sur le
    TOTAL, pas sur le bonus). B0 doit être bit-à-bit identique au comportement
    PROD (c'est le contrôle).
    """
    if favorable and episode.favorable_streak > 0:
        ramp_bonus = float(episode.favorable_streak) * per_day
        return min(float(ramp_max), float(degraded) + ramp_bonus)
    return degraded


def b1_allocation(episode: BreakerEpisode, equity: float) -> float:
    """Politique B1 : recovery depuis le trough par paliers (pas de régime)."""
    rr = recovery_ratio(episode, equity)
    return _tiers_from_ratio(rr, B1_TIERS)


def b2_allocation(episode: BreakerEpisode, equity: float, favorable: bool) -> float:
    """Politique B2 : régime contrôle la VITESSE de ramp, mais exige une
    amélioration minimale de l'equity (pas de réarmement au régime seul)."""
    # Base : 25% en BULL/REBOUND, 10% en CORRECTION/SLIDE.
    base = 0.25 if favorable else 0.10
    # Exigence d'amélioration : il faut que l'equity dépasse le trough (RR > 0).
    rr = recovery_ratio(episode, equity)
    if rr <= 0.0:
        return base
    # Vitesse : +25 pts/séance valide en favorable, +10 pts en défensif.
    step = 0.25 if favorable else 0.10
    n_steps = episode.favorable_streak if favorable else episode.favorable_streak
    return min(1.0, base + float(max(0, n_steps)) * step)


def b3_allocation(episode: BreakerEpisode, equity: float, favorable: bool) -> float:
    """Politique B3 (principale) : trough-recovery + régime asymétrique + hystérésis.

    Tableau (RecoveryRatio → alloc favorable / défensive) :
        RR < 25%   : 25% / 10%
        RR 25-50%  : 50% / 25%
        RR 50-75%  : 75% / 50%
        RR 75-90%  : 100% / 75%
        RR >= 90%  : 100% / 100%
    """
    rr = recovery_ratio(episode, equity)
    alloc = 0.10
    for threshold, (fav_lvl, def_lvl) in B3_TIERS:
        if rr >= threshold:
            alloc = fav_lvl if favorable else def_lvl
    return alloc


def b4_allocation(
    episode: BreakerEpisode,
    equity: float,
    regime: str | None,
    *,
    bull_streak_level: float = B4_BULL_STREAK_ALLOC,
) -> float:
    """Politique B4 — regime rearm + equity confirmation (spec 2026-08-21).

    Le régime AUTORISE le réarmement, la récupération du portefeuille (RR)
    détermine JUSQU'OÙ on peut aller :

        SLIDE / CORRECTION                    -> max 10%
        REBOUND + favorable >= 3 séances      -> max 25%
        REBOUND + RR >= 25%                   -> max 50%
        BULL    + favorable >= 3 séances      -> max {bull_streak_level:.0%}
        BULL    + RR >= 25%                   -> max 75%
        BULL    + RR >= 50%                   -> max 100%

    Un simple flip SLIDE -> REBOUND ne peut plus ramener à 100% (le défaut 2022).
    RELAPSE : nouveau trough OU DD détérioré de >= 3 pts depuis le début du
    réarmement -> retour à 10% (détecté dans ``trip_or_recover`` via
    ``_b4_check_relapse``, consommé ici par ``relapse_day``).

    ``bull_streak_level`` = palier BULL confirmé (streak >= 3) : B4 -> 50%,
    B4a -> 75%. Le 100% reste TOUJOURS conditionné au RR >= 50%.
    """
    if episode.relapse_day:
        episode.relapse_day = False
        episode.rearm_start_dd = None
        return B4_FLOOR
    reg = str(regime).strip().upper() if regime is not None else ""
    rr = recovery_ratio(episode, equity)
    cap = B4_FLOOR
    if reg == "REBOUND":
        if episode.favorable_streak >= HYSTERESIS_FAVORABLE_DAYS:
            cap = max(cap, 0.25)
        if rr >= B4_RR_25:
            cap = max(cap, 0.50)
    elif reg == "BULL":
        if episode.favorable_streak >= HYSTERESIS_FAVORABLE_DAYS:
            cap = max(cap, bull_streak_level)
        if rr >= B4_RR_25:
            cap = max(cap, 0.75)
        if rr >= B4_RR_50:
            cap = max(cap, 1.00)
    # Début de réarmement : on mémorise le DD pour la détection de RELAPSE.
    if cap > B4_FLOOR and episode.rearm_start_dd is None:
        episode.rearm_start_dd = _dd_pct(episode, equity)
    elif cap <= B4_FLOOR:
        episode.rearm_start_dd = None
    return cap


def _dd_pct(episode: BreakerEpisode, equity: float) -> float:
    """Drawdown courant (fraction) par rapport au peak D'ÉPISODE (figé)."""
    if episode.peak <= 0:
        return 0.0
    return max(0.0, (episode.peak - equity) / episode.peak)


def _b4_check_relapse(episode: BreakerEpisode, equity: float, prev_trough: float) -> None:
    """RELAPSE B4 : nouveau trough OU DD détérioré de >= 3 pts depuis le début
    du réarmement -> allocation 10%, streak reset, rearm_start_dd reset.

    On NE crée PAS un nouvel épisode : le peak de référence reste celui de
    l'épisode original (pas de peak artificiellement plus bas).
    """
    if episode.rearm_start_dd is None:
        return
    new_trough = equity < prev_trough
    dd = _dd_pct(episode, equity)
    dd_worsened = (dd - episode.rearm_start_dd) >= RELAPSE_DD_PTS
    if new_trough or dd_worsened:
        episode.allocation = B4_FLOOR
        episode.favorable_streak = 0
        episode.rearm_start_dd = None
        episode.relapse_day = True


def allocate(policy: str, episode: BreakerEpisode, equity: float, *, regime: str | None = None, recovery_pct: float = 0.92, degraded: float = 0.06, ramp_max: float = 0.25) -> float:
    """Dispatch des 4 politiques. Retourne l'allocation cible dans [0,1]."""
    policy = str(policy).strip().lower()
    favorable = is_favorable(regime)
    if policy == "b0":
        return b0_allocation(episode, equity, recovery_pct, degraded, ramp_max, favorable)
    if policy == "b1":
        return b1_allocation(episode, equity)
    if policy == "b2":
        return b2_allocation(episode, equity, favorable)
    if policy == "b3":
        return b3_allocation(episode, equity, favorable)
    if policy == "b4":
        return b4_allocation(episode, equity, regime)
    if policy == "b4a":
        return b4_allocation(episode, equity, regime, bull_streak_level=B4A_BULL_STREAK_ALLOC)
    raise ValueError(f"politique breaker inconnue: {policy}")


def trip_or_recover(episode: BreakerEpisode, equity: float, peak_equity: float, *, policy: str, max_dd_pct: float = TRIP_DD_PCT, recovery_pct: float = 0.92) -> None:
    """Met à jour l'état trip/recovery d'un épisode selon la politique.

    - Trip : DD >= max_dd_pct (toujours 15%, GELÉ — on ne teste pas le seuil).
      Au moment du trip, on fige ``episode.peak`` = peak d'equity courant (HWM
      d'épisode) et on initialise ``episode.trough``.
    - Recovery (fin d'épisode) :
        B1/B3 : RR >= 90% ET allocation == 100% (high-water mark d'épisode clos ;
                on n'attend plus le retour à l'ancien sommet absolu)
        B2    : equity >= peak * recovery_pct (comme B0, mais ramp régime-aware)
    À l'entrée dans un trip, on fige peak et on initialise trough.
    """
    if not episode.tripped:
        dd = 0.0
        if peak_equity > 0:
            dd = (peak_equity - equity) / peak_equity
        if dd >= max_dd_pct:
            episode.tripped = True
            episode.peak = float(peak_equity)   # HWM figé au moment du trip
            episode.trough = float(min(peak_equity, equity))
        return
    # Déjà trippé : suivre le trough.
    prev_trough = episode.trough
    if equity < episode.trough:
        episode.trough = equity
    # B4/B4a — RELAPSE anti-rechute (avant le calcul d'allocation).
    if policy in ("b4", "b4a"):
        _b4_check_relapse(episode, equity, prev_trough)
    # Fin d'épisode.
    if policy in ("b1", "b3", "b4", "b4a"):
        rr = recovery_ratio(episode, equity)
        if rr >= 0.90 and episode.allocation >= 0.999:
            episode.tripped = False
            episode.allocation = 1.0
            episode.favorable_streak = 0
            episode.rearm_start_dd = None
            episode.relapse_day = False
    elif equity >= episode.peak * recovery_pct:
        episode.tripped = False
        episode.allocation = 1.0
        episode.favorable_streak = 0


def update_streak(episode: BreakerEpisode, favorable: bool) -> None:
    """Hystérésis : pour AUGMENTER il faut 3 séances favorables consécutives ;
    pour DIMINUER, effet immédiat (géré par allocate())."""
    if favorable:
        episode.favorable_streak = min(episode.favorable_streak + 1, HYSTERESIS_FAVORABLE_DAYS)
    else:
        episode.favorable_streak = 0
