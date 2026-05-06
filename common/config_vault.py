"""Sprint S12.5 — Backup configuration via secret manager.

Interface :class:`ConfigVault` (Protocol) + deux implémentations :

- :class:`EnvFallbackVault` : lit ``os.environ`` et stocke les versions
  successives sous ``artifacts/config_vault/<key>/<vN>.json`` (audit trail
  local). Utilisable hors-ligne (CI, dev).
- :class:`HashiCorpVault` : optionnel, requiert ``hvac``. Bascule
  automatiquement sur :class:`EnvFallbackVault` si la dépendance ou la
  connexion échoue.

La rotation crée une nouvelle version du secret et conserve la précédente
pour 90 j (politique audit_global §S12.5).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol, runtime_checkable

LOGGER = logging.getLogger(__name__)

DEFAULT_VAULT_DIR = Path("artifacts") / "config_vault"
RETENTION_DAYS = 90


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


@runtime_checkable
class ConfigVault(Protocol):
    """Contrat minimal d'un coffre de configuration versionné."""

    def get(self, key: str, *, version: int | None = None) -> str | None: ...

    def put(self, key: str, value: str) -> int: ...

    def list_versions(self, key: str) -> list[int]: ...

    def rotate(self, key: str, new_value: str) -> int: ...


# ---------------------------------------------------------------------------
# Implémentation locale (fallback CI / dev)
# ---------------------------------------------------------------------------


@dataclass
class EnvFallbackVault:
    """Vault local : lit l'environnement, stocke les versions sur disque.

    - ``get(key)`` sans version : retourne ``os.environ[key]`` si défini,
      sinon la dernière version persistée.
    - ``get(key, version=N)`` : lit la version N depuis le disque.
    """

    root: Path = field(default_factory=lambda: DEFAULT_VAULT_DIR)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- helpers -------------------------------------------------------

    def _key_dir(self, key: str) -> Path:
        d = self.root / _safe(key)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _version_files(self, key: str) -> list[tuple[int, Path]]:
        out: list[tuple[int, Path]] = []
        for p in self._key_dir(key).glob("v*.json"):
            try:
                v = int(p.stem.lstrip("v"))
                out.append((v, p))
            except ValueError:
                continue
        out.sort()
        return out

    # ---- API -----------------------------------------------------------

    def get(self, key: str, *, version: int | None = None) -> str | None:
        if version is None:
            env_val = os.getenv(key)
            if env_val is not None:
                return env_val
            versions = self._version_files(key)
            if not versions:
                return None
            target = versions[-1][1]
        else:
            target = self._key_dir(key) / f"v{version}.json"
            if not target.exists():
                return None
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            return str(payload.get("value", ""))
        except Exception:  # noqa: BLE001
            LOGGER.warning("Vault read failed for %s v=%s", key, version, exc_info=True)
            return None

    def put(self, key: str, value: str) -> int:
        existing = self._version_files(key)
        next_version = (existing[-1][0] + 1) if existing else 1
        payload = {
            "value": value,
            "version": next_version,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        path = self._key_dir(key) / f"v{next_version}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return next_version

    def list_versions(self, key: str) -> list[int]:
        return [v for v, _ in self._version_files(key)]

    def rotate(self, key: str, new_value: str) -> int:
        new_version = self.put(key, new_value)
        self._purge_expired(key)
        return new_version

    def _purge_expired(self, key: str) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - RETENTION_DAYS * 86400
        for _, path in self._version_files(key)[:-1]:  # garde la dernière
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover
                continue


# ---------------------------------------------------------------------------
# Implémentation HashiCorp Vault (optionnelle)
# ---------------------------------------------------------------------------


@dataclass
class HashiCorpVault:
    """Wrapper sur ``hvac`` avec fallback automatique sur ``EnvFallbackVault``.

    Activé via env ``ALPHA_TRADE_VAULT_ADDR`` + ``ALPHA_TRADE_VAULT_TOKEN``.
    """

    address: str
    token: str
    mount_point: str = "secret"
    fallback: ConfigVault = field(default_factory=EnvFallbackVault)
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            import hvac  # type: ignore[import-not-found]

            self._client = hvac.Client(url=self.address, token=self.token)
            if not self._client.is_authenticated():
                raise RuntimeError("hvac client not authenticated")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("HashiCorpVault indisponible (%s) — fallback env.", exc)
            self._client = None

    def _path(self, key: str) -> str:
        return f"alpha_trade/{key}"

    def get(self, key: str, *, version: int | None = None) -> str | None:
        if self._client is None:
            return self.fallback.get(key, version=version)
        try:
            resp = self._client.secrets.kv.v2.read_secret_version(
                path=self._path(key), version=version, mount_point=self.mount_point,
            )
            return str(resp["data"]["data"].get("value"))
        except Exception:  # noqa: BLE001
            return self.fallback.get(key, version=version)

    def put(self, key: str, value: str) -> int:
        if self._client is None:
            return self.fallback.put(key, value)
        resp = self._client.secrets.kv.v2.create_or_update_secret(
            path=self._path(key), secret={"value": value}, mount_point=self.mount_point,
        )
        return int(resp["data"]["version"])

    def list_versions(self, key: str) -> list[int]:
        if self._client is None:
            return self.fallback.list_versions(key)
        try:
            meta = self._client.secrets.kv.v2.read_secret_metadata(
                path=self._path(key), mount_point=self.mount_point,
            )
            return sorted(int(v) for v in meta["data"]["versions"].keys())
        except Exception:  # noqa: BLE001
            return self.fallback.list_versions(key)

    def rotate(self, key: str, new_value: str) -> int:
        return self.put(key, new_value)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_vault_from_env() -> ConfigVault:
    """Sélectionne l'implémentation selon l'environnement."""
    addr = os.getenv("ALPHA_TRADE_VAULT_ADDR")
    token = os.getenv("ALPHA_TRADE_VAULT_TOKEN")
    if addr and token:
        return HashiCorpVault(address=addr, token=token)
    return EnvFallbackVault()


def _safe(key: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in key)


__all__ = [
    "ConfigVault",
    "EnvFallbackVault",
    "HashiCorpVault",
    "build_vault_from_env",
    "DEFAULT_VAULT_DIR",
    "RETENTION_DAYS",
]

