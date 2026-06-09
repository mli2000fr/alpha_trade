"""Presets de capital partagés entre IHM pipeline et backtesting.

Inclut un garde-fou A-005 : tout écart explicite entre un preset capital et le
profil canonique ``STRICT_SWING_CASH_FILTERS`` doit être documenté dans le YAML.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.filter_profiles import STRICT_SWING_CASH_FILTERS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAPITAL_PRESETS_CONFIG_PATH = PROJECT_ROOT / "config" / "capital_presets.yaml"
DETECTED_EQUITY_PLACEHOLDER = "__DETECTED_EQUITY__"
DEFAULT_CAPITAL_PRESET_KEY = "capital_0_2000_eur"
SELECTOR_RS_ALIAS_KEY = "selector_min_ibd_rs_rank"
SELECTOR_RS_LEGACY_KEY = "selector_min_relative_strength_index"

STRICT_PROFILE_SELECTOR_BASELINES: dict[str, Any] = {
    "selector_liquidity_threshold": float(STRICT_SWING_CASH_FILTERS.min_avg_dollar_volume_20d),
    "selector_min_close": float(STRICT_SWING_CASH_FILTERS.min_close),
    "selector_max_volatility_ratio": float(STRICT_SWING_CASH_FILTERS.max_volatility_ratio),
    SELECTOR_RS_ALIAS_KEY: float(STRICT_SWING_CASH_FILTERS.min_relative_strength_index or 100.0),
    "selector_min_high_52w_proximity": float(STRICT_SWING_CASH_FILTERS.min_high_52w_proximity),
    "selector_min_weekly_trend_score": float(STRICT_SWING_CASH_FILTERS.min_weekly_trend_score),
    "selector_min_atr_pct_20": float(STRICT_SWING_CASH_FILTERS.min_atr_pct_20),
    "selector_max_atr_pct_20": float(STRICT_SWING_CASH_FILTERS.max_atr_pct_20),
    "selector_min_market_cap": float(STRICT_SWING_CASH_FILTERS.min_market_cap),
    "selector_min_beta_126": float(STRICT_SWING_CASH_FILTERS.min_beta_126),
    "selector_max_spread_bps": float(STRICT_SWING_CASH_FILTERS.max_spread_bps),
    "selector_max_spread_bps_iex": float(STRICT_SWING_CASH_FILTERS.max_spread_bps_iex),
    "selector_earnings_blackout_days": int(STRICT_SWING_CASH_FILTERS.earnings_blackout_days or 0),
    "selector_require_above_ma200": bool(STRICT_SWING_CASH_FILTERS.require_above_ma200),
}


@dataclass(frozen=True, slots=True)
class CapitalPreset:
    key: str
    label: str
    description: str
    min_equity: float
    max_equity: float | None
    values: dict[str, Any]
    strict_profile_justifications: dict[str, str] = field(default_factory=dict)

    def matches_equity(self, equity: float | None) -> bool:
        if equity is None:
            return False
        if equity < self.min_equity:
            return False
        if self.max_equity is not None and equity > self.max_equity:
            return False
        return True

    def to_session_state_values(self, *, detected_equity: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for option_key, raw_value in self.values.items():
            normalized_option_key = (
                SELECTOR_RS_LEGACY_KEY if option_key == SELECTOR_RS_ALIAS_KEY else option_key
            )
            session_key = (
                normalized_option_key
                if normalized_option_key.startswith("pipeline_")
                else f"pipeline_{normalized_option_key}"
            )
            if raw_value == DETECTED_EQUITY_PLACEHOLDER:
                if detected_equity is None or detected_equity <= 0:
                    continue
                payload[session_key] = float(detected_equity)
                continue
            payload[session_key] = _normalize_option_value(normalized_option_key, raw_value)
        return payload


def _normalize_option_value(option_key: str, raw_value: Any) -> Any:
    if isinstance(raw_value, bool):
        return "auto" if raw_value else "off"
    normalized = str(raw_value).strip().lower()
    if normalized in {"false", "off"}:
        return "off"
    if normalized in {"true", "auto"}:
        return "auto"
    return raw_value


def _coerce_float(value: object, *, field_name: str) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Valeur numérique invalide pour {field_name}: {value!r}") from exc


def _canonicalize_strict_profile_key(selector_key: str) -> str:
    cleaned_key = str(selector_key or "").strip()
    if cleaned_key == SELECTOR_RS_LEGACY_KEY:
        return SELECTOR_RS_ALIAS_KEY
    return cleaned_key


def _normalize_scalar_for_comparison(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return value


def _extract_selector_rs_value(values: dict[str, Any]) -> Any:
    rs_alias = values.get(SELECTOR_RS_ALIAS_KEY)
    rs_legacy = values.get(SELECTOR_RS_LEGACY_KEY)
    if rs_alias is not None and rs_legacy is not None:
        if _normalize_scalar_for_comparison(rs_alias) != _normalize_scalar_for_comparison(rs_legacy):
            raise ValueError(
                "Les alias selector_min_ibd_rs_rank et selector_min_relative_strength_index "
                "doivent rester identiques dans un preset de capital."
            )
    return rs_alias if rs_alias is not None else rs_legacy


def collect_strict_profile_deviations(preset: CapitalPreset) -> dict[str, dict[str, Any]]:
    deviations: dict[str, dict[str, Any]] = {}
    for selector_key, strict_value in STRICT_PROFILE_SELECTOR_BASELINES.items():
        if selector_key == SELECTOR_RS_ALIAS_KEY:
            preset_value = _extract_selector_rs_value(preset.values)
            if preset_value is None:
                continue
        else:
            if selector_key not in preset.values:
                continue
            preset_value = preset.values[selector_key]
        if _normalize_scalar_for_comparison(preset_value) == _normalize_scalar_for_comparison(strict_value):
            continue
        deviations[selector_key] = {
            "preset_value": preset_value,
            "strict_value": strict_value,
        }
    return deviations


def _normalize_strict_profile_justifications(raw_value: Any, *, preset_key: str) -> dict[str, str]:
    if raw_value is None or raw_value == "":
        return {}
    if not isinstance(raw_value, dict):
        raise ValueError(
            f"Le preset {preset_key} doit définir `strict_profile_justifications` comme mapping YAML."
        )

    justifications: dict[str, str] = {}
    for raw_selector_key, raw_reason in raw_value.items():
        selector_key = _canonicalize_strict_profile_key(str(raw_selector_key))
        if selector_key not in STRICT_PROFILE_SELECTOR_BASELINES:
            raise ValueError(
                f"Le preset {preset_key} documente un champ strict inconnu: {raw_selector_key}"
            )
        reason = str(raw_reason or "").strip()
        if not reason:
            raise ValueError(
                f"Le preset {preset_key} doit fournir une justification non vide pour {selector_key}."
            )
        if selector_key in justifications:
            raise ValueError(
                f"Le preset {preset_key} documente plusieurs fois l'écart {selector_key}."
            )
        justifications[selector_key] = reason
    return justifications


def _validate_capital_preset_strict_profile_alignment(preset: CapitalPreset) -> None:
    deviations = collect_strict_profile_deviations(preset)
    documented = set(preset.strict_profile_justifications.keys())
    actual = set(deviations.keys())

    undocumented = sorted(actual - documented)
    if undocumented:
        details = ", ".join(
            f"{selector_key}={deviations[selector_key]['preset_value']!r} (strict={deviations[selector_key]['strict_value']!r})"
            for selector_key in undocumented
        )
        raise ValueError(
            f"Le preset {preset.key} diverge de STRICT_SWING_CASH_FILTERS sans justification: {details}"
        )

    stale = sorted(documented - actual)
    if stale:
        raise ValueError(
            f"Le preset {preset.key} contient des justifications devenues inutiles: {', '.join(stale)}"
        )


def _load_capital_presets_uncached(config_path: Path) -> tuple[CapitalPreset, ...]:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    raw_presets = payload.get("presets")
    if not isinstance(raw_presets, list) or not raw_presets:
        raise ValueError("Le fichier de presets de capital doit définir une liste non vide `presets`.")

    presets: list[CapitalPreset] = []
    previous_max: float | None = None
    seen_keys: set[str] = set()
    for raw_preset in raw_presets:
        if not isinstance(raw_preset, dict):
            raise ValueError("Chaque preset de capital doit être un mapping YAML.")
        key = str(raw_preset.get("key") or "").strip()
        label = str(raw_preset.get("label") or key).strip()
        description = str(raw_preset.get("description") or "").strip()
        min_equity = _coerce_float(raw_preset.get("min_equity", 0.0), field_name=f"{key}.min_equity")
        max_equity_raw = raw_preset.get("max_equity")
        max_equity = None if max_equity_raw in {None, ""} else _coerce_float(max_equity_raw, field_name=f"{key}.max_equity")
        values = dict(raw_preset.get("values") or {})
        strict_profile_justifications = _normalize_strict_profile_justifications(
            raw_preset.get("strict_profile_justifications"),
            preset_key=key or "<unknown>",
        )

        if not key:
            raise ValueError("Chaque preset de capital doit définir une clé `key` non vide.")
        if key in seen_keys:
            raise ValueError(f"Clé de preset de capital dupliquée: {key}")
        if max_equity is not None and max_equity < min_equity:
            raise ValueError(f"Le preset {key} a une borne max inférieure à la borne min.")
        if previous_max is not None and min_equity <= previous_max:
            raise ValueError("Les presets de capital doivent être ordonnés par tranches strictement croissantes.")
        if not values:
            raise ValueError(f"Le preset {key} doit définir au moins une valeur dans `values`.")

        preset = CapitalPreset(
            key=key,
            label=label,
            description=description,
            min_equity=min_equity,
            max_equity=max_equity,
            values=values,
            strict_profile_justifications=strict_profile_justifications,
        )
        _validate_capital_preset_strict_profile_alignment(preset)
        presets.append(preset)
        seen_keys.add(key)
        previous_max = max_equity if max_equity is not None else float("inf")

    return tuple(presets)


@lru_cache(maxsize=1)
def _load_default_capital_presets() -> tuple[CapitalPreset, ...]:
    return _load_capital_presets_uncached(CAPITAL_PRESETS_CONFIG_PATH)


def load_capital_presets(config_path: str | Path | None = None) -> tuple[CapitalPreset, ...]:
    if config_path is None:
        return _load_default_capital_presets()
    return _load_capital_presets_uncached(Path(config_path))


def get_capital_preset_by_key(key: str, *, config_path: str | Path | None = None) -> CapitalPreset | None:
    cleaned_key = str(key or "").strip()
    if not cleaned_key:
        return None
    for preset in load_capital_presets(config_path):
        if preset.key == cleaned_key:
            return preset
    return None


def resolve_capital_preset_for_equity(equity: float | None, *, config_path: str | Path | None = None) -> CapitalPreset | None:
    if equity is None:
        return None
    for preset in load_capital_presets(config_path):
        if preset.matches_equity(float(equity)):
            return preset
    return None


def require_capital_preset(key: str, *, config_path: str | Path | None = None) -> CapitalPreset:
    preset = get_capital_preset_by_key(key, config_path=config_path)
    if preset is None:
        raise ValueError(f"Preset de capital inconnu : {key}")
    return preset


def get_default_capital_preset(*, config_path: str | Path | None = None) -> CapitalPreset:
    preset = get_capital_preset_by_key(DEFAULT_CAPITAL_PRESET_KEY, config_path=config_path)
    if preset is None:
        presets = load_capital_presets(config_path)
        if not presets:
            raise ValueError("Aucun preset de capital disponible.")
        return presets[0]
    return preset


def resolve_effective_capital_preset(
    *,
    capital_preset_key: str | None = None,
    equity: float | None = None,
    config_path: str | Path | None = None,
) -> tuple[CapitalPreset, str]:
    cleaned_key = str(capital_preset_key or "").strip()
    if cleaned_key:
        return require_capital_preset(cleaned_key, config_path=config_path), "explicit_key"

    resolved = resolve_capital_preset_for_equity(equity, config_path=config_path)
    if resolved is not None:
        return resolved, "resolved_from_equity"

    return get_default_capital_preset(config_path=config_path), "default_fallback"


def capital_preset_fingerprint(preset: CapitalPreset) -> str:
    canonical_payload = {
        "key": preset.key,
        "values": {key: preset.values[key] for key in sorted(preset.values.keys())},
    }
    raw = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_screener_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]:
    values = preset.values
    default_liquidity_threshold = float(STRICT_SWING_CASH_FILTERS.min_avg_dollar_volume_20d)
    default_relative_strength = float(STRICT_SWING_CASH_FILTERS.min_relative_strength_index or 100.0)
    return {
        "liquidity_threshold_usd": float(values.get("screener_liquidity_threshold_usd", default_liquidity_threshold)),
        "min_relative_strength_index": float(values.get("screener_min_relative_strength_index", default_relative_strength)),
        "historical_range_lookback_days": int(values.get("screener_historical_range_lookback_days", 504)),
        "min_historical_range_score": float(values.get("screener_min_historical_range_score", 70.0)),
        "first_pass_window_days": int(values.get("screener_first_pass_window_days", 400)),
    }


def build_selector_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]:
    values = preset.values
    rs_threshold = values.get(SELECTOR_RS_ALIAS_KEY)
    if rs_threshold is None:
        rs_threshold = values.get(SELECTOR_RS_LEGACY_KEY, 100.0)
    rs_threshold_value = _coerce_float(
        rs_threshold if rs_threshold is not None else 100.0,
        field_name=f"{preset.key}.{SELECTOR_RS_ALIAS_KEY}",
    )
    return {
        "selection_size": int(values.get("selector_selection_size", 50)),
        "sector_cap_ratio": float(values.get("selector_sector_cap_ratio", 0.28)),
        "liquidity_threshold": float(values.get("selector_liquidity_threshold", 30_000_000.0)),
        "min_close": float(values.get("selector_min_close", 10.0)),
        "max_volatility_ratio": float(values.get("selector_max_volatility_ratio", 0.9)),
        "min_relative_strength_index": rs_threshold_value,
        "min_high_52w_proximity": float(values.get("selector_min_high_52w_proximity", 0.75)),
        "min_weekly_trend_score": float(values.get("selector_min_weekly_trend_score", 1.0)),
        "min_atr_pct_20": float(values.get("selector_min_atr_pct_20", 0.015)),
        "max_atr_pct_20": float(values.get("selector_max_atr_pct_20", 0.06)),
        "min_market_cap": float(values.get("selector_min_market_cap", 2_000_000_000.0)),
        "min_beta_126": float(values.get("selector_min_beta_126", 0.8)),
        "max_spread_bps": float(values.get("selector_max_spread_bps", 40.0)),
        "max_spread_bps_iex": float(values.get("selector_max_spread_bps_iex", 60.0)),
        "earnings_blackout_days": int(values.get("selector_earnings_blackout_days", 3)),
        "max_anomaly_count": int(values.get("selector_max_anomaly_count", 20)),
        "require_above_ma200": bool(values.get("selector_require_above_ma200", True)),
    }


_RISK_CONFIG_PRESET_MAPPING: tuple[tuple[str, str, type], ...] = (
    # (preset_key, RiskConfig field, cast)
    ("risk_per_trade_pct", "risk_per_trade_pct", float),
    ("risk_max_positions", "max_positions", int),
    ("risk_max_position_weight", "max_position_weight", float),
    ("risk_max_sector_weight", "max_sector_weight", float),
    ("risk_min_position_notional", "min_position_notional", float),
    ("risk_max_drawdown_pct", "max_portfolio_drawdown_pct", float),
    ("risk_max_daily_loss_pct", "max_daily_loss_pct", float),
    ("risk_drawdown_rolling_peak_window_days", "rolling_peak_window_days", int),
    ("risk_degraded_entry_allocation_pct", "degraded_entry_allocation_pct", float),
    ("risk_correlation_threshold", "correlation_threshold", float),
    ("risk_correlation_lookback_days", "correlation_lookback_days", int),
    ("risk_correlation_min_overlap", "correlation_min_overlap", int),
    ("risk_enable_kelly", "enable_kelly_sizing", bool),
0    ("risk_allow_fractional_shares", "allow_fractional_shares", bool),
    ("risk_score_weight", "score_weight", float),
    ("risk_prediction_weight", "prediction_weight", float),
)


def build_risk_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]:
    """Construit les kwargs ``RiskConfig`` à partir des valeurs d'un preset.

    Sprint S4 / fix backtest : les phases qui instancient ``RiskConfig`` (notamment
    la phase 2 du backtesting) doivent honorer les overrides définis dans le
    preset capital (tickets minimum, corrélation, drawdown, etc.). Sans cela,
    les valeurs par défaut de ``RiskConfig`` (ex. ``min_position_notional=500``)
    masquent silencieusement le preset choisi.
    """
    kwargs: dict[str, Any] = {}
    for preset_key, field_name, cast_fn in _RISK_CONFIG_PRESET_MAPPING:
        if preset_key not in preset.values:
            continue
        raw_value = preset.values[preset_key]
        if raw_value == DETECTED_EQUITY_PLACEHOLDER:
            # Le placeholder est résolu côté appelant (account_equity vient de l'equity réelle).
            continue
        if cast_fn is bool:
            if isinstance(raw_value, bool):
                kwargs[field_name] = raw_value
            else:
                kwargs[field_name] = str(raw_value).strip().lower() in {"true", "1", "yes", "on"}
        else:
            kwargs[field_name] = cast_fn(raw_value)
    return kwargs


def apply_backtest_defaults_from_preset(
    values: dict[str, Any],
    preset: CapitalPreset,
    *,
    explicit_flags: set[str],
) -> dict[str, Any]:
    updated = dict(values)
    preset_values = preset.values
    mapping = {
        "max_positions": ("risk_max_positions", int),
        "account_type": ("execution_account_type", str),
        "swing_only": ("execution_swing_only", bool),
        "cash_settlement_days": ("execution_cash_settlement_days", int),
        "commission_bps": ("backtesting_commission_bps_stress", float),
        "slippage_bps": ("backtesting_slippage_bps_stress", float),
        "max_sector_exposure_pct": ("backtesting_max_sector_exposure_pct", float),
        "max_entry_gap_pct": ("backtesting_max_entry_gap_pct", float),
        "dd_rolling_peak_window_days": ("backtesting_dd_rolling_peak_window_days", int),
        "dd_degraded_allocation_pct": ("backtesting_dd_degraded_allocation_pct", float),
    }
    for target_key, (preset_key, cast_fn) in mapping.items():
        if target_key in explicit_flags:
            continue
        if preset_key not in preset_values:
            continue
        raw_value = preset_values[preset_key]
        if cast_fn is bool:
            if isinstance(raw_value, bool):
                updated[target_key] = raw_value
            else:
                updated[target_key] = str(raw_value).strip().lower() in {"true", "1", "yes", "on"}
            continue
        if cast_fn is str:
            updated[target_key] = str(raw_value).strip().lower()
            continue
        updated[target_key] = cast_fn(raw_value)
    return updated


def build_capital_preset_executability_summary(
    preset: CapitalPreset,
    *,
    detected_equity: float | None = None,
) -> dict[str, Any]:
    values = dict(preset.values)
    account_type = str(values.get("execution_account_type", "cash") or "cash").strip().lower() or "cash"
    swing_only = bool(values.get("execution_swing_only", True))
    max_positions = int(values.get("risk_max_positions", 0) or 0)
    min_notional = float(values.get("risk_min_position_notional", 0.0) or 0.0)
    equity_value = float(detected_equity) if detected_equity is not None and detected_equity > 0 else None
    ticket_share_of_equity = (min_notional / equity_value) if equity_value else None
    recommended_commission_bps = float(
        values.get(
            "backtesting_commission_bps_stress",
            15.0 if account_type == "cash" and min_notional <= 200.0 else 10.0 if account_type == "cash" else 5.0,
        )
    )
    recommended_slippage_bps = float(
        values.get(
            "backtesting_slippage_bps_stress",
            25.0 if min_notional <= 200.0 else 18.0 if min_notional <= 350.0 else 10.0,
        )
    )
    recommended_live_max_portfolio_dd_pct = float(
        values.get(
            "risk_max_drawdown_pct",
            values.get("backtesting_max_portfolio_dd_pct", 0.15),
        )
    )
    recommended_live_max_daily_loss_pct = float(values.get("risk_max_daily_loss_pct", 0.05))
    recommended_live_target_annual_vol = float(
        values.get(
            "risk_target_annual_vol",
            values.get("backtesting_target_annual_vol", 0.0),
        )
    )
    recommended_live_min_ml_coverage_ratio = float(
        values.get(
            "risk_min_ml_coverage_ratio",
            values.get("backtesting_min_ml_coverage_ratio", 0.0),
        )
    )
    recommended_live_vol_target_lookback_days = int(values.get("risk_vol_target_lookback_days", 60) or 60)
    cash_settlement_days = int(
        values.get("execution_cash_settlement_days", 1 if account_type == "cash" else 0) or 0
    )
    ml_gate_policy = str(
        values.get(
            "risk_ml_gate_policy",
            "quant_only_on_ml_gate_disable" if float(values.get("risk_prediction_weight", 0.0) or 0.0) > 0 else "quant_only",
        )
    )
    warnings: list[str] = []
    if account_type == "cash" and cash_settlement_days > 0:
        warnings.append(f"compte cash : simulation règlement-livraison T+{cash_settlement_days}")
    if min_notional > 0:
        warnings.append(f"ticket minimal effectif {min_notional:,.0f} $")
    if ticket_share_of_equity is not None and ticket_share_of_equity >= 0.2:
        warnings.append(f"ticket mini ≈ {ticket_share_of_equity * 100:.1f}% de l'equity détectée")
    if swing_only:
        warnings.append("preset orienté swing : sorties intraday à éviter")
    return {
        "preset_key": preset.key,
        "account_type": account_type,
        "swing_only": swing_only,
        "cash_settlement_days": cash_settlement_days,
        "max_positions": max_positions,
        "min_position_notional": min_notional,
        "ticket_share_of_equity": float(ticket_share_of_equity) if ticket_share_of_equity is not None else None,
        "recommended_commission_bps_stress": recommended_commission_bps,
        "recommended_slippage_bps_stress": recommended_slippage_bps,
        "recommended_live_max_portfolio_dd_pct": recommended_live_max_portfolio_dd_pct,
        "recommended_live_max_daily_loss_pct": recommended_live_max_daily_loss_pct,
        "recommended_live_target_annual_vol": recommended_live_target_annual_vol,
        "recommended_live_min_ml_coverage_ratio": recommended_live_min_ml_coverage_ratio,
        "recommended_live_vol_target_lookback_days": recommended_live_vol_target_lookback_days,
        "ml_gate_policy": ml_gate_policy,
        "warnings": warnings,
    }


__all__ = [
    "CAPITAL_PRESETS_CONFIG_PATH",
    "DEFAULT_CAPITAL_PRESET_KEY",
    "DETECTED_EQUITY_PLACEHOLDER",
    "CapitalPreset",
    "apply_backtest_defaults_from_preset",
    "build_risk_config_kwargs_from_preset",
    "build_capital_preset_executability_summary",
    "build_screener_config_kwargs_from_preset",
    "build_selector_config_kwargs_from_preset",
    "capital_preset_fingerprint",
    "get_capital_preset_by_key",
    "get_default_capital_preset",
    "load_capital_presets",
    "require_capital_preset",
    "resolve_capital_preset_for_equity",
    "resolve_effective_capital_preset",
]
