"""Presets de capital IHM pour préremplir Risk / Execution / Selector."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAPITAL_PRESETS_CONFIG_PATH = PROJECT_ROOT / "config" / "capital_presets.yaml"
DETECTED_EQUITY_PLACEHOLDER = "__DETECTED_EQUITY__"


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


__all__ = [
	"CAPITAL_PRESETS_CONFIG_PATH",
	"DETECTED_EQUITY_PLACEHOLDER",
	"CapitalPreset",
	"get_capital_preset_by_key",
	"load_capital_presets",
	"resolve_capital_preset_for_equity",
]


