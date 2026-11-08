from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from common import ia_prompts
from service.llm_directional.config import FilterConfig
from service.llm_directional.openai_client import build_request
from service.llm_directional import prompts


FIXTURE = json.loads((Path(__file__).parent/'fixtures/llm_cloud_prompt_hashes.json').read_text(encoding='utf-8'))


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@pytest.mark.parametrize('prompt_id,expected',list(FIXTURE['files'].items()))
def test_extracted_files_match_original_prompt_text_exactly(prompt_id,expected):
    assert sha(ia_prompts.load_prompt(prompt_id,runtime='cloud'))==expected


@pytest.mark.parametrize('case,expected',list(FIXTURE['requests'].items()))
def test_all_historical_and_current_request_contracts_are_identical(case,expected):
    version,provider,mode,short=case.split(':')
    versions=dict(v4='oracle-web-directional-v4',v5=prompts.VERSION,v6=prompts.DEEPSEEK_SEARCH_VERSION,
        v7=prompts.FRESH_VERSION,v8=prompts.SCORE_VERSION,v9=prompts.TREND_EVIDENCE_VERSION)
    config=FilterConfig(provider=provider,analysis_mode=mode,allow_short=short=='True',
        scoring_mode='direction_1_10' if version in ('v8','v9') else 'legacy_confidence',
        separate_trend_evidence=version=='v9')
    context=dict(FIXTURE['context'],analysis_protocol=versions[version],analysis_mode=mode)
    # Request construction only: no client or paid API is instantiated.
    request=build_request(context,config)
    assert sha(json.dumps(request,sort_keys=True,ensure_ascii=False))==expected


def catalog(tmp_path,monkeypatch,entries):
    monkeypatch.setattr(ia_prompts,'PROMPT_ROOT',tmp_path)
    (tmp_path/'catalog.json').write_text(json.dumps(dict(schema_version=1,prompts=entries)),encoding='utf-8')


def test_future_local_prompt_is_distinct_and_never_falls_back_to_cloud(tmp_path,monkeypatch):
    catalog(tmp_path,monkeypatch,dict(
        cloud=dict(runtime='cloud',path='cloud/prompt.txt'),
        local=dict(runtime='local',path='local/prompt.txt')))
    for runtime in ('cloud','local'):
        (tmp_path/runtime).mkdir();(tmp_path/runtime/'prompt.txt').write_text(runtime,encoding='utf-8')
    assert ia_prompts.load_prompt('local',runtime='local')=='local'
    assert ia_prompts.load_prompt('cloud',runtime='cloud')=='cloud'
    with pytest.raises(ia_prompts.PromptConfigurationError,match='runtime local'):
        ia_prompts.load_prompt('cloud',runtime='local')
    with pytest.raises(ia_prompts.PromptConfigurationError):ia_prompts.load_prompt('missing',runtime='local')


@pytest.mark.parametrize('path',['../escape.txt','cloud/../../escape.txt','local/prompt.txt'])
def test_prompt_path_cannot_escape_its_runtime(tmp_path,monkeypatch,path):
    catalog(tmp_path,monkeypatch,dict(test=dict(runtime='cloud',path=path)))
    with pytest.raises(ia_prompts.PromptConfigurationError,match='hors du répertoire'):
        ia_prompts.load_prompt('test')


def test_missing_empty_and_updated_files_are_handled_before_api_calls(tmp_path,monkeypatch):
    catalog(tmp_path,monkeypatch,dict(test=dict(runtime='cloud',path='cloud/prompt.txt')))
    with pytest.raises(ia_prompts.PromptConfigurationError,match='illisible'):ia_prompts.load_prompt('test')
    (tmp_path/'cloud').mkdir();path=tmp_path/'cloud/prompt.txt';path.write_text('   ',encoding='utf-8')
    with pytest.raises(ia_prompts.PromptConfigurationError,match='vide'):ia_prompts.load_prompt('test')
    path.write_text('version one\n',encoding='utf-8');assert ia_prompts.load_prompt('test')=='version one\n'
    path.write_text('version two\n',encoding='utf-8');assert ia_prompts.load_prompt('test')=='version two\n'


def test_loading_does_not_depend_on_current_working_directory(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    value=prompts.instructions('local_data_only',prompts.TREND_EVIDENCE_VERSION)
    assert sha(value)==FIXTURE['files']['cloud.oracle_directional.v9.local_data_only']


def test_template_variables_are_explicit_and_not_recursively_evaluated(tmp_path,monkeypatch):
    catalog(tmp_path,monkeypatch,dict(test=dict(runtime='cloud',path='cloud/prompt.txt')))
    (tmp_path/'cloud').mkdir();(tmp_path/'cloud/prompt.txt').write_text('Schema: {{schema}}',encoding='utf-8')
    assert ia_prompts.render_prompt('test',variables={'schema':'{{untrusted}}'})=='Schema: {{untrusted}}'
    for variables in ({},{'other':'value'},{'schema':10}):
        with pytest.raises(ia_prompts.PromptConfigurationError):ia_prompts.render_prompt('test',variables=variables)


def test_invalid_catalog_is_an_explicit_configuration_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(ia_prompts,'PROMPT_ROOT',tmp_path)
    for text in ('{','[]','{"schema_version": 2, "prompts": {}}'):
        (tmp_path/'catalog.json').write_text(text,encoding='utf-8')
        with pytest.raises(ia_prompts.PromptConfigurationError):ia_prompts.load_prompt('test')
