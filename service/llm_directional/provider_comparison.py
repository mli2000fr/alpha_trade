"""Bounded research-only GPT/DeepSeek comparison on the authorized 11 tickers.

One fresh GPT Web answer per ticker, reused unchanged as evidence by DeepSeek.
No Oracle prediction, risk process or order. No automatic paid retry.
"""
import argparse
from dataclasses import replace
import json
import logging
from pathlib import Path
from .config import load_filter_config
from .openai_client import ResponsesClient, build_request
from .repository import Repository, dumps, digest
from .research_rerun import prepare_subset
from .runner import analyze, validate_analysis_window
from .report import report

SYMBOLS = 'SSTK,FICO,PENG,QFIN,FMC,ICHR,CWH,ABR,CLS,APP,HUBG'.split(',')
PARENT = 'llm-bc155d0d71484217b0bdc98cd9e06c7d'


class SharedWebClient(ResponsesClient):
    def __init__(self, config, archives, **kwargs):
        super().__init__(config, **kwargs)
        self.archives = archives
        self.current_symbol = None

    def __call__(self, payload):
        self.current_symbol = payload['context']['symbol']
        return super().__call__(payload)

    def _post(self, url, payload, key, provider):
        if url == 'https://api.openai.com/v1/responses':
            source = self.archives.get(self.current_symbol)
            if not source or source['request'] != payload or not source['response']:
                raise ValueError('Preuves GPT communes absentes ou requête différente ; aucun nouveau Web implicite')
            return source['response']
        return super()._post(url, payload, key, provider)


def comparison_rows(gpt, deepseek):
    left = {r['symbol']: r for r in gpt['candidates']}
    right = {r['symbol']: r for r in deepseek['candidates']}
    result = []
    for symbol in SYMBOLS:
        row = {'symbol': symbol}
        for name, source in [('gpt', left), ('deepseek', right)]:
            item = source.get(symbol, {})
            for field in ('status', 'decision', 'confidence_uncalibrated', 'eligible', 'selected',
                          'fresh_source_count', 'selection_blockers', 'error'):
                row[f'{name}_{field}'] = item.get(field)
        row['same_decision'] = (row['gpt_status'] == row['deepseek_status'] == 'VALID'
                                and row['gpt_decision'] == row['deepseek_decision'])
        result.append(row)
    return result


def run(engine, output, *, write=False):
    parent, snapshot, old, contexts, baseline = prepare_subset(engine, PARENT, SYMBOLS)
    current = load_filter_config()
    config = replace(old, enabled=True, provider='openai', model=current.model,
                     deepseek_model=current.deepseek_model, deepseek_api_key_env=current.deepseek_api_key_env)
    validate_analysis_window(parent['trade_date'])
    preview = {'research_only': True, 'parent_run_id': PARENT, 'trade_date': str(parent['trade_date']),
               'symbols': SYMBOLS, 'gpt_model': config.model, 'deepseek_model': config.deepseek_model,
               'max_paid_generations': 22, 'same_web_evidence': True,
               'warning': 'DeepSeek sees the GPT Web synthesis/preliminary view: not an independent blind comparison.'}
    if not write:
        return preview
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)  # Refuse duplicate paid launches.
    logging.getLogger().addHandler(logging.FileHandler(output / 'run.log', encoding='utf-8'))
    (output / 'protocol.json').write_text(dumps(dict(preview, config=config.snapshot(),
         parent_input_sha256=parent['input_sha256'], baseline=baseline)), encoding='utf-8')
    state = {'status': 'RUNNING', 'completed_api_calls': 0, 'total_api_calls': 22, 'provider': 'gpt'}
    def persist(name, payload):
        (output / name).write_text(dumps(payload), encoding='utf-8')
    def tracked(client, provider):
        def call(request):
            state.update(provider=provider, symbol=(json.loads(request['input'])['symbol']
                         if provider == 'gpt' else request['context']['symbol']))
            persist('progress.json', state)
            try:
                return client(request)
            finally:
                state['completed_api_calls'] += 1
                persist('progress.json', state)
        return call
    identifiers = {name: f'llm-research-{output.name}-{name}' for name in ('gpt', 'deepseek')}
    errors, views = {}, {}
    repo = Repository(engine)
    archives = {}
    for name in ('gpt', 'deepseek'):
        cfg = replace(config, provider='openai' if name == 'gpt' else 'deepseek')
        client = ResponsesClient(cfg) if name == 'gpt' else SharedWebClient(cfg, archives)
        try:
            analyze(engine=engine, batch_id=parent['batch_id'], trade_date=parent['trade_date'],
                    symbol_source=snapshot['symbol_source'], capital_preset_key=snapshot['capital_preset_key'],
                    config=cfg, run_id=identifiers[name], inputs=contexts, client=tracked(client, name),
                    research_parent_run_id=PARENT)
        except Exception as exc:
            errors[name] = f'{type(exc).__name__}: {str(exc)[:600]}'
            logging.error('%s: %s', name, errors[name])
        views[name] = report(engine, identifiers[name])
        persist(f'{name}_report.json', views[name])
        if name == 'gpt':
            _, items = repo.get(identifiers[name])
            for item in items:
                raw = json.loads(item['response_json'] or 'null')
                if raw and digest(raw) == item['response_sha256']:
                    archives[item['symbol']] = {'request': json.loads(item['request_json']), 'response': raw}
    final = dict(preview, run_ids=identifiers, errors=errors,
                 status='COMPLETED' if not errors else 'PARTIAL_FAILED',
                 comparison=comparison_rows(views['gpt'], views['deepseek']))
    persist('report.json', final)
    state.update(status=final['status'], run_ids=identifiers)
    persist('progress.json', state)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--write', action='store_true', help='Authorize 11 GPT Web + 11 DeepSeek calls, research SQL only')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    try:
        print(dumps(run(engine, args.output_dir, write=args.write)), flush=True)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
