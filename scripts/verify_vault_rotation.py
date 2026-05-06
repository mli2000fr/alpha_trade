"""Sprint S21.2 — Vérifie la rotation Vault (≤ 90 j).

Usage::

    python scripts/verify_vault_rotation.py KEY1 KEY2 ...
    python scripts/verify_vault_rotation.py --max-age-days 90 KEY1

Codes de retour :
    0 — toutes les clés respectent la rotation.
    2 — au moins une clé a une dernière version > ``max-age-days`` jours.
    3 — au moins une clé est introuvable.

Un rapport JSON est écrit dans
``artifacts/vault_rotation/<UTC-YYYYMMDDTHHMMSS>.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common.config_vault import (
    DEFAULT_VAULT_DIR,
    EnvFallbackVault,
    HashiCorpVault,
    RETENTION_DAYS,
    build_vault_from_env,
)


def _latest_version_age_days(vault: Any, key: str) -> tuple[int | None, float | None]:
    """Retourne ``(version, age_days)`` pour la dernière version connue de ``key``.

    Si la clé est introuvable retourne ``(None, None)``.
    """
    versions = vault.list_versions(key)
    if not versions:
        return None, None
    latest = max(versions)
    # On essaie de lire la métadonnée ``stored_at`` du fichier (EnvFallbackVault).
    stored_at: datetime | None = None
    if isinstance(vault, EnvFallbackVault):
        path = vault.root / "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in key
        ) / f"v{latest}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stored_at = datetime.fromisoformat(payload["stored_at"])
        except Exception:
            try:
                stored_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                stored_at = None
    elif isinstance(vault, HashiCorpVault) and getattr(vault, "_client", None) is not None:
        try:
            meta = vault._client.secrets.kv.v2.read_secret_metadata(  # noqa: SLF001
                path=vault._path(key), mount_point=vault.mount_point,  # noqa: SLF001
            )
            ts = meta["data"]["versions"][str(latest)]["created_time"]
            stored_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            stored_at = None

    if stored_at is None:
        return latest, None
    if stored_at.tzinfo is None:
        stored_at = stored_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - stored_at).total_seconds() / 86400.0
    return latest, age


def verify(
    keys: list[str],
    *,
    max_age_days: int = RETENTION_DAYS,
    vault: Any | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Audit de rotation. Retourne le rapport et écrit le JSON sur disque."""
    vault = vault or build_vault_from_env()
    report: dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "max_age_days": int(max_age_days),
        "keys": [],
        "status": "ok",
    }
    failed = False
    missing = False
    for key in keys:
        version, age = _latest_version_age_days(vault, key)
        entry: dict[str, Any] = {"key": key, "version": version, "age_days": age}
        if version is None:
            entry["status"] = "missing"
            missing = True
        elif age is not None and age > max_age_days:
            entry["status"] = "expired"
            failed = True
        else:
            entry["status"] = "ok"
        report["keys"].append(entry)

    if failed:
        report["status"] = "expired"
    elif missing:
        report["status"] = "missing"

    out_dir = output_dir or (Path("artifacts") / "vault_rotation")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = out_dir / f"{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vérifie la rotation des secrets Vault.")
    parser.add_argument("keys", nargs="+", help="Clés à vérifier.")
    parser.add_argument("--max-age-days", type=int, default=RETENTION_DAYS)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir) if args.output_dir else None
    report = verify(args.keys, max_age_days=args.max_age_days, output_dir=out_dir)
    print(json.dumps(report, indent=2, sort_keys=True))

    if report["status"] == "expired":
        return 2
    if report["status"] == "missing":
        return 3
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

