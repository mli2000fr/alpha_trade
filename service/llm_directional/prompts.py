"""Versioned v5-v9 local/Web prompts; historical request contracts stay immutable."""
from copy import deepcopy
from common.ia_prompts import load_prompt

VERSION='oracle-local-evidence-trend-v5'
DEEPSEEK_SEARCH_VERSION='oracle-deepseek-search-trend-v6'
FRESH_VERSION='oracle-fresh-evidence-trend-v7'
SCORE_VERSION='oracle-fresh-evidence-direction-score-v8'
TREND_EVIDENCE_VERSION='oracle-direction-evidence-v9'


def score_protocol(version):
    return version in (SCORE_VERSION, TREND_EVIDENCE_VERSION)


def fresh_protocol(version):
    return version in (FRESH_VERSION, SCORE_VERSION, TREND_EVIDENCE_VERSION)


def has_local_evidence(context):
    return context.get('analysis_protocol') in (VERSION, DEEPSEEK_SEARCH_VERSION,FRESH_VERSION,SCORE_VERSION,TREND_EVIDENCE_VERSION)


def native_search_protocol(version):
    return version in (DEEPSEEK_SEARCH_VERSION,FRESH_VERSION,SCORE_VERSION,TREND_EVIDENCE_VERSION)


def schema(base):
    value=deepcopy(base)
    value['properties']['local_evidence']={'type':'array','items':{'type':'object',
        'additionalProperties':False,'required':['source_id','quote'],
        'properties':{'source_id':{'type':'string'},'quote':{'type':'string'}}}}
    value['properties']['consensus_analysis']={'type':'string'}
    value['required']+=['local_evidence','consensus_analysis']
    return value


def instructions(mode,version=None):
    versions = {VERSION:'v5', DEEPSEEK_SEARCH_VERSION:'v6', FRESH_VERSION:'v7',
                SCORE_VERSION:'v8', TREND_EVIDENCE_VERSION:'v9'}
    version_key = versions.get(version,'v5')
    mode_key = 'local_data_only' if mode=='local_data_only' else 'web_search'
    return load_prompt(f'cloud.oracle_directional.{version_key}.{mode_key}',runtime='cloud')


def legacy_instructions():
    return load_prompt('cloud.oracle_directional.v4.web_search',runtime='cloud')


def response_schema(base,version=None):
    value=schema(base)
    if fresh_protocol(version):
        value['properties']['context_analysis']={'type':'string'}
        value['required'].append('context_analysis')
    if score_protocol(version):
        del value['properties']['decision']
        value['required'].remove('decision')
        value['properties']['direction_score']={'type':'integer','enum':list(range(1,11))}
        value['required'].append('direction_score')
    if version == TREND_EVIDENCE_VERSION:
        value['properties']['direction_score']={'type':['integer','null'],'enum':[*range(1,11),None]}
        value['properties']['trend_status']={'type':'string','enum':['ASSESSED','UNDETERMINABLE']}
        value['properties']['evidence_quality']={'type':'string','enum':['SUFFICIENT','PARTIAL','INSUFFICIENT']}
        value['properties']['evidence_explanation']={'type':'string'}
        value['required']+=['trend_status','evidence_quality','evidence_explanation']
    return value


def output_policy(context, config):
    version = context.get('analysis_protocol')
    if version == TREND_EVIDENCE_VERSION:
        key = 'v9'
    elif version == SCORE_VERSION:
        key = 'v8'
    else:
        key = 'legacy_long_short' if config.allow_short else 'legacy_long_only'
    return load_prompt(f'cloud.oracle_directional.output.{key}',runtime='cloud')
