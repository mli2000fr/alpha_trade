"""Process-local Windows/system trust adapter; full certificate verification stays on.

No root certificates installed, no verify=False and no production config change.
"""
import argparse
import json
import ssl

from requests.adapters import HTTPAdapter

from scripts.research import us_news_event_pilot_collect as collect
from scripts.research import us_news_event_pilot_diagnostic as diagnostic
from scripts.research import us_news_event_qualification as qualification


class SystemTrustAdapter(HTTPAdapter):
    def __init__(self, **kwargs):
        self.context = ssl.create_default_context()
        if not self.context.check_hostname or self.context.verify_mode != ssl.CERT_REQUIRED:
            raise RuntimeError('Full certificate and hostname verification required')
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        return super().init_poolmanager(connections,maxsize,block,
            ssl_context=self.context,**kwargs)

    def build_connection_pool_key_attributes(self,request,verify,cert=None):
        if verify is False:
            raise RuntimeError('Disabling TLS verification is forbidden')
        host, attributes = super().build_connection_pool_key_attributes(request,verify,cert)
        attributes['ssl_context'] = self.context
        return host, attributes


class SystemTransport(collect.Transport):
    def proxy(self,session):
        session.mount('https://eodhd.com/',SystemTrustAdapter())
        return super().proxy(session)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnostic',action='store_true')
    parser.add_argument('--output',type=qualification.Path)
    args=parser.parse_args()
    if args.diagnostic:
        # Only this diagnostic function's session factory is supplied an adapter.
        result=diagnostic.run(adapter=SystemTrustAdapter())
    else:
        if args.output is None:
            parser.error('--output required for collection')
        original=collect.Transport
        collect.Transport=SystemTransport
        try:
            result=collect.run(args.output,qualification.UNIVERSE,execute=True)
            qualification.save(args.output/'tls-attestation.json',dict(
                adapter_sha256=qualification.sha(__file__),collector_sha256=qualification.sha(collect.__file__),
                cert_required=True,check_hostname=True,system_trust=True,verify_false=False,
                production_config_changes=False))
        finally:
            collect.Transport=original
    print(json.dumps(qualification.archive.json_value(result),ensure_ascii=False))
