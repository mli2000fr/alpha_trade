"""modelFactory/calibration.py — Calibration légère des probabilités."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F


def margin_from_logits(logits: np.ndarray | torch.Tensor) -> np.ndarray:
	"""Retourne le margin binaire logit_pos - logit_neg."""
	if isinstance(logits, torch.Tensor):
		arr = logits.detach().cpu().numpy()
	else:
		arr = np.asarray(logits)
	if arr.ndim == 2 and arr.shape[1] == 2:
		return (arr[:, 1] - arr[:, 0]).astype(np.float64)
	return arr.reshape(-1).astype(np.float64)


@dataclass(slots=True)
class PlattCalibrator:
	"""Calibrateur sigmoid de type Platt scaling."""

	slope: float = 1.0
	intercept: float = 0.0
	fitted: bool = False
	max_iter: int = 100

	@property
	def method(self) -> str:
		return "platt"

	def fit(self, margins: np.ndarray, targets: np.ndarray) -> "PlattCalibrator":
		x = torch.as_tensor(np.asarray(margins, dtype=np.float32).reshape(-1))
		y = torch.as_tensor(np.asarray(targets, dtype=np.float32).reshape(-1))
		if x.numel() < 2:
			return self
		unique = torch.unique(y)
		if unique.numel() < 2:
			return self

		slope = torch.tensor(self.slope, dtype=torch.float32, requires_grad=True)
		intercept = torch.tensor(self.intercept, dtype=torch.float32, requires_grad=True)
		optimizer = torch.optim.LBFGS([slope, intercept], max_iter=self.max_iter, line_search_fn="strong_wolfe")

		def closure() -> torch.Tensor:
			optimizer.zero_grad()
			logits = slope * x + intercept
			loss = F.binary_cross_entropy_with_logits(logits, y)
			loss.backward()
			return loss

		optimizer.step(closure)
		self.slope = float(slope.detach().cpu().item())
		self.intercept = float(intercept.detach().cpu().item())
		self.fitted = True
		return self

	def predict_proba(self, margins: np.ndarray | torch.Tensor) -> np.ndarray:
		x = np.asarray(margins_from_logits_or_margin(margins), dtype=np.float64)
		z = np.clip(self.slope * x + self.intercept, -50.0, 50.0)
		return 1.0 / (1.0 + np.exp(-z))

	def state_dict(self) -> dict[str, Any]:
		return {
			"method": self.method,
			"slope": self.slope,
			"intercept": self.intercept,
			"fitted": self.fitted,
			"max_iter": self.max_iter,
		}

	@classmethod
	def from_state_dict(cls, state: dict[str, Any]) -> "PlattCalibrator":
		return cls(
			slope=float(state.get("slope", 1.0)),
			intercept=float(state.get("intercept", 0.0)),
			fitted=bool(state.get("fitted", False)),
			max_iter=int(state.get("max_iter", 100)),
		)


def margins_from_logits_or_margin(values: np.ndarray | torch.Tensor) -> np.ndarray:
	"""Accepte un tableau de logits [N,2] ou déjà un margin [N]."""
	if isinstance(values, torch.Tensor):
		arr = values.detach().cpu().numpy()
	else:
		arr = np.asarray(values)
	if arr.ndim == 2:
		return margin_from_logits(arr)
	return arr.reshape(-1).astype(np.float64)


def calibrator_from_state_dict(state: dict[str, Any] | None) -> PlattCalibrator | TemperatureScaler | None:
	if not state:
		return None
	method = state.get("method")
	if method == "platt":
		return PlattCalibrator.from_state_dict(state)
	if method == "temperature":
		return TemperatureScaler.from_state_dict(state)
	return None


# ---------------------------------------------------------------------------
# Temperature Scaling — calibration multi-classe (ternaire)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TemperatureScaler:
	"""Temperature Scaling pour calibration multi-classe (ternaire / N classes).

	Contrairement à Platt (binaire, travaille sur une marge),
	le Temperature Scaling applique un seul paramètre T à TOUS les
	logits avant softmax, ce qui le rend natif multi-classe.

	.. math::
		P_{calibré}(y=i | z) = \\frac{\\exp(z_i / T)}{\\sum_j \\exp(z_j / T)}

	- T > 1 : adoucit les probabilités (modèle trop confiant)
	- T < 1 : durcit les probabilités (modèle pas assez confiant)
	- T = 1 : softmax standard (aucun changement)

	Parameters
	----------
	temperature : float
		Température initiale (défaut 1.0 = pas de changement).
	max_iter : int
		Nombre maximum d'itérations LBFGS.
	"""

	temperature: float = 1.0
	fitted: bool = False
	max_iter: int = 100

	@property
	def method(self) -> str:
		return "temperature"

	def fit(self, logits: np.ndarray, labels: np.ndarray) -> "TemperatureScaler":
		"""Optimise T sur le set de validation via NLL loss.

		Parameters
		----------
		logits : np.ndarray [N, C]
			Logits bruts du modèle (avant softmax).
		labels : np.ndarray [N]
			Indices de classe (0, 1, 2, ...).
		"""
		x = torch.as_tensor(np.asarray(logits, dtype=np.float32))
		y = torch.as_tensor(np.asarray(labels, dtype=np.int64))
		if x.numel() < 2 or x.ndim < 2:
			return self
		unique = torch.unique(y)
		if unique.numel() < 2:
			return self

		temperature = torch.tensor(self.temperature, dtype=torch.float32, requires_grad=True)
		optimizer = torch.optim.LBFGS(
			[temperature], max_iter=self.max_iter, line_search_fn="strong_wolfe",
		)

		def closure() -> torch.Tensor:
			optimizer.zero_grad()
			loss = F.cross_entropy(x / temperature, y)
			loss.backward()
			return loss

		optimizer.step(closure)
		self.temperature = float(temperature.detach().cpu().item())
		self.fitted = True
		return self

	def predict(self, logits: np.ndarray | torch.Tensor) -> np.ndarray:
		"""Retourne les probabilités calibrées [N, C].

		Parameters
		----------
		logits : np.ndarray or torch.Tensor [N, C]
			Logits bruts du modèle.
		"""
		if isinstance(logits, torch.Tensor):
			x = logits.detach().cpu()
		else:
			x = torch.as_tensor(np.asarray(logits, dtype=np.float32))
		t = max(self.temperature, 1e-6)  # protection division par zéro
		return F.softmax(x / t, dim=1).numpy()

	def predict_proba(self, logits: np.ndarray | torch.Tensor) -> np.ndarray:
		"""Alias pour compatibilité avec :class:`PlattCalibrator`."""
		return self.predict(logits)

	def state_dict(self) -> dict[str, Any]:
		return {
			"method": self.method,
			"temperature": self.temperature,
			"fitted": self.fitted,
			"max_iter": self.max_iter,
		}

	@classmethod
	def from_state_dict(cls, state: dict[str, Any]) -> "TemperatureScaler":
		return cls(
			temperature=float(state.get("temperature", 1.0)),
			fitted=bool(state.get("fitted", False)),
			max_iter=int(state.get("max_iter", 100)),
		)


