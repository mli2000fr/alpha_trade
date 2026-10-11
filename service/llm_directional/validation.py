"""Fail closed: output schema, searched URLs, fresh dated evidence, identity."""
import json
import math
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from jsonschema import validate
from .openai_client import SCHEMA, deepseek_output

FRESH_QUALIFICATIONS = frozenset({'fresh_timestamp_claim', 'fresh_date_claim'})


def _date_only_bounds(value):
    """Bounds of a claimed calendar day over UTC offsets -12 through +14.

    These are interval bounds, NOT a fabricated publication timestamp.
    """
    if not value or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return None
    try:
        day_start = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        return (day_start - timedelta(hours=14),
                day_start + timedelta(days=1, hours=12))
    except (ValueError, OverflowError):
        return None


def _publication_status(value, now, max_age_days):
    """Qualify the claimed precision, never fill in a missing time or timezone."""
    if not value:
        return 'missing_publication_date'
    try:
        published = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, OverflowError):
        return 'invalid_publication_date'
    if 'T' not in value and ' ' not in value:
        bounds = _date_only_bounds(value)
        if bounds is None:
            return 'invalid_publication_date'
        earliest, latest_exclusive = bounds
        cutoff = now - timedelta(days=max_age_days)
        if earliest >= cutoff and latest_exclusive <= now:
            return 'fresh_date_claim'
        if latest_exclusive <= cutoff:
            return 'stale_date_claim'
        if earliest > now:
            return 'future_date_claim'
        return 'date_only_ambiguous'
    if published.tzinfo is None:
        return 'missing_timezone'
    if published > now:
        return 'future_publication_date'
    if published < now - timedelta(days=max_age_days):
        return 'stale_publication_date'
    return 'fresh_timestamp_claim'


def parse_response(response, symbol, config, observed_at):
    if config.provider == 'deepseek':
        response = deepseek_output(response)
    if response.get('status') != 'completed':
        raise ValueError(f'Réponse {config.provider_label} incomplète/refusée')
    searches, texts, known = [], [], set()
    for item in response.get('output', []):
        if item.get('type') == 'web_search_call' and item.get('status') == 'completed':
            searches.append(item)
            action = item.get('action') or {}
            for source in action.get('sources', []):
                if source.get('url'):
                    known.add(source['url'])
            if action.get('type') in ('open_page', 'find_in_page') and action.get('url'):
                known.add(action['url'])
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
    fresh, retained, excluded, qualifications = set(), [], [], []
    # Repository timestamps are naive UTC; preserve the instant of aware callers.
    now = (observed_at.replace(tzinfo=timezone.utc) if observed_at.tzinfo is None
           else observed_at.astimezone(timezone.utc))
    for source in result['sources']:
        url = source['url']
        try:
            parts = urlsplit(url)
            valid_url = parts.scheme in ('https', 'http') and bool(parts.hostname)
        except ValueError:
            valid_url = False
        status = ('invalid_url' if not valid_url else 'untraceable_url' if url not in known
                  else _publication_status(source['published_at'], now, config.max_source_age_days))
        qualification = dict(source, qualification=status)
        bounds = _date_only_bounds(source['published_at'])
        if bounds is not None:
            qualification['possible_publication_start_utc'] = bounds[0].isoformat()
            qualification['possible_publication_end_utc_exclusive'] = bounds[1].isoformat()
        qualifications.append(qualification)
        if status in ('invalid_url', 'untraceable_url'):
            excluded.append(dict(source, exclusion_reason=status))
            continue
        retained.append(source)
        if status in FRESH_QUALIFICATIONS:
            fresh.add(url)
    blockers = []
    if len(fresh) < config.min_sources:
        blockers.append('insufficient_fresh_sources')
    if excluded:
        # The directional reasoning may depend on an excluded claim. Do not
        # silently endorse that reasoning just because other sources are dated.
        blockers.append('excluded_untraceable_sources')
    if result['confidence'] < config.min_confidence:
        blockers.append('confidence_below_threshold')
    if result['decision'] == 'SHORT' and not config.allow_short:
        blockers.append('short_not_allowed')
    # An ABSTAIN remains a valid assessment even when recent sources are insufficient.
    result['eligible'] = result['decision'] != 'ABSTAIN' and not blockers
    result['assessment_outcome'] = ('ABSTAIN' if result['decision'] == 'ABSTAIN'
                                    else 'ABSTAIN_UNQUALIFIED' if blockers else 'ELIGIBLE')
    result['sources'] = retained
    result['excluded_sources'] = excluded
    result['source_qualifications'] = qualifications
    result['fresh_source_count'] = len(fresh)
    result['selection_blockers'] = blockers
    result['source_timestamps_verified'] = False
    return result


def select_symbols(items, config):
    eligible = [item for item in items if item['eligible']]
    eligible.sort(key=lambda item: (-item['confidence'], item['oracle_rank'], item['symbol']))
    return [item['symbol'] for item in eligible[:config.max_selected]]
