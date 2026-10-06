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


def probabilities_to_pseudo_logits(probabilities: np.ndarray) -> np.ndarray:
    """Convertit des probabilités multiclasse en pseudo-logits stables.

    Les modèles tabulaires n'exposent que ``predict_proba``. Les calibrateurs
    Temperature/Vector Scaling étant entraînés dans l'espace des logits, le
    serving doit reproduire la même transformation logarithmique.
    """
    proba = np.asarray(probabilities, dtype=np.float64)
    if proba.ndim != 2 or proba.shape[1] < 2:
        raise ValueError(f"multiclass probabilities must be 2-D, got {proba.shape}")
    if not np.isfinite(proba).all() or (proba < 0.0).any():
        raise ValueError("multiclass probabilities must be finite and non-negative")
    row_sums = proba.sum(axis=1, keepdims=True)
    if (row_sums <= 0.0).any():
        raise ValueError("multiclass probability rows must have a positive sum")
    normalized = proba / row_sums
    return np.log(np.clip(normalized, 1e-8, 1.0))


def calibrator_from_state_dict(state: dict[str, Any] | None) -> PlattCalibrator | TemperatureScaler | VectorScaler | None:
    if not state:
        return None
    method = state.get("method")
    if method == "platt":
        return PlattCalibrator.from_state_dict(state)
    if method == "temperature":
        return TemperatureScaler.from_state_dict(state)
    if method == "vector":
        return VectorScaler.from_state_dict(state)
    return None


# ---------------------------------------------------------------------------
# Temperature Scaling — calibration multi-classe (ternaire)
# ---------------------------------------------------------------------------

def _positive_temperature(value: float) -> float:
    temperature = float(value)
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("calibration temperature must be finite and strictly positive")
    return temperature


def _multiclass_logits(values: np.ndarray | torch.Tensor) -> torch.Tensor:
    x = (values.detach().cpu().to(dtype=torch.float64) if isinstance(values, torch.Tensor)
         else torch.as_tensor(np.asarray(values, dtype=np.float64)))
    if x.ndim != 2 or x.shape[1] < 2 or not torch.isfinite(x).all():
        raise ValueError("calibration logits must be finite with shape [N, C>=2]")
    return x


def _multiclass_labels(labels: np.ndarray, x: torch.Tensor) -> torch.Tensor:
    values = np.asarray(labels)
    if (values.ndim != 1 or len(values) != len(x) or not np.isfinite(values).all()
            or not np.equal(values, np.floor(values)).all()
            or (values < 0).any() or (values >= x.shape[1]).any()):
        raise ValueError("calibration labels must be class indices matching logits")
    return torch.as_tensor(values, dtype=torch.int64)


def _vector_biases(values: np.ndarray | None, classes: int | None = None) -> np.ndarray | None:
    if values is None:
        return None
    biases = np.asarray(values, dtype=np.float64)
    if (biases.ndim != 1 or len(biases) < 2 or not np.isfinite(biases).all()
            or (classes is not None and len(biases) != classes)):
        raise ValueError("calibration biases must be finite and match class count")
    return biases

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

	def __post_init__(self) -> None:
		self.temperature = _positive_temperature(self.temperature)

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
		x = _multiclass_logits(logits)
		y = _multiclass_labels(labels, x)
		if len(x) < 2:
			return self
		unique = torch.unique(y)
		if unique.numel() < 2:
			return self

		# Optimize log(T): the fit and serving formulas share the same positive T.
		log_temperature = torch.tensor(np.log(_positive_temperature(self.temperature)), dtype=torch.float64, requires_grad=True)
		optimizer = torch.optim.LBFGS(
			[log_temperature], max_iter=self.max_iter, line_search_fn="strong_wolfe",
		)

		def closure() -> torch.Tensor:
			optimizer.zero_grad()
			temperature = log_temperature.exp()
			_positive_temperature(temperature.detach().item())
			loss = F.cross_entropy(x / temperature, y)
			if not torch.isfinite(loss):
				raise ValueError("non-finite temperature calibration loss")
			loss.backward()
			return loss

		optimizer.step(closure)
		self.temperature = _positive_temperature(log_temperature.detach().exp().item())
		self.fitted = True
		return self

	def predict(self, logits: np.ndarray | torch.Tensor) -> np.ndarray:
		"""Retourne les probabilités calibrées [N, C].

		Parameters
		----------
		logits : np.ndarray or torch.Tensor [N, C]
			Logits bruts du modèle.
		"""
		x = _multiclass_logits(logits)
		t = _positive_temperature(self.temperature)
		result = F.softmax(x / t, dim=1)
		if not torch.isfinite(result).all():
			raise ValueError("non-finite temperature calibration output")
		return result.numpy()

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


