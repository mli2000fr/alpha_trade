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


def calibrator_from_state_dict(state: dict[str, Any] | None) -> PlattCalibrator | None:
	if not state:
		return None
	if state.get("method") != "platt":
		return None
	return PlattCalibrator.from_state_dict(state)


