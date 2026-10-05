"""Public INPI account archive only: every document quarantined, no SQL or serving."""
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

from service.inpi.accounts_pilot import normal_name, run, validate_manifest
from service.inpi.accounts_smoke import summary
from service.inpi.client import InpiClient, InpiError
from service.inpi.files import atomic


class DocumentExcluded(InpiError):
    """Unusable identity/access evidence, distinct from transport/quota failures."""


class ArchiveClient:
    def __init__(self, client, manifest, root, *, max_requests, max_bytes):
        self.client=client; self.root=root; self.max_requests=max_requests; self.max_bytes=max_bytes
        self.bytes=0; self.observations=[]; self.new_documents=0
        self.names={i['siren']:{normal_name(n) for n in i['name_aliases']} for i in manifest['issuers']}

    @property
    def calls(self): return self.client.calls

    def _budget(self):
        if self.calls>=self.max_requests: raise InpiError('Budget appels INPI atteint')

    def login(self):
        self._budget(); self.client.login()

    def accounts(self,*args,**kwargs):
        self._budget(); return self.client.accounts(*args,**kwargs)

    def account(self,identifier):
        self._budget(); payload=self.client.account(identifier)
        observed=datetime.now(UTC).isoformat()
        siren=str(payload.get('siren'))
        if siren not in self.names: raise DocumentExcluded('ACCOUNT_SIREN_NOT_VERIFIED')
        try:
            checked=summary(payload,siren)
        except InpiError:
            raise DocumentExcluded('WITHDRAWN_NON_PUBLIC_OR_INTERNAL_IDENTITY_MISMATCH') from None
        if payload.get('id')!=identifier:
            raise DocumentExcluded('ACCOUNT_ID_MISMATCH')
        if checked['identity'].get('codeConfidentialite')!='0':
            raise DocumentExcluded('INTERNAL_CONFIDENTIALITY_NOT_PUBLIC')
        if normal_name(payload.get('denomination')) not in self.names[siren]:
            raise DocumentExcluded('ACCOUNT_LEGAL_NAME_NOT_MATCHED')
        content=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode('utf-8')
        if self.bytes+len(content)>self.max_bytes: raise InpiError('Budget octets INPI atteint')
        self.bytes+=len(content)
        digest=hashlib.sha256(content).hexdigest()
        target=self.root/'quarantine'/'objects'/f'{digest}.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                raise InpiError('Archive existante corrompue : arrêt')
        else:
            atomic(target,payload)
            self.new_documents+=1
        self.observations.append({'id':checked.get('id') or identifier,'siren':siren,
            'sha256':digest,'path':str(target),'observed_at':observed,'available_at':observed,
            'qualification_state':'QUARANTINED_UNQUALIFIED','ml_usable':False,
            'historical_pit_qualified':False,'canonical_go':False})
        return payload

    def close(self): self.client.close()


def collect(cfg,result,*,root,manifest_path,dry_run=False,max_symbols=None,client=None):
    if cfg.get('collection_mode')!='quarantine_only':
        raise ValueError('Mode INPI obligatoire : quarantine_only')
    if cfg.get('canonical_writes_enabled') is not False or cfg.get('serving_enabled') is not False:
        raise ValueError('Promotion des comptes INPI interdite')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    validate_manifest(manifest)
    if max_symbols is not None:
        if not 1<=max_symbols<=10: raise ValueError('Limite pilote INPI : 1 à 10 émetteurs')
        manifest={**manifest,'issuers':manifest['issuers'][:max_symbols]}
    max_requests=cfg.get('max_requests_per_run',130)
    max_bytes=cfg.get('max_archive_bytes_per_run',134217728)
    if type(max_requests) is not int or not 1<=max_requests<=130:
        raise ValueError('Budget INPI : 1 à 130 appels')
    if type(max_bytes) is not int or not 1<=max_bytes<=134217728:
        raise ValueError('Budget archive INPI : au plus 128 Mio')
    result.update(requested_count=len(manifest['issuers']),collection_mode='quarantine_only',
                  scope='TEN_VERIFIED_ISSUERS_NOT_FULL_FR_UNIVERSE',ml_usable=False,
                  historical_pit_qualified=False,quarantined_count=0)
    if dry_run: return
    archive=ArchiveClient(client or InpiClient(username_env=cfg.get('username_env','INPI_USERNAME'),
        password_env=cfg.get('password_env','INPI_PASSWORD')),manifest,root,
        max_requests=max_requests,max_bytes=max_bytes)
    folder=root/'observations'/(datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    report=run(archive,manifest,folder)
    evidence={'qualification_state':'QUARANTINED_UNQUALIFIED','canonical_go':False,
              'ml_usable':False,'historical_pit_qualified':False,'documents':archive.observations}
    with (folder/'quarantine_manifest.json').open('x',encoding='utf-8') as handle:
        json.dump(evidence,handle,ensure_ascii=False,indent=2)
    result.update(received_count=len(archive.observations),persisted_count=len(archive.observations),
                  quarantined_count=len(archive.observations),new_objects_count=archive.new_documents,
                  provider_calls=archive.calls,archive_bytes=archive.bytes,
                  report_path=str(folder/'report.json'),quarantine_manifest=str(folder/'quarantine_manifest.json'),
                  counter_units='requested=issuers; received/persisted=public account observations; failed=issuer errors')
    failures=sum(bool(i['errors']) or not i['accounts'] for i in report['issuers'])
    result['failed_count']=failures
    if report['status'] not in ('PILOT_COMPLETE_REVIEW_PENDING',) or failures:
        result['failed_count']=max(1,failures)
        raise InpiError('Collecte INPI incomplète ; comptes reçus conservés en quarantaine. '+report.get('error_message',''))
    # Accounting anomalies are expected in quarantine, not transport failures.
    result['qualification_issues_count']=sum(bool(a.get('issues')) for i in report['issuers'] for a in i['accounts'])
