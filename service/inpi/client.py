"""Bounded read-only client for the public accounts API, verified TLS only."""
from __future__ import annotations

import json
import os
import re
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlencode, quote

BASE='https://registre-national-entreprises.inpi.fr/api/'


class InpiError(RuntimeError):
    pass


def credential(name):
    value=os.environ.get(name,'')
    if not value and os.name=='nt':
        # Refresh user variables without restart; never print/export credentials.
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as key:
                value=winreg.QueryValueEx(key,name)[0]
        except FileNotFoundError: pass
    if not value: raise InpiError('Variable absente : '+name)
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise InpiError('Redirection INPI refusée ; aucun secret transféré')


class InpiClient:
    def __init__(self,*,username_env='INPI_USERNAME',password_env='INPI_PASSWORD',opener=None):
        self.username_env=username_env; self.password_env=password_env
        self._token=None; self.calls=0
        context=ssl.create_default_context()
        self.opener=opener or urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=context))

    def _request(self,path,*,data=None,authenticated=True):
        if not re.fullmatch(r'(sso/login|bilans(?:-saisis)?(?:/[A-Za-z0-9_-]+)?)(?:\?[^\s]*)?',path):
            raise InpiError('Endpoint INPI non autorisé')
        if authenticated and not self._token: self.login()
        headers={'Accept':'application/json','User-Agent':'AlphaTrade-INPI-research/1.0'}
        if authenticated: headers['Authorization']='Bearer '+self._token
        if data is not None: headers['Content-Type']='application/json'
        request=urllib.request.Request(BASE+path,headers=headers,
            data=json.dumps(data).encode() if data is not None else None)
        guard=getattr(self,'request_guard',None)
        if guard is not None: guard()
        self.calls+=1
        try:
            with self.opener.open(request,timeout=30) as response:
                content=response.read(16*1024*1024+1)
                if len(content)>16*1024*1024: raise InpiError('Réponse INPI au-delà du budget')
                payload=json.loads(content)
                cursor=response.headers.get('pagination-search-after')
                return payload,cursor
        except urllib.error.HTTPError as exc:
            # Never include response body, auth data or headers in logs/errors.
            raise InpiError('INPI HTTP '+str(exc.code)) from None
        except (urllib.error.URLError,ValueError) as exc:
            raise InpiError('INPI réseau/JSON : '+type(exc).__name__) from None

    def login(self):
        data,_=self._request('sso/login',authenticated=False,data={
            'username':credential(self.username_env),'password':credential(self.password_env)})
        token=data.get('token') if isinstance(data,dict) else None
        if not isinstance(token,str) or not token: raise InpiError('Login INPI sans token')
        self._token=token
        # Do not return the account profile or login payload to callers.

    def accounts(self,siren,*,kind='bilans-saisis',page_size=3,search_after=None):
        if not re.fullmatch(r'\d{9}',siren) or kind not in ('bilans','bilans-saisis') or not 1<=page_size<=10:
            raise InpiError('Paramètres smoke INPI invalides')
        params={'siren[]':siren,'pageSize':page_size}
        if search_after is not None:
            if not isinstance(search_after,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}',search_after):
                raise InpiError('Curseur INPI invalide')
            params['searchAfter']=search_after
        rows,cursor=self._request(kind+'?'+urlencode(params))
        if not isinstance(rows,list) or len(rows)>page_size or any(not isinstance(r,dict) or str(r.get('siren'))!=siren for r in rows):
            raise InpiError('Réponse INPI hors périmètre SIREN')
        return rows,cursor

    def account(self,identifier):
        if not re.fullmatch(r'[A-Za-z0-9_-]+',identifier): raise InpiError('Identifiant bilan invalide')
        payload,_=self._request('bilans-saisis/'+quote(identifier,safe=''))
        if not isinstance(payload,dict): raise InpiError('Bilan JSON inattendu')
        return payload

    def close(self):
        self._token=None