# ---------------------------------------------------------------------------
# Vector Scaling — calibration multi-classe avec correction du biais
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class VectorScaler:
    """Vector Scaling pour calibration multi-classe avec correction du biais.

    Contrairement au TemperatureScaler (1 seul paramètre T), le VectorScaler
    ajoute un biais par classe, ce qui permet de corriger une tendance
    systématique à sur-prédire ou sous-prédire certaines classes.

    .. math::
        P_{calibré}(y=i | z) = \\frac{\\exp(z_i / T + b_i)}{\\sum_j \\exp(z_j / T + b_j)}

    - T : température globale (adoucit/durcit)
    - b_i : biais par classe (corrige la sur/sous-prédiction)

    Avec la contrainte sum(b_i) = 0 pour l'identifiabilité.

    Parameters
    ----------
    temperature : float
        Température (défaut 1.0).
    biases : np.ndarray [C]
        Biais par classe, initialisés à 0.
    max_iter : int
        Nombre maximum d'itérations LBFGS.
    """

    temperature: float = 1.0
    biases: np.ndarray | None = None  # [num_classes]
    fitted: bool = False
    max_iter: int = 100

    def __post_init__(self) -> None:
        self.temperature = _positive_temperature(self.temperature)
        self.biases = _vector_biases(self.biases)

    @property
    def method(self) -> str:
        return "vector"

    def fit(self, logits: np.ndarray, labels: np.ndarray) -> "VectorScaler":
        """Optimise T et b_i sur le set de validation via NLL loss.

        Parameters
        ----------
        logits : np.ndarray [N, C]
            Logits bruts du modèle (avant softmax).
        labels : np.ndarray [N]
            Indices de classe (0, 1, 2, ...).
        """
        x = _multiclass_logits(logits)
        y = _multiclass_labels(labels, x)
        if len(x) < 2:
            return self
        unique = torch.unique(y)
        if unique.numel() < 2:
            return self

        num_classes = x.shape[1]
        # Initialisation : T=1.0, b_i=0 avec contrainte sum(b)=0
        log_temperature = torch.tensor(np.log(_positive_temperature(self.temperature)), dtype=torch.float64, requires_grad=True)
        biases = torch.zeros(num_classes, dtype=torch.float64, requires_grad=True)
        params = [log_temperature, biases]
        optimizer = torch.optim.LBFGS(
            params, max_iter=self.max_iter, line_search_fn="strong_wolfe",
        )

        def closure() -> torch.Tensor:
            optimizer.zero_grad()
            # Centrer les biais pour l'identifiabilité (sum b_i = 0)
            centered_biases = biases - biases.mean()
            temperature = log_temperature.exp()
            _positive_temperature(temperature.detach().item())
            scaled = x / temperature + centered_biases.unsqueeze(0)
            loss = F.cross_entropy(scaled, y)
            if not torch.isfinite(loss):
                raise ValueError("non-finite vector calibration loss")
            loss.backward()
            return loss

        optimizer.step(closure)
        with torch.no_grad():
            fitted_temperature = _positive_temperature(log_temperature.detach().exp().item())
            fitted_biases = _vector_biases(biases.detach().cpu().numpy().copy(), num_classes)
            self.temperature = fitted_temperature
            self.biases = fitted_biases
        self.fitted = True
        return self

    def predict(self, logits: np.ndarray | torch.Tensor) -> np.ndarray:
        """Retourne les probabilités calibrées [N, C].

        Parameters
        ----------
        logits : np.ndarray or torch.Tensor [N, C]
            Logits bruts du modèle.
        """
        x = _multiclass_logits(logits)
        t = _positive_temperature(self.temperature)
        biases = _vector_biases(self.biases, x.shape[1])
        b = torch.as_tensor(
            biases if biases is not None else np.zeros(x.shape[1], dtype=np.float64)
        )
        # Centrer les biais pour la prédiction
        b_centered = b - b.mean()
        result = F.softmax(x / t + b_centered.unsqueeze(0), dim=1)
        if not torch.isfinite(result).all():
            raise ValueError("non-finite vector calibration output")
        return result.numpy()

    def predict_proba(self, logits: np.ndarray | torch.Tensor) -> np.ndarray:
        """Alias pour compatibilité avec PlattCalibrator / TemperatureScaler."""
        return self.predict(logits)

    def state_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "temperature": self.temperature,
            "biases": self.biases.tolist() if self.biases is not None else None,
            "fitted": self.fitted,
            "max_iter": self.max_iter,
        }

    @classmethod
    def from_state_dict(cls, state: dict[str, Any]) -> "VectorScaler":
        biases = state.get("biases")
        return cls(
            temperature=float(state.get("temperature", 1.0)),
            biases=np.array(biases, dtype=np.float64) if biases is not None else None,
            fitted=bool(state.get("fitted", False)),
            max_iter=int(state.get("max_iter", 100)),
        )
