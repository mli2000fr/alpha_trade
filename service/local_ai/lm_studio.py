"""Explicit loopback LM Studio client, with no cloud fallback or automatic retry."""
from dataclasses import dataclass
from datetime import datetime,timezone
import ipaddress
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

import requests
import yaml

from common.ia_prompts import load_prompt


PROJECT=Path(__file__).resolve().parents[2]
CONFIG_PATH=PROJECT/'config/ia/connections/lm_studio.yaml'


@dataclass(frozen=True)
class Connection:
    base_url: str='http://127.0.0.1:1234/v1'
    model: str='qwen3.5-9b'
    timeout_seconds: int=120
    max_output_tokens: int=512
    temperature: float=0.
    api_key_env: str='LM_STUDIO_API_KEY'

    def __post_init__(self):
        parts=urlsplit(self.base_url)
        try:
            local=parts.hostname=='localhost' or ipaddress.ip_address(parts.hostname or '').is_loopback
            port=parts.port
        except ValueError:local=False;port=None
        if (not local or parts.scheme not in ('http','https') or parts.username or parts.password
                or parts.query or parts.fragment or parts.path.rstrip('/')!='/v1' or port is None):
            raise ValueError('LM Studio : URL explicite de boucle locale avec port et chemin /v1 requise')
        if not isinstance(self.model,str) or not self.model.strip():raise ValueError('Modèle local requis')
        if type(self.timeout_seconds) is not int or not 5<=self.timeout_seconds<=600:raise ValueError('Délai local invalide')
        if type(self.max_output_tokens) is not int or not 1<=self.max_output_tokens<=32000:raise ValueError('Limite de tokens locale invalide')
        if type(self.temperature) not in (float,int) or not math.isfinite(self.temperature) or not 0<=self.temperature<=2:raise ValueError('Température locale invalide')
        if self.api_key_env!='LM_STUDIO_API_KEY':raise ValueError('Utiliser exclusivement LM_STUDIO_API_KEY pour cette connexion')


def load_connection(path=None):
    values=yaml.safe_load(Path(path or CONFIG_PATH).read_text(encoding='utf-8'))
    if not isinstance(values,dict):raise ValueError('Configuration LM Studio invalide')
    return Connection(**values)


class Client:
    def __init__(self,config=None,*,session=None):
        self.config=config or load_connection()
        self.session=session or requests.Session()
        self.session.trust_env=False  # Never forward local traffic to an environment proxy.
        token=os.environ.get(self.config.api_key_env)
        self.headers={'Authorization':'Bearer '+token} if token else {}

    def close(self):self.session.close()

    def _request(self,method,path,body=None):
        try:
            response=self.session.request(method,self.config.base_url.rstrip('/')+path,
                json=body,headers=self.headers,timeout=(3,self.config.timeout_seconds),allow_redirects=False)
        except requests.RequestException as exc:
            raise RuntimeError(f'LM Studio indisponible : {type(exc).__name__}, sans reprise automatique') from None
        if response.status_code!=200:
            raise RuntimeError(f'LM Studio HTTP {response.status_code} ; vérifier le serveur, le modèle et son authentification')
        try:result=response.json()
        except ValueError:raise RuntimeError('LM Studio : réponse JSON invalide') from None
        if not isinstance(result,dict) or result.get('error'):
            raise RuntimeError('LM Studio : réponse en erreur ou non objet')
        return result

    def models(self):
        result=self._request('GET','/models')
        if not isinstance(result.get('data'),list):raise RuntimeError('LM Studio : liste de modèles invalide')
        return [row['id'] for row in result['data'] if isinstance(row,dict) and isinstance(row.get('id'),str)]

    def chat(self,messages):
        if not messages or any(not isinstance(m,dict) or m.get('role') not in ('system','user','assistant')
                or not isinstance(m.get('content'),str) for m in messages):raise ValueError('Messages locaux invalides')
        request=dict(model=self.config.model,messages=messages,temperature=self.config.temperature,
                     max_tokens=self.config.max_output_tokens,stream=False)
        raw=self._request('POST','/chat/completions',request)
        choices=raw.get('choices')
        if not isinstance(choices,list) or not choices or not isinstance(choices[0],dict):
            raise RuntimeError('LM Studio : réponse sans choix exploitable')
        message=choices[0].get('message') or {}
        content=message.get('content')
        if not isinstance(content,str) or not content.strip():
            raise RuntimeError('LM Studio a répondu sans texte final ; vérifier la limite de tokens et le mode de raisonnement')
        return dict(content=content,model=raw.get('model'),finish_reason=choices[0].get('finish_reason'),
                    usage=raw.get('usage'),request=request,response=raw)


def connectivity_test(client=None):
    owned=client is None;client=client or Client();started=time.monotonic()
    try:
        available=client.models()
        if client.config.model not in available:
            raise RuntimeError(f'Modèle {client.config.model} non exposé par LM Studio ; aucun remplacement automatique')
        system=load_prompt('local.connectivity.v1.system',runtime='local')
        result=client.chat([dict(role='system',content=system),
                          dict(role='user',content='Réponds exactement LM_STUDIO_OK.')])
        exact=result['content'].strip()=='LM_STUDIO_OK'
        return dict(status='CONNECTED_AND_EXACT_RESPONSE' if exact else 'CONNECTED_RESPONSE_DIFFERS',
            observed_at_utc=datetime.now(timezone.utc).isoformat(),available_models=available,
            base_url=client.config.base_url,configured_model=client.config.model,
            elapsed_seconds=time.monotonic()-started,cloud_calls=0,broker_calls=0,
            pipeline_changed=False,**result)
    finally:
        if owned:client.close()


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    client=Client(load_connection(args.config))
    try:report=connectivity_test(client)
    except Exception as exc:
        report=dict(status='FAILED',error_type=type(exc).__name__,error=str(exc),cloud_calls=0,pipeline_changed=False)
    finally:client.close()
    (args.output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('request','response')},ensure_ascii=False,indent=2))
    if report['status']=='FAILED':raise SystemExit(1)


if __name__=='__main__':main()
