"""Session HTTPS vérifiée avec les autorités du système (Windows inclus).

Requests utilise normalement certifi, qui peut manquer l'autorité d'une
installation Windows. Ce transport conserve CERT_REQUIRED et hostname check.
"""
from __future__ import annotations

import ssl

import requests
from requests.adapters import HTTPAdapter


class SystemTrustAdapter(HTTPAdapter):
    def __init__(self, **kwargs):
        self.ssl_context = ssl.create_default_context()
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)


def verified_system_session() -> requests.Session:
    session = requests.Session()
    session.mount("https://", SystemTrustAdapter())
    return session
