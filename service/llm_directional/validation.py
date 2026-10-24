"""Fail closed: output schema, searched URLs, fresh dated evidence, identity."""
import json
import math
import re
from dataclasses import replace
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


def _parse_web_response(response, symbol, config, observed_at, *, response_schema=None, score_mode=False):
    provider_dates=None
    from .prompts import native_search_protocol
    if (config.provider=='deepseek' and native_search_protocol(response.get('analysis_protocol'))
            and response.get('web_status')=='completed' and not response.get('error')):
        from .deepseek_search import evidence
        provider_dates={s['url']:s['provider_date'] for s in evidence(
            response.get('search_receipts',[]),response.get('fetch_receipts',[]),500)}
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
    validate(result, response_schema or SCHEMA)
    if score_mode:
        from .direction_score import apply_score
        apply_score(result, config)
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
                  else 'provider_date_mismatch' if provider_dates is not None
                  and source['published_at']!=provider_dates.get(url)
                  else _publication_status(source['published_at'], now, config.max_source_age_days))
        qualification = dict(source, qualification=status)
        bounds = _date_only_bounds(source['published_at'])
        if bounds is not None:
            qualification['possible_publication_start_utc'] = bounds[0].isoformat()
            qualification['possible_publication_end_utc_exclusive'] = bounds[1].isoformat()
        qualifications.append(qualification)
        if status in ('invalid_url', 'untraceable_url', 'provider_date_mismatch'):
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
    if not score_mode and result['confidence'] < config.min_confidence:
        blockers.append('confidence_below_threshold')
    if result['decision'] == 'SHORT' and not config.allow_short:
        blockers.append('short_not_allowed')
    if result['decision'] == 'LONG' and not config.allow_long:
        blockers.append('long_not_allowed')
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


def _local_qualifications(result,context,config,observed_at):
    from .repository import digest
    if digest(context.get('local_evidence'))!=context.get('local_evidence_sha256'):
        raise ValueError('Preuves locales altérées')
    def utc(value):
        stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Horodatage de preuve sans fuseau')
        return stamp.astimezone(timezone.utc)
    cutoff=utc(context['evidence_cutoff_utc'])
    now=observed_at.replace(tzinfo=timezone.utc) if observed_at.tzinfo is None else observed_at.astimezone(timezone.utc)
    if cutoff>now:
        raise ValueError('Cutoff de preuve futur')
    sources=[]
    for source in context['local_evidence']:
        sources.append(source)
        sources.extend(source.get('prior_actual_snapshots',[]))
    by_id={s['source_id']:s for s in sources}
    if len(by_id)!=len(sources):
        raise ValueError('Identifiants de preuve locale ambigus')
    qualifications,qualified,excluded=[],set(),[]
    norm=lambda value:re.sub(r'\s+',' ',value).strip()
    for citation in result['local_evidence']:
        source=by_id.get(citation['source_id'])
        quote=citation['quote']
        if not source or not 8<=len(quote)<=800 or norm(quote) not in norm(source['text']):
            excluded.append(dict(citation,qualification='untraceable_local_evidence'))
            continue
        status='unqualified_local_context'
        received=utc(source['available_at_utc'])
        if not received<cutoff:
            raise ValueError('Preuve locale reçue après cutoff')
        if source.get('observed_at_utc') and utc(source['observed_at_utc'])>received:
            raise ValueError('Horloge de preuve incohérente')
        fresh=received>=cutoff-timedelta(days=config.max_source_age_days)
        if source['kind']=='consensus':
            fresh &= received>=cutoff-timedelta(days=config.consensus_max_age_days)
            ready=(source.get('units_qualified') is True and source.get('fiscal_identity_qualified') is True
                and source.get('qualification_status') in ('QUALIFIED','VALIDATED','PROSPECTIVE_QUALIFIED'))
        elif source['kind']=='news':
            publication=utc(source['publication_utc'])
            fresh &= cutoff-timedelta(days=config.max_source_age_days)<=publication<cutoff
            ready=source.get('identity_qualified') is True
        elif source['kind']=='sec':
            from .prompts import fresh_protocol
            if not fresh_protocol(context.get('analysis_protocol')):
                raise ValueError('Type de preuve incompatible avec le protocole')
            from .fresh_evidence import day,sec_url,NY
            fresh &= cutoff.astimezone(NY).date()-timedelta(days=config.evidence_sec_max_age_days)<=day(source['publication_date'])<=cutoff.astimezone(NY).date()
            ready=(source.get('identity_qualified') is True and source.get('integrity_qualified') is True
                and sec_url(source.get('url'),source.get('cik'),source.get('accession','')))
        elif source['kind'] in ('earnings_calendar','price_volume','fundamentals'):
            from .prompts import fresh_protocol
            if not fresh_protocol(context.get('analysis_protocol')):
                raise ValueError('Type de contexte incompatible')
            ready=False  # Contextual facts, never sufficient directional evidence.
            status='qualified_factual_context_only'
        else:
            raise ValueError('Type de preuve inconnu')
        if fresh and ready and source.get('eligible_for_direction') is True:
            status='qualified_local_evidence'
            qualified.add(source['source_id'])
        qualifications.append(dict(citation,qualification=status,available_at_utc=source['available_at_utc']))
    return qualifications,qualified,excluded


