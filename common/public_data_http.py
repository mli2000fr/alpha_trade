"""Verified HTTPS for official public data; never disables certificate checks."""
import ssl

import requests
from requests.adapters import HTTPAdapter


class SystemTrustAdapter(HTTPAdapter):
    def __init__(self, **kwargs):
        self.ssl_context = ssl.create_default_context()
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)


def verified_session():
    session = requests.Session()
    session.mount('https://', SystemTrustAdapter())
    session.headers['User-Agent'] = 'AlphaTrade-public-macro/1.0 (personal research)'
    return session
