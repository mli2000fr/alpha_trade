"""Requests session using verified Certifi + Windows roots, never verify=False."""
import ssl
import certifi
import requests


def verified_context():
    context = ssl.create_default_context(cafile=certifi.where())
    enum = getattr(ssl, 'enum_certificates', None)
    if enum:
        for certificate, encoding, _trust in enum('ROOT'):
            if encoding == 'x509_asn':
                try:
                    context.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(certificate))
                except ssl.SSLError:
                    continue
    return context


class VerifiedTLSAdapter(requests.adapters.HTTPAdapter):
    def __init__(self):
        self.context = verified_context()
        super().__init__(max_retries=0)

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        if verify is False:
            raise ValueError('Désactiver TLS est interdit')
        host, pool = super().build_connection_pool_key_attributes(request, verify, cert)
        if verify is True:
            pool['ssl_context'] = self.context
        return host, pool


def verified_session():
    session = requests.Session()
    session.mount('https://', VerifiedTLSAdapter())
    return session
