"""Configuration centralisée du module de gestion de risque."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.ml_selection_contract import SelectionCapacity

if TYPE_CHECKING:
    from core.conviction import ConvictionWeights


@dataclass(frozen=True, slots=True)
class RiskConfig:
    """Paramètres de risque — immutable après construction."""

    account_equity: float = 100_000.0
    risk_per_trade_pct: float = 0.01
    atr_window: int = 20

    # ── V1 Multi-Horizon Risk (2026-08-09) ──
    # Stop = ATR × atr_stop_multiple[H]
    # TP   = min(ATR × tp_atr_multiple[H], price × tp_max_pct[H])
    # Ancien champ scalaire conservé pour rétrocompatibilité des presets non migrés.
    # Les nouvelles méthodes `atr_stop_multiple_for(h)` et `tp_params_for(h)`
    # doivent être utilisées dans tout le code.
    atr_stop_multiple: float = 2.0  # fallback scalaire (rétrocompatibilité)
    best_horizon: int = 10  # horizon cible pour sizing/TP ; 10 = défaut conservateur

    # Multiples ATR par horizon (stop loss)
    _atr_stop_multiple_map: dict[int, float] | None = None
    # Multiples ATR par horizon (take profit)
    _tp_atr_multiple_map: dict[int, float] | None = None
    # Plafond TP en % du prix par horizon
    _tp_max_pct_map: dict[int, float] | None = None

    max_positions: int = 20
    max_long_positions: int | None = None
    max_short_positions: int = 2
    max_position_weight: float = 0.10
    max_sector_weight: float = 0.30
    max_gross_exposure: float = 1.0
    min_position_notional: float = 500.0

    # ── P2-1 sizing live (2026-08-13) ──
    # "atr" = legacy (budget de risque ATR égal par position).
    # "rank_weighted" = facteurs d'allocation depuis `selection_rank`.
    # "conviction_weighted" = facteurs d'allocation depuis `conviction_score`.
    # "equal_weight" = base égale 1/max_positions (sans effet net sur l'ATR).
    sizing_mode: str = "atr"
    sector_multipliers_path: str | None = None
    sizing_min_weight_pct: float = 0.005
    sizing_max_weight_pct: float = 0.20

    max_portfolio_drawdown_pct: float = 0.15
    max_daily_loss_pct: float = 0.05
    # Circuit breaker drawdown — mode dégradé et pic roulant (parité backtest Phase C.5)
    # 0.0 = blocage total (comportement original) ; > 0 = mode dégradé (sizing réduit)
    degraded_entry_allocation_pct: float = 0.0
    rolling_peak_window_days: int = 0   # 0 = pic historique absolu (comportement original)
    # Seuil de recovery : une fois trippé en mode dégradé, le breaker ne se
    # désactive que si l'equity remonte à cette fraction du pic de référence.
    recovery_pct: float = 0.92
    # Ramp-up régimed : si le régime repasse en "normal" ET que l'equity
    # progresse, l'allocation dégradée est progressivement augmentée.
    regime_ramp_up_enabled: bool = False
    regime_ramp_up_pct_per_day: float = 0.025
    regime_ramp_up_max_pct: float = 0.40
    # Fenêtre glissante pour le « pic sur N jours » : le streak s'incrémente
    # dès que l'equity dépasse le max des N jours précédents (résilience aux
    # jours de stagnation).
    regime_ramp_up_peak_window_days: int = 5

    # Concentration / diversification (Priorité 4)
    concentration_max_trades_per_symbol: int = 5
    concentration_window_calendar_days: int = 180
    concentration_max_consecutive_losses: int = 3
    concentration_blacklist_duration_days: int = 90

    # Anti-faux-départs (Quick Win 1) — nombre de jours consécutifs de
    # présence dans le top-N avant qu'un candidat soit éligible.
    # 1 = confirmation immédiate (filtre désactivé).
    # Pour le live, peut être remonté à 3 avec persistence JSON.
    min_breakout_days: int = 1

    # Ancien alias long, conservé pour les presets non migrés.
    min_score_threshold: float = 0.0
    # Vetos post-prédiction: le score ne définit ni le scope ni le côté.
    min_score_veto_long: float = 0.0
    max_score_veto_short: float = 1.0
    min_proba_long: float = 0.0
    min_proba_short: float = 0.0

    # Force-close sur circuit breaker : liquide toutes les positions quand
    # le breaker trippe (max_drawdown_pct atteint).
    force_close_on_breaker: bool = False
    # Fraction des positions à liquider (0.0-1.0). 1.0 = tout, 0.5 = moitié.
    force_close_pct: float = 0.50

    # Sprint 2 — short selling (Option C : MomentumRotationState)
    short_selling_enabled: bool = False
    short_min_score: float = 0.30
    short_rotation_required: bool = True
    short_tp_pct: float = 0.08
    short_trailing_pct: float = 0.10
    short_time_stop_days: int = 20
    # Ancien alias short, conservé pour les presets non migrés.
    min_score_threshold_short: float = 0.0
    # Exclure les sélections sans modèle ML entraîné.
    filter_unmodeled_selections: bool = False
    # Si True, liquide les longs existants quand le régime passe en mode défensif
    # (capital_preservation). Libère le capital pour les shorts.
    close_longs_on_defensive_regime: bool = True
    # Si True, ne permet les shorts que si le benchmark (SPY) est sous sa SMA50.
    # Évite de shorter dans un marché qui rebondit (ex: V-shaped recovery).
    short_require_bearish_benchmark: bool = True

    target_annual_vol: float | None = None
    vol_target_lookback_days: int = 60

    dry_run: bool = False

    # ── V1 Multi-Horizon helpers ──
    def atr_stop_multiple_for(self, horizon: int | None = None) -> float:
        """Multiple ATR pour le stop loss, selon l'horizon.

        Si ``_atr_stop_multiple_map`` est défini et contient ``horizon``,
        utilise la valeur mappée. Sinon, utilise ``best_horizon``. Sinon,
        fallback sur ``atr_stop_multiple`` (rétrocompatibilité).
        """
        h = horizon if horizon is not None else self.best_horizon
        if self._atr_stop_multiple_map and h in self._atr_stop_multiple_map:
            return float(self._atr_stop_multiple_map[h])
        return float(self.atr_stop_multiple)

    def tp_params_for(self, horizon: int | None = None) -> tuple[float, float]:
        """Retourne (tp_atr_multiple, tp_max_pct) pour l'horizon donné.

        Utilisé pour calculer : TP = min(ATR × tp_atr_multiple, price × tp_max_pct)
        """
        h = horizon if horizon is not None else self.best_horizon
        tp_atr = 3.0   # fallback conservateur
        tp_max = 0.07  # 7%
        if self._tp_atr_multiple_map and h in self._tp_atr_multiple_map:
            tp_atr = float(self._tp_atr_multiple_map[h])
        if self._tp_max_pct_map and h in self._tp_max_pct_map:
            tp_max = float(self._tp_max_pct_map[h])
        return tp_atr, tp_max

    # --- Correlation filter V2 ---
    correlation_threshold: float = 0.80
    correlation_lookback_days: int = 60
    correlation_min_overlap: int = 40

    # --- Factor risk model (Priorité 3 — RisqueSectoriel.md) ---
    # Active le modèle de risque factoriel CWMS (Phases A-E).
    enable_factor_model: bool = False
    # Active le filtre de corrélation basé sur le modèle factoriel (Phase E).
    # Remplace le filtre Pearson quand activé.
    use_factor_correlation_filter: bool = False
    # Seuil de corrélation implicite max pour le filtre factoriel (Phase E).
    factor_correlation_threshold: float = 0.70
    # Beta moyen pondéré maximum du portefeuille (Phase D).
    max_portfolio_beta: float = 1.2
    # Part maximale du risque total venant d'un seul facteur (Phase D).
    max_factor_concentration_pct: float = 0.60
    # Nombre minimum de facteurs avec contribution > 10% (Phase D).
    min_factor_diversification: int = 2
    # Demi-vie EWMA pour l'estimation de la covariance factorielle (Phase B).
    factor_ewma_half_life: int = 60
    # Fenêtre de lookback pour l'estimation factorielle en jours (Phase B).
    factor_lookback_days: int = 252

    # --- Kelly sizing V2 ---
    enable_kelly_sizing: bool = False
    assumed_payoff_ratio: float = 1.5
    kelly_fraction_multiplier: float = 0.25
    # Plafond de sécurité absolu sur la fraction Kelly (P0 2026-06-25)
    max_kelly_fraction: float = 0.25
    min_effective_probability: float = 0.52
    default_win_rate: float = 0.55

    # --- Conviction score V2 ---
    # P1 (2026-06-25) : 70/30 au lieu de 40/60 — le ML est un filtre, pas le moteur
    score_weight: float = 0.70
    prediction_weight: float = 0.30
    prediction_confidence_weight: float = 0.60
    historical_win_rate_weight: float = 0.40

    # --- Market-aware regime (Axe B du plan ``prompt/parttern/plan.md``) ---
    # Multiplicateur de risque appliqué au sizing ATR (1.0 = nominal).
    risk_multiplier: float = 1.0
    # Si défini, remplace ``min_position_notional`` lors du contrôle de notional
    # (typiquement 155 USD pour rester compatible Alpaca + petit capital).
    enforce_min_notional: float | None = None
    # Plafond optionnel "max_positions" calculé dynamiquement à partir de
    # l'equity et/ou du régime (None => ``max_positions`` standard utilisé).
    effective_max_positions_override: int | None = None
    # Maximum 2 tickers par secteur (en complément de ``max_sector_weight``).
    max_tickers_per_sector: int | None = None
    allow_fractional_shares: bool = False

    # --- Liquidité dynamique (LiquiditeDynamique.md P1) ---
    # Position max en % de l'ADV 20j du ticker. None = contrainte désactivée.
    # Ex: 0.01 = une position ne peut pas dépasser 1% du volume quotidien.
    max_position_pct_of_adv: float | None = None

    # --- Market-neutral constraints (Sprint 5, 2026-07-05) ---
    # Active la contrainte de neutralité nette. Quand activé, le portefeuille
    # est rééquilibré pour maintenir l'exposition nette dans le corridor
    # [target - tolerance, target + tolerance]. Les positions du côté
    # surpondéré sont réduites proportionnellement.
    enforce_net_exposure: bool = False
    # Exposition nette cible en fraction de l'equity.
    # 0.0 = market-neutral parfait, 0.30 = biais long 30%.
    net_exposure_target: float = 0.0
    # Tolérance autour de la cible (±). Ex: target=0.0, tolerance=0.10
    # → net_exposure autorisée ∈ [-0.10, +0.10].
    net_exposure_tolerance: float = 0.10
    # Corrélation inter-jambes long/short max avant déclenchement d'une
    # réduction de levier. None = pas de contrainte.
    max_long_short_correlation: float | None = None

    def __post_init__(self) -> None:
        if self.account_equity <= 0:
            raise ValueError("account_equity doit être > 0.")
        if not 0 < self.risk_per_trade_pct < 1:
            raise ValueError("risk_per_trade_pct doit être dans ]0, 1[.")
        if self.atr_window < 1:
            raise ValueError("atr_window doit être >= 1.")
        if self.atr_stop_multiple <= 0:
            raise ValueError("atr_stop_multiple doit être > 0.")
        if self.target_annual_vol is not None and self.target_annual_vol <= 0:
            raise ValueError("target_annual_vol doit être > 0 quand renseigné.")
        if self.vol_target_lookback_days < 2:
            raise ValueError("vol_target_lookback_days doit être >= 2.")
        if self.max_positions < 1:
            raise ValueError("max_positions doit être >= 1.")
        resolved_max_long_positions = (
            self.max_positions
            if self.max_long_positions is None
            else self.max_long_positions
        )
        SelectionCapacity(
            max_positions=self.max_positions,
            max_long_positions=resolved_max_long_positions,
            max_short_positions=self.max_short_positions,
        )
        # --- V2 validations ---
        if not (0 < self.correlation_threshold <= 1):
            raise ValueError("correlation_threshold doit être dans ]0, 1].")
        if self.correlation_lookback_days < self.correlation_min_overlap:
            raise ValueError("correlation_lookback_days doit être >= correlation_min_overlap.")
        if self.correlation_min_overlap < 1:
            raise ValueError("correlation_min_overlap doit être >= 1.")
        if self.assumed_payoff_ratio <= 0:
            raise ValueError("assumed_payoff_ratio doit être > 0.")
        if not (0 < self.kelly_fraction_multiplier <= 1):
            raise ValueError("kelly_fraction_multiplier doit être dans ]0, 1].")
        if not (0 < self.max_kelly_fraction <= 1):
            raise ValueError("max_kelly_fraction doit être dans ]0, 1].")
        if not (0.5 <= self.min_effective_probability < 1):
            raise ValueError("min_effective_probability doit être dans [0.5, 1[.")
        if not (0.5 <= self.default_win_rate < 1):
            raise ValueError("default_win_rate doit être dans [0.5, 1[.")
        for field_name in (
            "min_score_veto_long", "max_score_veto_short", "min_proba_long", "min_proba_short",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} doit être dans [0, 1].")
        if abs((self.score_weight + self.prediction_weight) - 1.0) > 1e-6:
            raise ValueError("score_weight + prediction_weight doit == 1.0.")
        if abs((self.prediction_confidence_weight + self.historical_win_rate_weight) - 1.0) > 1e-6:
            raise ValueError("prediction_confidence_weight + historical_win_rate_weight doit == 1.0.")
        # --- Market-aware validations ---
        if self.risk_multiplier < 0:
            raise ValueError("risk_multiplier doit être >= 0.")
        if self.enforce_min_notional is not None and self.enforce_min_notional < 0:
            raise ValueError("enforce_min_notional doit être >= 0 quand renseigné.")
        if self.effective_max_positions_override is not None and self.effective_max_positions_override < 0:
            raise ValueError("effective_max_positions_override doit être >= 0 quand renseigné.")
        if self.max_tickers_per_sector is not None and self.max_tickers_per_sector < 1:
            raise ValueError("max_tickers_per_sector doit être >= 1 quand renseigné.")
        # --- Factor model validations (Priorité 3) ---
        if self.factor_correlation_threshold <= 0 or self.factor_correlation_threshold > 1:
            raise ValueError("factor_correlation_threshold doit être dans ]0, 1].")
        if self.max_portfolio_beta <= 0:
            raise ValueError("max_portfolio_beta doit être > 0.")
        if not (0 < self.max_factor_concentration_pct <= 1):
            raise ValueError("max_factor_concentration_pct doit être dans ]0, 1].")
        if self.min_factor_diversification < 1:
            raise ValueError("min_factor_diversification doit être >= 1.")
        if self.factor_ewma_half_life < 2:
            raise ValueError("factor_ewma_half_life doit être >= 2.")
        if self.factor_lookback_days < 20:
            raise ValueError("factor_lookback_days doit être >= 20.")
        # Sprint 5 — market-neutral
        if self.enforce_net_exposure:
            if self.net_exposure_target < -1.0 or self.net_exposure_target > 1.0:
                raise ValueError("net_exposure_target doit être dans [-1.0, 1.0].")
            if self.net_exposure_tolerance <= 0:
                raise ValueError("net_exposure_tolerance doit être > 0.")
            if self.max_long_short_correlation is not None and not (0 < self.max_long_short_correlation <= 1):
                raise ValueError("max_long_short_correlation doit être dans ]0, 1] quand renseigné.")

    @property
    def effective_min_notional(self) -> float:
        """Notional minimum effectif (``enforce_min_notional`` prioritaire)."""
        if self.enforce_min_notional is not None:
            return float(self.enforce_min_notional)
        return float(self.min_position_notional)

    @property
    def effective_max_positions(self) -> int:
        """Max positions effectif (``effective_max_positions_override`` prioritaire)."""
        if self.effective_max_positions_override is not None:
            return max(0, int(self.effective_max_positions_override))
        return int(self.max_positions)

    @property
    def selection_capacity(self) -> SelectionCapacity:
        """Contrat de capacité nominal partagé par les moteurs de sélection."""
        effective_total = self.effective_max_positions
        resolved_max_long_positions = (
            self.max_positions
            if self.max_long_positions is None
            else self.max_long_positions
        )
        return SelectionCapacity(
            max_positions=effective_total,
            max_long_positions=min(resolved_max_long_positions, effective_total),
            max_short_positions=min(self.max_short_positions, effective_total),
        )

    def to_conviction_weights(self) -> ConvictionWeights:
        """Phase 5.1.b — Adapte les pondérations risk vers ``core.conviction.ConvictionWeights``.

        Centralise la fusion conviction (cf. `prompt/refactor/plan_phase5.md` §5.1.b).
        """
        from core.conviction import ConvictionWeights

        return ConvictionWeights(
            score_weight=self.score_weight,
            prediction_weight=self.prediction_weight,
        )

    # ── Sprint Maître 6 : fingerprint et sérialisation ──────────────────

    @property
    def fingerprint(self) -> str:
        """SHA256/16 du contenu effectif de la configuration.

        Deux configs avec le même fingerprint sont garanties identiques
        pour tous les champs influençant les décisions de risque.
        """
        import hashlib
        import json

        payload = self.to_dict(exclude_defaults=False)
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def to_dict(self, *, exclude_defaults: bool = True) -> dict[str, object]:
        """Sérialise la config en dictionnaire.

        Parameters
        ----------
        exclude_defaults : bool
            Si True, exclut les champs inchangés depuis les défauts.
        """
        import dataclasses

        default = RiskConfig() if exclude_defaults else None
        result: dict[str, object] = {}
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if exclude_defaults and default is not None:
                default_val = getattr(default, f.name)
                if value == default_val:
                    continue
            result[f.name] = value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RiskConfig":
        """Construit une RiskConfig depuis un dictionnaire.

        Les clés inconnues sont rejetées (fail-fast).
        """
        import dataclasses

        valid_fields = {f.name for f in dataclasses.fields(cls)}
        unknown = set(data.keys()) - valid_fields
        if unknown:
            raise ValueError(
                f"Clés inconnues dans RiskConfig: {sorted(unknown)}. "
                f"Clés valides: {sorted(valid_fields)}"
            )

        # Filtrer les clés valides
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)  # type: ignore[arg-type]

    def with_overrides(self, **overrides: object) -> "RiskConfig":
        """Retourne une nouvelle config avec les overrides appliqués.

        Les clés inconnues sont rejetées.
        """
        import dataclasses

        current = self.to_dict(exclude_defaults=False)
        valid_fields = {f.name for f in dataclasses.fields(self)}
        unknown = set(overrides.keys()) - valid_fields
        if unknown:
            raise ValueError(
                f"Overrides inconnus: {sorted(unknown)}. "
                f"Clés valides: {sorted(valid_fields)}"
            )
        current.update(overrides)
        return RiskConfig.from_dict(current)

    # ── P2-1 sizing live (2026-08-13) ─────────────────────────────────

    def build_sizing_config(self) -> "SizingConfig | None":
        """Construit la ``SizingConfig`` P2-1 consommée par le live.

        ``sizing_mode == "atr"`` → ``None`` (comportement legacy inchangé).
        Sinon, charge les multiplicateurs sectoriels depuis
        ``sector_multipliers_path`` si configuré (illisible → ignorés
        avec un WARNING, pas d'échec du run).
        """
        import json
        import logging
        from pathlib import Path

        from common.sizing import SizingConfig

        mode = str(self.sizing_mode or "atr").strip().lower()
        if mode == "atr":
            return None
        if mode not in {"equal_weight", "conviction_weighted", "rank_weighted"}:
            logging.getLogger(__name__).warning(
                "P2-1: sizing_mode inconnu %r — comportement legacy (atr).", mode,
            )
            return None

        sector_multipliers: dict[str, float] | None = None
        if self.sector_multipliers_path:
            try:
                payload = json.loads(Path(self.sector_multipliers_path).read_text(encoding="utf-8"))
                sector_multipliers = {
                    str(k).strip(): float(v)
                    for k, v in payload.items()
                    if str(k).strip()
                }
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "P2-1: multiplicateurs sectoriels illisibles (%s) — ignorés.",
                    exc,
                )

        return SizingConfig(
            mode=mode,
            min_weight_pct=float(self.sizing_min_weight_pct),
            max_weight_pct=float(self.sizing_max_weight_pct),
            sector_multipliers=sector_multipliers,
        )

    # ── Section 17 Point 6.1 : factories unifiées ─────────────────────

    @classmethod
    def from_preset(
        cls,
        preset_key: str | None = None,
        *,
        equity: float | None = None,
        **overrides: object,
    ) -> "RiskConfig":
        """Construit une RiskConfig à partir d'un preset capital.

        Si ``preset_key`` n'est pas fourni, le preset est résolu
        automatiquement depuis ``equity`` via
        ``resolve_capital_preset_for_equity()``.

        Les ``overrides`` sont appliqués en dernier (priorité maximale)
        et les clés inconnues sont rejetées.
        """
        from common.capital_presets import (
            build_risk_config_kwargs_from_preset,
            resolve_capital_preset_for_equity,
        )

        if preset_key is not None:
            from common.capital_presets import get_capital_preset_by_key

            preset = get_capital_preset_by_key(preset_key)
        elif equity is not None:
            preset = resolve_capital_preset_for_equity(equity)
        else:
            raise ValueError("from_preset requiert preset_key ou equity.")

        kwargs = build_risk_config_kwargs_from_preset(preset)
        kwargs.update(overrides)
        return cls.from_dict(kwargs)

    @classmethod
    def from_yaml_section(
        cls,
        yaml_data: dict[str, object] | None = None,
        *,
        preset_key: str | None = None,
        equity: float | None = None,
        **overrides: object,
    ) -> "RiskConfig":
        """Construit une RiskConfig depuis la section ``risk_management``
        du fichier ``config.yaml``, fusionnée avec un preset capital.

        Priorité (croissante) :
        1. Défauts du dataclass
        2. ``config.yaml`` → section ``risk_management``
        3. Preset capital (auto-résolu ou explicite)
        4. ``overrides`` explicites (CLI args, etc.)

        Les clés présentes dans le YAML mais non reconnues comme champs
        valides de ``RiskConfig`` sont journalisées en WARNING, pas
        rejetées (compatibilité avec les clés de config non-risk).
        """
        import logging

        from common.config_loader import load_config

        _logger = logging.getLogger(__name__)

        # 1. Charger config.yaml si pas fourni
        if yaml_data is None:
            full_cfg = load_config() or {}
            yaml_risk = full_cfg.get("risk_management", {})
            if not isinstance(yaml_risk, dict):
                yaml_risk = {}
        else:
            yaml_risk = dict(yaml_data)

        # 2. Filtrer les clés YAML connues et avertir sur les inconnues
        import dataclasses

        valid_fields = {f.name for f in dataclasses.fields(cls)}
        yaml_known: dict[str, object] = {}
        for k, v in yaml_risk.items():
            if k in valid_fields:
                yaml_known[k] = v
            else:
                _logger.debug("RiskConfig.from_yaml_section: clé YAML non-risk ignorée %s", k)

        # 3. Résoudre le preset capital
        if preset_key is not None or equity is not None:
            preset_cfg = cls.from_preset(preset_key=preset_key, equity=equity)
        else:
            preset_cfg = RiskConfig()

        # 4. Fusion : défauts → YAML → preset → overrides
        #    (on part des défauts, on applique YAML, puis preset, puis overrides)
        merged = preset_cfg.to_dict(exclude_defaults=False)
        # YAML écrase les défauts (mais pas le preset)
        merged.update(yaml_known)
        # Recharger le preset pour qu'il écrase YAML
        if preset_key is not None or equity is not None:
            from common.capital_presets import (
                build_risk_config_kwargs_from_preset,
                get_capital_preset_by_key,
                resolve_capital_preset_for_equity,
            )

            if preset_key is not None:
                preset = get_capital_preset_by_key(preset_key)
            elif equity is not None:
                preset = resolve_capital_preset_for_equity(equity)
            else:
                preset = None

            if preset is not None:
                preset_kwargs = build_risk_config_kwargs_from_preset(preset)
                merged.update(preset_kwargs)

        # Overrides écrasent tout
        merged.update(overrides)

        return cls.from_dict(merged)


# ── Section 17 Point 6.1 : loader canonique ────────────────────────────


def load_risk_config(
    *,
    equity: float | None = None,
    preset_key: str | None = None,
    yaml_path: str | None = None,
    cli_overrides: dict[str, object] | None = None,
) -> RiskConfig:
    """Charge une ``RiskConfig`` canonique, point d'entrée unique pour
    tous les consommateurs (CLI live, backtest, IHM).

    Priorité : defaults < config.yaml < capital_preset < cli_overrides.

    Parameters
    ----------
    equity : float | None
        Equity du compte pour résolution automatique du preset.
    preset_key : str | None
        Clé de preset explicite (court-circuite la résolution auto).
    yaml_path : str | None
        Chemin vers un fichier YAML alternatif (None = config.yaml).
    cli_overrides : dict | None
        Overrides explicites (CLI args, flags IHM, etc.).

    Returns
    -------
    RiskConfig
        Configuration risqué immuable, validée, avec fingerprint.
    """
    import logging

    _logger = logging.getLogger(__name__)

    # 1. Charger config.yaml
    if yaml_path is not None:
        from common.config_loader import load_config_from_path
        full_cfg = load_config_from_path(yaml_path) or {}
    else:
        from common.config_loader import load_config
        full_cfg = load_config() or {}

    yaml_risk = full_cfg.get("risk_management", {})
    if not isinstance(yaml_risk, dict):
        yaml_risk = {}

    # 2. Construire via from_yaml_section
    overrides = dict(cli_overrides or {})
    # ── V1 Multi-Horizon : injecter les maps par défaut si non fournies ──
    # Ne pas écraser les maps déjà présentes dans YAML ou overrides.
    yaml_risk = full_cfg.get("risk_management", {})
    if not isinstance(yaml_risk, dict):
        yaml_risk = {}
    _map_defaults: dict[str, dict[int, float]] = {
        "_atr_stop_multiple_map": {3: 1.5, 5: 2.0, 10: 2.5, 15: 3.0, 20: 3.5},
        "_tp_atr_multiple_map": {3: 2.0, 5: 2.5, 10: 3.0, 15: 3.5, 20: 4.0},
        "_tp_max_pct_map": {3: 0.03, 5: 0.04, 10: 0.07, 15: 0.10, 20: 0.13},
    }
    for _k, _v in _map_defaults.items():
        if _k not in overrides and _k not in yaml_risk:
            overrides[_k] = _v
    config = RiskConfig.from_yaml_section(
        yaml_data=yaml_risk,
        preset_key=preset_key,
        equity=equity,
        **overrides,
    )

    # 3. Logguer le fingerprint pour audit
    _logger.info(
        "load_risk_config: equity=%.0f preset=%s fingerprint=%s",
        equity or 0,
        preset_key or "auto",
        config.fingerprint,
    )

    return config

