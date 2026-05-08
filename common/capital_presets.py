"""Presets de capital partagés entre IHM pipeline et backtesting."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CAPITAL_PRESETS_CONFIG_PATH = PROJECT_ROOT / "config" / "capital_presets.yaml"
DETECTED_EQUITY_PLACEHOLDER = "__DETECTED_EQUITY__"
DEFAULT_CAPITAL_PRESET_KEY = "capital_50001_100000"


@dataclass(frozen=True, slots=True)
class CapitalPreset:
    key: str
    label: str
    description: str
    min_equity: float
    max_equity: float | None
    values: dict[str, Any]

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
            session_key = option_key if option_key.startswith("pipeline_") else f"pipeline_{option_key}"
            if raw_value == DETECTED_EQUITY_PLACEHOLDER:
                if detected_equity is None or detected_equity <= 0:
                    continue
                payload[session_key] = float(detected_equity)
                continue
            payload[session_key] = _normalize_option_value(option_key, raw_value)
        return payload


def _normalize_option_value(option_key: str, raw_value: Any) -> Any:
    if option_key.endswith("execution_pdt_rule"):
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

        presets.append(
            CapitalPreset(
                key=key,
                label=label,
                description=description,
                min_equity=min_equity,
                max_equity=max_equity,
                values=values,
            )
        )
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
    return {
        "liquidity_threshold_usd": float(values.get("screener_liquidity_threshold_usd", 10_000_000.0)),
        "min_relative_strength_index": float(values.get("screener_min_relative_strength_index", 100.0)),
        "historical_range_lookback_days": int(values.get("screener_historical_range_lookback_days", 504)),
        "min_historical_range_score": float(values.get("screener_min_historical_range_score", 70.0)),
        "first_pass_window_days": int(values.get("screener_first_pass_window_days", 400)),
    }


def build_selector_config_kwargs_from_preset(preset: CapitalPreset) -> dict[str, Any]:
    values = preset.values
    return {
        "selection_size": int(values.get("selector_selection_size", 50)),
        "sector_cap_ratio": float(values.get("selector_sector_cap_ratio", 0.28)),
        "liquidity_threshold": float(values.get("selector_liquidity_threshold", 30_000_000.0)),
        "min_close": float(values.get("selector_min_close", 10.0)),
        "max_volatility_ratio": float(values.get("selector_max_volatility_ratio", 0.9)),
        "min_relative_strength_index": float(values.get("selector_min_relative_strength_index", 100.0)),
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
        "pdt_rule": ("execution_pdt_rule", str),
        "swing_only": ("execution_swing_only", bool),
    }
    for target_key, (preset_key, cast_fn) in mapping.items():
        if target_key in explicit_flags:
            continue
        if preset_key not in preset_values:
            continue
        updated[target_key] = cast_fn(preset_values[preset_key])
    return updated


__all__ = [
    "CAPITAL_PRESETS_CONFIG_PATH",
    "DEFAULT_CAPITAL_PRESET_KEY",
    "DETECTED_EQUITY_PLACEHOLDER",
    "CapitalPreset",
    "apply_backtest_defaults_from_preset",
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
