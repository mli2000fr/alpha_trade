"""Helpers de reproductibilité pour modelFactory."""
from __future__ import annotations

import hashlib
import os
import random
from typing import Any

import numpy as np
import torch

from modelFactory.config import ReproducibilityConfig

_MAX_NUMPY_SEED = 2 ** 32
_MAX_TORCH_SEED = 2 ** 63 - 1


def normalize_seed(seed: int) -> int:
    """Normalise un seed entier dans une plage stable et positive."""
    return int(seed) % _MAX_TORCH_SEED


def derive_seed(base_seed: int, *parts: object) -> int:
    """Dérive un seed stable à partir d'un seed racine et d'un contexte."""
    payload = "::".join([str(normalize_seed(base_seed)), *[str(part) for part in parts]])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % _MAX_TORCH_SEED


def seed_worker(base_seed: int, worker_id: int) -> None:
    """Initialise proprement un worker DataLoader."""
    worker_seed = derive_seed(base_seed, "worker", worker_id)
    random.seed(worker_seed)
    np.random.seed(worker_seed % _MAX_NUMPY_SEED)
    try:
        torch.manual_seed(worker_seed)
    except Exception:
        pass


def build_torch_generator(seed: int) -> torch.Generator:
    generator = torch.Generator()
    generator.manual_seed(normalize_seed(seed))
    return generator


def apply_reproducibility(config: ReproducibilityConfig, *, context: str | None = None) -> dict[str, Any]:
    """Applique la politique de reproductibilité au process courant."""
    resolved_seed = normalize_seed(config.seed)
    python_hash_seed = resolved_seed % _MAX_NUMPY_SEED
    os.environ["PYTHONHASHSEED"] = str(python_hash_seed)
    if config.deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

    random.seed(resolved_seed)
    np.random.seed(resolved_seed % _MAX_NUMPY_SEED)

    cuda_available = False
    try:
        torch.manual_seed(resolved_seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(resolved_seed)
            cuda_available = True
    except Exception:
        # CUDA peut être indisponible ou en erreur (ex: conflit multi-process,
        # GPU en mode exclusif, TDR Windows). On dégrade vers CPU.
        try:
            torch.manual_seed(resolved_seed)
        except Exception:
            pass

    cudnn_backend = getattr(torch.backends, "cudnn", None)
    if cudnn_backend is not None:
        try:
            cudnn_backend.deterministic = bool(config.deterministic)
            cudnn_backend.benchmark = False if config.deterministic else cudnn_backend.benchmark
        except Exception:
            pass

    deterministic_applied = False
    if cuda_available:
        try:
            torch.use_deterministic_algorithms(bool(config.deterministic))
            deterministic_applied = bool(config.deterministic)
        except Exception:
            deterministic_applied = False

    return {
        "seed": resolved_seed,
        "python_hash_seed": int(python_hash_seed),
        "deterministic_requested": bool(config.deterministic),
        "deterministic_applied": deterministic_applied,
        "context": context,
    }