def parse_response(response, symbol, config, observed_at, context=None):
    from .prompts import DEEPSEEK_SEARCH_VERSION,FRESH_VERSION,SCORE_VERSION,fresh_protocol,has_local_evidence,response_schema
    upgraded=context is not None and has_local_evidence(context)
    version=context.get('analysis_protocol') if context else None
    score_mode=version==SCORE_VERSION
    if score_mode and config.scoring_mode!='direction_1_10':
        raise ValueError('Protocole de score incompatible avec la configuration')
    if context and (version==DEEPSEEK_SEARCH_VERSION or fresh_protocol(version) and config.provider=='deepseek' and config.analysis_mode=='web_search'):
        if (config.provider!='deepseek' or config.analysis_mode!='web_search'
                or response.get('analysis_protocol')!=version
                or response.get('web_provider')!='deepseek' or response.get('analysis_mode')!='web_search'):
            raise ValueError('Provenance DeepSeek Search native incompatible')
    local=config.analysis_mode=='local_data_only'
    if not upgraded:
        if local:
            raise ValueError('Contexte local figé requis pour validation')
        return _parse_web_response(response,symbol,config,observed_at)
    if context.get('symbol')!=symbol or context.get('analysis_mode')!=config.analysis_mode:
        raise ValueError('Mode/symbole du contexte incompatible')
    if fresh_protocol(version):
        from .fresh_evidence import validate_fresh_packet
        validate_fresh_packet(context,config,observed_at)
    if not local:
        web_config=(replace(config,max_source_age_days=min(config.max_source_age_days,config.evidence_news_max_age_days))
                    if fresh_protocol(version) else config)
        result=_parse_web_response(response,symbol,web_config,observed_at,response_schema=response_schema(SCHEMA,version),score_mode=score_mode)
    else:
        normalized=deepseek_output(response) if config.provider=='deepseek' else response
        if normalized.get('status')!='completed':
            raise ValueError(f'Réponse {config.provider_label} locale incomplète/refusée')
        if any(item.get('type','').endswith('_call') for item in normalized.get('output',[])):
            raise ValueError('Appel outil interdit en mode local')
        parts=[p for item in normalized.get('output',[]) if item.get('type')=='message'
               for p in item.get('content',[])]
        if any(p.get('type')=='refusal' for p in parts):
            raise ValueError('Refus du modèle')
        result=json.loads(''.join(p.get('text','') for p in parts if p.get('type')=='output_text'))
        validate(result,response_schema(SCHEMA,version))
        if score_mode:
            from .direction_score import apply_score
            apply_score(result, config)
        if result['symbol']!=symbol or result['sources']:
            raise ValueError('Symbole incorrect ou sources Web interdites en mode local')
        if type(result['confidence']) not in (int,float) or not math.isfinite(result['confidence']):
            raise ValueError('Confiance non finie')
        blockers=[]
        if not result['identity_verified']:
            blockers.append('identity_not_confirmed')
        if not score_mode and result['confidence']<config.min_confidence:
            blockers.append('confidence_below_threshold')
        if result['decision']=='SHORT' and not config.allow_short:
            blockers.append('short_not_allowed')
        if result['decision']=='LONG' and not config.allow_long:
            blockers.append('long_not_allowed')
        result.update(selection_blockers=blockers,sources=[],excluded_sources=[],
            source_qualifications=[],fresh_source_count=0,source_timestamps_verified=False)
    if not result['consensus_analysis'].strip():
        raise ValueError('Analyse du consensus absente ; expliciter les données manquantes si nécessaire')
    if fresh_protocol(version) and not result['context_analysis'].strip():
        raise ValueError('Analyse du contexte frais absente')
    qualifications,qualified,excluded=_local_qualifications(result,context,config,observed_at)
    result.update(local_source_qualifications=qualifications,excluded_local_sources=excluded,
        fresh_local_source_count=len(qualified),analysis_mode=config.analysis_mode,
        evidence_cutoff_utc=context['evidence_cutoff_utc'])
    if excluded:
        result['selection_blockers'].append('excluded_untraceable_local_sources')
    if local and len(qualified)<config.min_local_sources:
        result['selection_blockers'].append('insufficient_qualified_local_sources')
    if score_mode and result['decision']=='ABSTAIN':
        result['selection_blockers'].append('direction_score_neutral')
    result['eligible']=result['decision']!='ABSTAIN' and not result['selection_blockers']
    result['assessment_outcome']=('ABSTAIN' if result['decision']=='ABSTAIN' else
        'ELIGIBLE' if result['eligible'] else 'ABSTAIN_UNQUALIFIED')
    return result


def select_symbols(items, config):
    eligible = [item for item in items if item['eligible']]
    for item in eligible:
        if (item.get('decision') == 'LONG' and not config.allow_long
                or item.get('decision') == 'SHORT' and not config.allow_short):
            raise ValueError('Sélection direction non autorisée incohérente')
    from .direction_score import selection_sort_key, score_decision
    if config.scoring_mode=='direction_1_10':
        for item in items:
            expected=score_decision(item.get('direction_score'),config)
            if item['decision']!=expected or item['eligible'] and (expected=='ABSTAIN' or expected=='SHORT' and not config.allow_short):
                raise ValueError('Sélection score/direction incohérente')
    eligible.sort(key=selection_sort_key)
    return [item['symbol'] for item in eligible[:config.max_selected]]
