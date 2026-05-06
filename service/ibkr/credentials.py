"""Sprint S13.2 — Lecture des credentials IBKR depuis l'environnement / vault."""
from __future__ import annotations

import os
from dataclasses import dataclass

ENV_HOST = "IBKR_HOST"
ENV_PORT = "IBKR_PORT"
ENV_CLIENT_ID = "IBKR_CLIENT_ID"


@dataclass(frozen=True, slots=True)
class IBKRCredentials:
    host: str
    port: int
    client_id: int


def get_ibkr_credentials() -> IBKRCredentials:
    """Lit l'env (fallback values = TWS paper local par défaut)."""
    return IBKRCredentials(
        host=os.getenv(ENV_HOST, "127.0.0.1"),
        port=int(os.getenv(ENV_PORT, "7497")),
        client_id=int(os.getenv(ENV_CLIENT_ID, "1")),
    )


__all__ = ["IBKRCredentials", "get_ibkr_credentials", "ENV_HOST", "ENV_PORT", "ENV_CLIENT_ID"]

