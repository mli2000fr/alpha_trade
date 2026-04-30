"""
backtesting/run_metadata.py
============================
Phase A.4 (refactor/backtesting/audit_plan.md) — collecte de métadonnées de
reproductibilité injectées dans ``report.json["run_metadata"]`` :

- ``git_commit_sha`` (HEAD courant si disponible)
- ``git_dirty`` (True si working tree modifié)
- ``python_version``
- ``platform``
- ``packages`` (versions de pandas/numpy/vectorbt si importés)
- ``dataset_hash`` (md5 d'une portée canonique d'OHLCV/scores)
- ``seed`` (graine fournie par le caller, sinon None)
- ``generated_at_utc``
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import platform
import subprocess
import sys
from typing import Any, Iterable, Mapping

import pandas as pd

LOGGER = logging.getLogger(__name__)


def _safe_git_command(args: list[str]) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", *args],
            stderr=subprocess.DEVNULL,
            timeout=2.0,
        )
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return None


def collect_git_info() -> dict[str, Any]:
    sha = _safe_git_command(["rev-parse", "HEAD"]) or None
    branch = _safe_git_command(["rev-parse", "--abbrev-ref", "HEAD"]) or None
    dirty_status = _safe_git_command(["status", "--porcelain"])
    dirty = bool(dirty_status) if dirty_status is not None else None
    return {"git_commit_sha": sha, "git_branch": branch, "git_dirty": dirty}


def collect_environment_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
    }
    packages: dict[str, str] = {}
    for pkg_name in ("pandas", "numpy", "vectorbt", "sqlalchemy"):
        try:
            mod = __import__(pkg_name)
            packages[pkg_name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            continue
    info["packages"] = packages
    return info


def hash_dataset(frames: Mapping[str, pd.DataFrame | pd.Series | None]) -> str:
    """Produit un hash md5 stable d'un petit dictionnaire de frames.

    On hash uniquement la **forme** + un échantillon canonique pour rester
    rapide même sur 10 ans × 5000 symboles.
    """
    hasher = hashlib.md5()
    for name in sorted(frames):
        frame = frames[name]
        if frame is None:
            hasher.update(f"{name}:none\n".encode())
            continue
        try:
            shape = getattr(frame, "shape", None)
            hasher.update(f"{name}:{shape}\n".encode())
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                # Premier + dernier index + somme des valeurs numériques.
                first_idx = str(frame.index[0])
                last_idx = str(frame.index[-1])
                hasher.update(f"{first_idx}|{last_idx}\n".encode())
                num = frame.select_dtypes(include="number")
                if not num.empty:
                    digest = float(num.to_numpy(dtype=float, na_value=0.0).sum())
                    hasher.update(f"{digest:.6f}\n".encode())
            elif isinstance(frame, pd.Series) and not frame.empty:
                hasher.update(f"{frame.iloc[0]}|{frame.iloc[-1]}\n".encode())
        except Exception as exc:  # pragma: no cover - défensif
            LOGGER.debug("hash_dataset partial failure (%s): %s", name, exc)
            hasher.update(f"{name}:err\n".encode())
    return hasher.hexdigest()


def build_run_metadata(
    *,
    seed: int | None = None,
    dataset_frames: Mapping[str, pd.DataFrame | pd.Series | None] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Construit le bloc ``run_metadata`` injecté dans ``report.json``."""
    payload: dict[str, Any] = {
        "generated_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "seed": seed,
    }
    payload.update(collect_git_info())
    payload.update(collect_environment_info())
    if dataset_frames:
        payload["dataset_hash"] = hash_dataset(dataset_frames)
    if extra:
        payload["extra"] = dict(extra)
    return payload


__all__ = [
    "build_run_metadata",
    "collect_environment_info",
    "collect_git_info",
    "hash_dataset",
]

