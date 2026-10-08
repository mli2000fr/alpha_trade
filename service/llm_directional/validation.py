"""Fail closed: output schema, searched URLs, fresh dated evidence, identity."""
import json
import math
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from jsonschema import validate
from .openai_client import SCHEMA


def parse_response(response, symbol, config, observed_at):
    if response.get('status') != 'completed':
        raise ValueError('Réponse OpenAI incomplète/refusée')
    searches, texts, known = [], [], set()
    for item in response.get('output', []):
        if item.get('type') == 'web_search_call' and item.get('status') == 'completed':
            searches.append(item)
            for source in (item.get('action') or {}).get('sources', []):
                if source.get('url'):
                    known.add(source['url'])
        if item.get('type') == 'message':
            for content in item.get('content', []):
                if content.get('type') == 'refusal':
                    raise ValueError('Refus du modèle')
                if content.get('type') == 'output_text':
                    texts.append(content.get('text', ''))
                    for annotation in content.get('annotations', []):
                        if annotation.get('type') == 'url_citation' and annotation.get('url'):
                            known.add(annotation['url'])
    if not searches:
        raise ValueError('Aucune recherche Web terminée')
    result = json.loads(''.join(texts))
    validate(result, SCHEMA)
    if result['symbol'] != symbol or not result['identity_verified']:
        raise ValueError('Identité du titre non vérifiée')
    if isinstance(result['confidence'], bool) or not math.isfinite(result['confidence']):
        raise ValueError('Note non numérique/finie')
    fresh = set()
    for source in result['sources']:
        url = source['url']
        parts = urlsplit(url)
        if parts.scheme not in ('https', 'http') or not parts.hostname or url not in known:
            raise ValueError('Source absente des résultats Web')
        if source['published_at']:
            published = datetime.fromisoformat(source['published_at'].replace('Z', '+00:00'))
            if published.tzinfo is None:
                raise ValueError('Date de publication sans fuseau')
            now = observed_at.replace(tzinfo=timezone.utc)
            if now - timedelta(days=config.max_source_age_days) <= published <= now:
                fresh.add(url)
    # An ABSTAIN remains a valid assessment even when recent sources are insufficient.
    eligible = (result['decision'] == 'LONG' and result['confidence'] >= config.min_confidence
                and len(fresh) >= config.min_sources)
    result['eligible'] = eligible
    result['source_timestamps_verified'] = False
    return result


def select_symbols(items, config):
    eligible = [item for item in items if item['eligible']]
    eligible.sort(key=lambda item: (-item['confidence'], item['oracle_rank'], item['symbol']))
    return [item['symbol'] for item in eligible[:config.max_selected]]
