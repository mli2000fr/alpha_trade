"""Sprint S7 — `AlphaScannerConfig` + constantes module ``selector``.

Extrait de ``selector.alpha_scanner`` (Phase 3.3.a → S7) pour découpler
la configuration de l'orchestration. Tout est ré-exporté par le shim
``selector.alpha_scanner`` afin de préserver l'API historique.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import cast

import numpy as np
import yaml

from core.filter_profiles import STRICT_SWING_CASH_FILTERS, StrictFilterProfile

RUN_SUMMARY_PREFIX = "::alpha_trade_run_summary::"
PRICE_COLUMNS = ["symbol", "date", "close", "volume", "high", "low"]
DATA_QUALITY_MODE_BLOCK = "block"
DATA_QUALITY_MODE_WARN_SKIP_FILTER = "warn_skip_filter"
SUPPORTED_DATA_QUALITY_MODES = {
    DATA_QUALITY_MODE_BLOCK,
    DATA_QUALITY_MODE_WARN_SKIP_FILTER,
}
ABLATION_MODE_OFF = "off"
ABLATION_MODE_SHADOW = "shadow"
SUPPORTED_ABLATION_MODES = {
    ABLATION_MODE_OFF,
    ABLATION_MODE_SHADOW,
}
ABLATION_FILTER_CONFIG_OVERRIDES: dict[str, dict[str, object]] = {
    "volatility": {"max_volatility_ratio": None},
    "atr": {"min_atr_pct_20": None, "max_atr_pct_20": None},
    "relative_strength": {"min_relative_strength_index": None},
    "ma200": {"require_above_ma200": False},
    "high_52w": {"min_high_52w_proximity": None},
    "weekly_trend": {"min_weekly_trend_score": None},
    "market_cap": {"min_market_cap": None, "market_cap_max_age_days": None},
    "market_cap_ttl": {"market_cap_max_age_days": None},
    "beta": {"min_beta_126": None},
    "spread": {"max_spread_bps": None, "max_spread_bps_iex": None, "min_quote_size": None},
    "earnings_blackout": {"earnings_blackout_days": None},
}
SUPPORTED_ABLATION_FILTERS = frozenset(ABLATION_FILTER_CONFIG_OVERRIDES)
SUPPORTED_ABLATION_OVERRIDE_KEYS = frozenset(
    {
        "selection_size",
        "max_volatility_ratio",
        "min_relative_strength_index",
        "min_high_52w_proximity",
        "min_weekly_trend_score",
        "min_atr_pct_20",
        "max_atr_pct_20",
        "min_market_cap",
        "min_beta_126",
        "max_spread_bps",
        "max_spread_bps_iex",
        "min_quote_size",
        "market_cap_max_age_days",
        "earnings_blackout_days",
        "require_above_ma200",
        "max_anomaly_count",
        "max_missing_days_count",
        "sector_cap_ratio",
        "neutralize_by_sector",
        "weight_trend_vcp",
        "weight_total_score",
        "weight_rsi",
    }
)
DEFAULT_ABLATION_ARTIFACT_DIR = "artifacts/selector/ablation"


def _normalize_ablation_filter_keys(filter_keys: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_key in filter_keys:
        key = str(raw_key).strip()
        if not key:
            continue
        if key not in SUPPORTED_ABLATION_FILTERS:
            raise ValueError(
                f"Filtre d'ablation inconnu `{key}` ; valeurs supportées: {sorted(SUPPORTED_ABLATION_FILTERS)}."
            )
        if key not in seen:
            normalized.append(key)
            seen.add(key)
    return tuple(normalized)


def _normalize_ablation_overrides(raw_overrides: dict[str, object] | None) -> dict[str, object]:
    overrides = dict(raw_overrides or {})
    invalid_keys = sorted(set(overrides).difference(SUPPORTED_ABLATION_OVERRIDE_KEYS))
    if invalid_keys:
        raise ValueError(
            "Clés `config_overrides` non supportées pour une variante selector: "
            f"{invalid_keys}. Clés supportées: {sorted(SUPPORTED_ABLATION_OVERRIDE_KEYS)}."
        )
    return overrides


@dataclass(frozen=True, slots=True)
class SelectorVariantSpec:
    variant_id: str
    description: str | None = None
    disabled_filters: tuple[str, ...] = ()
    config_overrides: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        variant_id = str(self.variant_id).strip()
        if not variant_id:
            raise ValueError("variant_id doit être non vide.")
        normalized_filters = _normalize_ablation_filter_keys(list(self.disabled_filters))
        normalized_overrides = _normalize_ablation_overrides(self.config_overrides)
        if not normalized_filters and not normalized_overrides:
            raise ValueError(
                f"La variante `{variant_id}` doit désactiver au moins un filtre ou définir un override."
            )
        description = str(self.description).strip() if self.description is not None else None
        object.__setattr__(self, "variant_id", variant_id)
        object.__setattr__(self, "description", description or None)
        object.__setattr__(self, "disabled_filters", normalized_filters)
        object.__setattr__(self, "config_overrides", normalized_overrides)


@dataclass(frozen=True, slots=True)
class SelectorAblationPlan:
    mode: str = ABLATION_MODE_OFF
    variants: tuple[SelectorVariantSpec, ...] = ()
    artifact_dir: str = DEFAULT_ABLATION_ARTIFACT_DIR

    def __post_init__(self) -> None:
        normalized_mode = str(self.mode).strip() or ABLATION_MODE_OFF
        if normalized_mode not in SUPPORTED_ABLATION_MODES:
            raise ValueError(
                f"mode d'ablation invalide `{normalized_mode}` ; valeurs supportées: {sorted(SUPPORTED_ABLATION_MODES)}."
            )
        normalized_variants = tuple(self.variants)
        seen_variant_ids: set[str] = set()
        for variant in normalized_variants:
            if not isinstance(variant, SelectorVariantSpec):
                raise ValueError("variants doit contenir uniquement des SelectorVariantSpec.")
            if variant.variant_id in seen_variant_ids:
                raise ValueError(f"variant_id dupliqué dans le plan d'ablation: `{variant.variant_id}`.")
            seen_variant_ids.add(variant.variant_id)
        artifact_dir = str(self.artifact_dir).strip() or DEFAULT_ABLATION_ARTIFACT_DIR
        if normalized_mode == ABLATION_MODE_SHADOW and not normalized_variants:
            raise ValueError("mode=shadow requiert au moins une variante d'ablation.")
        object.__setattr__(self, "mode", normalized_mode)
        object.__setattr__(self, "variants", normalized_variants)
        object.__setattr__(self, "artifact_dir", artifact_dir)


def build_selector_variant_spec_from_mapping(payload: dict[str, object]) -> SelectorVariantSpec:
    variant_id = payload.get("variant_id", payload.get("name", payload.get("id", "")))
    disabled_filters = payload.get("disabled_filters", ())
    if not isinstance(disabled_filters, (list, tuple)):
        raise ValueError("disabled_filters doit être une liste/tuple de clés de filtres.")
    config_overrides = payload.get("config_overrides", {})
    if not isinstance(config_overrides, dict):
        raise ValueError("config_overrides doit être un mapping JSON/YAML.")
    return SelectorVariantSpec(
        variant_id=str(variant_id),
        description=cast(str | None, payload.get("description")),
        disabled_filters=tuple(str(value) for value in disabled_filters),
        config_overrides=dict(config_overrides),
    )


def build_selector_ablation_plan_from_mapping(payload: dict[str, object]) -> SelectorAblationPlan:
    raw_variants = payload.get("variants", [])
    if raw_variants is None:
        raw_variants = []
    if not isinstance(raw_variants, list):
        raise ValueError("Le fichier d'ablation selector doit contenir `variants` sous forme de liste.")
    variants = [
        build_selector_variant_spec_from_mapping(dict(item))
        for item in raw_variants
        if isinstance(item, dict)
    ]
    mode = payload.get("mode")
    normalized_mode = str(mode).strip() if mode not in (None, "") else (ABLATION_MODE_SHADOW if variants else ABLATION_MODE_OFF)
    return SelectorAblationPlan(
        mode=normalized_mode,
        variants=tuple(variants),
        artifact_dir=str(payload.get("artifact_dir") or DEFAULT_ABLATION_ARTIFACT_DIR),
    )


def load_selector_ablation_plan_from_file(file_path: str | Path) -> SelectorAblationPlan:
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"Fichier d'ablation selector introuvable: {path}")
    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(raw_text)
    else:
        payload = yaml.safe_load(raw_text)
    if not isinstance(payload, dict):
        raise ValueError("Le fichier d'ablation selector doit contenir un objet JSON/YAML racine.")
    return build_selector_ablation_plan_from_mapping(dict(payload))


def get_ablation_filter_config_overrides(filter_key: str) -> dict[str, object]:
    normalized_key = str(filter_key).strip()
    if normalized_key not in ABLATION_FILTER_CONFIG_OVERRIDES:
        raise ValueError(
            f"Filtre d'ablation inconnu `{normalized_key}` ; valeurs supportées: {sorted(SUPPORTED_ABLATION_FILTERS)}."
        )
    return dict(ABLATION_FILTER_CONFIG_OVERRIDES[normalized_key])


def is_filter_effectively_enabled(config: AlphaScannerConfig, filter_key: str) -> bool:
    normalized_key = str(filter_key).strip()
    if normalized_key == "volatility":
        return config.max_volatility_ratio is not None
    if normalized_key == "atr":
        return config.min_atr_pct_20 is not None or config.max_atr_pct_20 is not None
    if normalized_key == "relative_strength":
        return config.min_relative_strength_index is not None
    if normalized_key == "ma200":
        return bool(config.require_above_ma200)
    if normalized_key == "high_52w":
        return config.min_high_52w_proximity is not None
    if normalized_key == "weekly_trend":
        return config.min_weekly_trend_score is not None
    if normalized_key == "market_cap":
        return config.min_market_cap is not None
    if normalized_key == "market_cap_ttl":
        return config.min_market_cap is not None and config.market_cap_max_age_days is not None
    if normalized_key == "beta":
        return config.min_beta_126 is not None
    if normalized_key == "spread":
        return config.max_spread_bps is not None
    if normalized_key == "earnings_blackout":
        return config.earnings_blackout_days is not None
    raise ValueError(
        f"Filtre d'ablation inconnu `{normalized_key}` ; valeurs supportées: {sorted(SUPPORTED_ABLATION_FILTERS)}."
    )


def apply_variant_spec_to_config(
    base_config: AlphaScannerConfig,
    variant: SelectorVariantSpec,
) -> AlphaScannerConfig:
    overrides: dict[str, object] = {}
    for filter_key in variant.disabled_filters:
        overrides.update(get_ablation_filter_config_overrides(filter_key))
    overrides.update(dict(variant.config_overrides))
    return replace(base_config, **overrides)


def compute_config_diff(
    base_config: AlphaScannerConfig,
    other_config: AlphaScannerConfig,
) -> dict[str, object]:
    diff: dict[str, object] = {}
    for field_info in fields(AlphaScannerConfig):
        field_name = field_info.name
        if field_name == "ablation_plan":
            continue
        if field_name not in SUPPORTED_ABLATION_OVERRIDE_KEYS and field_name not in {
            "max_spread_bps_iex",
            "min_quote_size",
            "market_cap_max_age_days",
            "earnings_blackout_days",
        }:
            continue
        base_value = getattr(base_config, field_name)
        other_value = getattr(other_config, field_name)
        if base_value != other_value:
            diff[field_name] = other_value
    return diff


@dataclass(frozen=True, slots=True)
class AlphaScannerConfig:
    preset_profile: str = "custom"
    preset_profile_version: str | None = None
    price_table: str = "stock_bars_daily"
    score_table: str = "stock_scores"
    chunk_size: int = 500
    selection_size: int = 60
    short_selection_size: int = 60
    min_history_days: int = 252
    liquidity_threshold: float = 20_000_000.0
    min_close: float = 5.0
    max_volatility_ratio: float | None = None
    min_relative_strength_index: float | None = None
    min_high_52w_proximity: float | None = None
    min_weekly_trend_score: float | None = None
    min_atr_pct_20: float | None = None
    max_atr_pct_20: float | None = None
    min_market_cap: float | None = None
    min_beta_126: float | None = None
    max_spread_bps: float | None = None
    # Phase 3.3.c — extensions IEX : relâchement contrôlé du filtre spread.
    max_spread_bps_iex: float | None = None
    min_quote_size: float | None = None
    # Phase 3.3.d — TTL appliqué au filtre ``min_market_cap``.
    market_cap_max_age_days: int | None = None
    spread_data_quality_mode: str = DATA_QUALITY_MODE_BLOCK
    earnings_blackout_days: int | None = None
    earnings_data_quality_mode: str = DATA_QUALITY_MODE_BLOCK
    market_cap_filter_data_quality_mode: str = DATA_QUALITY_MODE_WARN_SKIP_FILTER
    require_above_ma200: bool = False
    max_anomaly_count: int = 20
    max_missing_days_count: int = 10
    sector_cap_ratio: float = 0.30
    volatility_short_window: int = 10
    volatility_long_window: int = 60
    vcp_ratio_threshold: float = 0.60
    ma_short_window: int = 50
    ma_mid_window: int = 150
    ma_long_window: int = 200
    trailing_range_window: int = 252
    liquidity_lookback_days: int = 20
    update_batch_size: int = 500
    max_workers: int | None = None
    ablation_plan: SelectorAblationPlan | None = None

    # Composition multi-facteurs : poids configurables.
    weight_trend_vcp: float = 0.50
    weight_total_score: float = 0.30
    weight_rsi: float = 0.20

    # Winsorisation (anti-outliers).
    winsor_lower_pct: float = 0.01
    winsor_upper_pct: float = 0.99

    # Neutralisation cross-sectorielle (P0).
    neutralize_by_sector: bool = True

    @classmethod
    def from_filter_profile(
        cls,
        profile: StrictFilterProfile,
        **overrides: object,
    ) -> AlphaScannerConfig:
        merged_kwargs: dict[str, object] = {
            "preset_profile": profile.name,
            "preset_profile_version": profile.version,
            **profile.to_scanner_config_kwargs(),
        }
        # Phase 3.3.c/d — merger les extensions IEX/TTL.
        for key, value in profile.iex_extensions().items():
            if value is not None:
                merged_kwargs[key] = value
        for key, value in overrides.items():
            merged_kwargs[key] = value
        return cls(**merged_kwargs)

    @classmethod
    def strict_swing_cash(cls, **overrides: object) -> AlphaScannerConfig:
        return cls.from_filter_profile(STRICT_SWING_CASH_FILTERS, **overrides)

    @staticmethod
    def _yaml_defaults() -> dict[str, object]:
        """Charge les valeurs par defaut depuis ``config.yaml`` (section ``selector``)."""
        try:
            from common.config_loader import load_config
            cfg = load_config() or {}
            return dict(cfg.get("selector") or {})
        except Exception:
            return {}

    def __post_init__(self) -> None:
        if self.chunk_size < 1:
            raise ValueError("chunk_size doit être supérieur ou égal à 1.")
        if self.selection_size < 1:
            raise ValueError("selection_size doit etre superieur ou egal a 1.")
        if self.short_selection_size < 0:
            raise ValueError("short_selection_size doit etre superieur ou egal a 0.")
        if self.min_history_days < self.trailing_range_window:
            raise ValueError("min_history_days doit être supérieur ou égal à trailing_range_window.")
        if self.liquidity_threshold <= 0:
            raise ValueError("liquidity_threshold doit être strictement positif.")
        if self.min_close <= 0:
            raise ValueError("min_close doit être strictement positif.")
        if self.max_volatility_ratio is not None and self.max_volatility_ratio <= 0:
            raise ValueError("max_volatility_ratio doit être strictement positif lorsqu'il est renseigné.")
        if self.min_relative_strength_index is not None and self.min_relative_strength_index <= 0:
            raise ValueError("min_relative_strength_index doit être strictement positif lorsqu'il est renseigné.")
        if self.min_high_52w_proximity is not None and not 0 < self.min_high_52w_proximity <= 1:
            raise ValueError("min_high_52w_proximity doit être compris dans ]0, 1] lorsqu'il est renseigné.")
        if self.min_weekly_trend_score is not None and not 0 <= self.min_weekly_trend_score <= 1:
            raise ValueError("min_weekly_trend_score doit être compris dans [0, 1] lorsqu'il est renseigné.")
        if self.min_atr_pct_20 is not None and self.min_atr_pct_20 <= 0:
            raise ValueError("min_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_atr_pct_20 is not None and self.max_atr_pct_20 <= 0:
            raise ValueError("max_atr_pct_20 doit être strictement positif lorsqu'il est renseigné.")
        if self.min_market_cap is not None and self.min_market_cap <= 0:
            raise ValueError("min_market_cap doit être strictement positif lorsqu'il est renseigné.")
        if self.min_beta_126 is not None and self.min_beta_126 <= 0:
            raise ValueError("min_beta_126 doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps is not None and self.max_spread_bps <= 0:
            raise ValueError("max_spread_bps doit être strictement positif lorsqu'il est renseigné.")
        if self.max_spread_bps_iex is not None and self.max_spread_bps_iex <= 0:
            raise ValueError("max_spread_bps_iex doit être strictement positif lorsqu'il est renseigné.")
        if (
            self.max_spread_bps is not None
            and self.max_spread_bps_iex is not None
            and self.max_spread_bps_iex < self.max_spread_bps
        ):
            raise ValueError(
                "max_spread_bps_iex doit être >= max_spread_bps (relâchement IEX, pas durcissement)."
            )
        if self.min_quote_size is not None and self.min_quote_size < 0:
            raise ValueError("min_quote_size doit être positif ou nul lorsqu'il est renseigné.")
        if self.market_cap_max_age_days is not None and self.market_cap_max_age_days < 0:
            raise ValueError("market_cap_max_age_days doit être positif ou nul lorsqu'il est renseigné.")
        if self.earnings_blackout_days is not None and self.earnings_blackout_days < 0:
            raise ValueError("earnings_blackout_days doit être positif ou nul lorsqu'il est renseigné.")
        for field_name, field_value in (
            ("spread_data_quality_mode", self.spread_data_quality_mode),
            ("earnings_data_quality_mode", self.earnings_data_quality_mode),
            ("market_cap_filter_data_quality_mode", self.market_cap_filter_data_quality_mode),
        ):
            if str(field_value).strip() not in SUPPORTED_DATA_QUALITY_MODES:
                raise ValueError(
                    f"{field_name} doit être l'un de {sorted(SUPPORTED_DATA_QUALITY_MODES)}."
                )
        if (
            self.min_atr_pct_20 is not None
            and self.max_atr_pct_20 is not None
            and self.min_atr_pct_20 > self.max_atr_pct_20
        ):
            raise ValueError("min_atr_pct_20 ne peut pas être supérieur à max_atr_pct_20.")
        if not 0 < self.sector_cap_ratio <= 1:
            raise ValueError("sector_cap_ratio doit être compris entre 0 exclus et 1 inclus.")
        if self.volatility_short_window < 2 or self.volatility_long_window <= self.volatility_short_window:
            raise ValueError("Les fenêtres de volatilité sont invalides.")
        if self.vcp_ratio_threshold <= 0:
            raise ValueError("vcp_ratio_threshold doit être strictement positif.")
        if self.update_batch_size < 1:
            raise ValueError("update_batch_size doit être supérieur ou égal à 1.")
        if self.max_workers is not None and self.max_workers < 1:
            raise ValueError("max_workers doit être supérieur ou égal à 1.")
        if self.ablation_plan is not None and not isinstance(self.ablation_plan, SelectorAblationPlan):
            raise ValueError("ablation_plan doit être un SelectorAblationPlan ou None.")
        total_weight = self.weight_trend_vcp + self.weight_total_score + self.weight_rsi
        if not np.isclose(total_weight, 1.0, atol=1e-6):
            raise ValueError(
                f"La somme des poids facteurs doit être égale à 1.0 "
                f"(weight_trend_vcp + weight_total_score + weight_rsi = {total_weight:.6f})."
            )
        if not 0.0 <= self.winsor_lower_pct < self.winsor_upper_pct <= 1.0:
            raise ValueError("winsor_lower_pct et winsor_upper_pct doivent respecter 0 ≤ lower < upper ≤ 1.")


# ── Sprint 5 — Grilles symétriques market-neutral ──────────────────────

SYMMETRIC_GRIDS: dict[str, tuple[int, int]] = {
    "60/60": (60, 60),
    "80/80": (80, 80),
    "100/100": (100, 100),
    "40/40": (40, 40),
    "20/20": (20, 20),
}
"""Grilles symétriques prédéfinies pour tester la neutralité nette.
Clé = label, valeur = (selection_size, short_selection_size)."""


def resolve_symmetric_grid(label: str) -> tuple[int, int]:
    """Résout un label de grille symétrique (ex: \"60/60\", \"80/80\").
    Retourne (selection_size, short_selection_size).
    Lève KeyError si le label est inconnu.
    """
    if label not in SYMMETRIC_GRIDS:
        raise KeyError(
            f"Grille symétrique inconnue : {label!r}. "
            f"Grilles disponibles : {', '.join(sorted(SYMMETRIC_GRIDS))}"
        )
    return SYMMETRIC_GRIDS[label]


__all__ = [
    "ABLATION_MODE_OFF",
    "ABLATION_MODE_SHADOW",
    "AlphaScannerConfig",
    "DATA_QUALITY_MODE_BLOCK",
    "DATA_QUALITY_MODE_WARN_SKIP_FILTER",
    "DEFAULT_ABLATION_ARTIFACT_DIR",
    "PRICE_COLUMNS",
    "RUN_SUMMARY_PREFIX",
    "SUPPORTED_ABLATION_FILTERS",
    "SUPPORTED_ABLATION_MODES",
    "SUPPORTED_ABLATION_OVERRIDE_KEYS",
    "SUPPORTED_DATA_QUALITY_MODES",
    "SelectorAblationPlan",
    "SelectorVariantSpec",
    "apply_variant_spec_to_config",
    "build_selector_ablation_plan_from_mapping",
    "build_selector_variant_spec_from_mapping",
    "compute_config_diff",
    "get_ablation_filter_config_overrides",
    "is_filter_effectively_enabled",
    "load_selector_ablation_plan_from_file",
    "SYMMETRIC_GRIDS",
    "resolve_symmetric_grid",
]

