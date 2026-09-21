from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from service.tushare.errors import TushareAuthenticationError


@dataclass(frozen=True, slots=True)
class TushareAccount:
    token: str
    token_env: str

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.token.encode()).hexdigest()[:12]


def load_account(token_env: str = "TUSHARE_TOKEN") -> TushareAccount:
    token = os.getenv(token_env, "").strip()
    if not token:
        raise TushareAuthenticationError(
            f"Token Tushare absent : définir la variable d'environnement {token_env}"
        )
    return TushareAccount(token=token, token_env=token_env)


__all__ = ["TushareAccount", "load_account"]
