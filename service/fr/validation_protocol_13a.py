"""Freeze FR economic comparison inputs and gates; no SQL, fitting or replay."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from service.fr.economic_preflight_11a import load_protocol, selection_ledger
from service.fr.exploitable_scope_12e import sha


def build_protocol(cfg: dict) -> dict:
    return {
        'schema_version': 1, 'profile': 'fr_economic_validation_13a_v1',
        'market_code': 'FR_EQ', 'currency': 'EUR',
        'development_protocol': cfg,
        'comparison_policies': cfg['policies'],
        'cost_scenarios': {'nominal': 1, 'execution_costs_x2': 2},
        'stress_components': ['commission', 'spread', 'slippage'],
        'tax_stress': False,
        'required_metrics': ['net_pnl_eur', 'net_return_pct', 'daily_sharpe', 'max_drawdown_pct',
                             'mean_gross_exposure_pct', 'mean_net_exposure_pct', 'turnover',
                             'executed_orders', 'closed_trades', 'win_rate',
                             'commission_eur', 'spread_eur', 'slippage_eur', 'taxes_eur',
                             'dividend_cashflows_eur', 'by_fold', 'by_semester', 'by_symbol'],
        'benchmark_state': 'PENDING_QUALIFIED_TOTAL_RETURN_BENCHMARK_NO_PRICE_ONLY_SUBSTITUTION',
        'directional_policy_state': 'NOT_PROMOTED_NO_VALIDATED_DIRECTIONAL_POLICY',
        'sensitivity_state': 'DESCRIPTIVE_ONLY_NO_RETUNING_NO_FUTURE_PATH_FILTERING',
        'confirmation_2026': 'RESERVED_NOT_READ_NOT_EVALUATED',
        'common_population_required': True, 'unknown_evidence_policy': 'BLOCK_COMPARISON_NOT_DROP_PATH',
        'economic_go_allowed': False, 'canonical_writes': False, 'serving_enabled': False,
        'shared_backtest_changes': False,
    }


def inspect_scope(paths: pd.DataFrame, intents: pd.DataFrame, cfg: dict) -> dict:
    keys = ['fold', 'research_uid', 'entry_session']
    if paths.empty or paths.duplicated(keys).any():
        raise ValueError('Population de chemins vide ou dupliquée')
    if set(paths.fold) != set(cfg['folds']) or paths.entry_session.gt(cfg['development_end']).any() \
            or paths.exit_session.gt(cfg['development_end']).any():
        raise ValueError('Périmètre hors folds/période figés ; confirmation réservée')
    if set(intents.policy) != set(cfg['policies']) or intents.future_label_used.any():
        raise ValueError('Politique ajoutée/absente ou intentions utilisant les labels futurs')
    if intents.duplicated(keys+['policy']).any() or not intents.execution_state.eq('INTENT_NOT_FILL').all():
        raise ValueError('Intentions dupliquées ou assimilées à des fills')
    joined = intents[keys].merge(paths[keys], how='left', on=keys, indicator=True, validate='many_to_one')
    if not joined._merge.eq('both').all():
        raise ValueError('Intention sans chemin audité')
    ready = paths.economic_qualified.eq(True)
    return {'candidate_paths': len(paths), 'qualified_common_paths': int(ready.sum()),
            'all_paths_qualified': bool(ready.all()), 'intentions': len(intents),
            'blockers_non_additive': {str(k): int(v) for k,v in paths.explode('blockers').groupby('blockers').size().items()},
            'by_policy': intents.groupby(['fold','policy']).size().rename('intentions').reset_index().to_dict('records')}


def run(output: Path, *, scope: Path, preflight: Path,
        protocol_path=Path('config/research_fr/economic_references_11a_v1.yaml'),
        costs=Path('config/markets/fr_execution_research_v1.yaml'),
        eligibility=Path('config/taxes/fr_ttf_eligibility.yaml')) -> dict:
    if output.exists():
        raise ValueError('Choisir un nouveau dossier ; les preuves archivées ne sont pas écrasées')
    cfg = load_protocol(protocol_path)
    report_path = scope/'report.json'
    prior = json.loads(report_path.read_text(encoding='utf-8'))
    if not prior.get('population_preserved') or not prior.get('policy_ranks_preserved'):
        raise ValueError('La population/rangs ne sont pas préservés')
    for name, expected in prior['input_hashes'].items():
        if sha(Path(name)) != expected:
            raise ValueError(f'Entrée modifiée : {name}')
    for name, expected in prior['output_hashes'].items():
        if sha(scope/name) != expected:
            raise ValueError(f'Sortie de qualification modifiée : {name}')
    anchored = {Path(k).resolve(): v for k,v in prior['input_hashes'].items()}
    sources = [preflight/'report.json', preflight/'selection_intents.parquet',
               preflight/'decision_candidates_scored.parquet']
    if any(anchored.get(p.resolve()) != sha(p) for p in sources):
        raise ValueError('Préflight non ancré au dossier de qualification')
    pre = json.loads(sources[0].read_text(encoding='utf-8'))
    if pre['protocol'] != cfg:
        raise ValueError('Protocole du préflight divergent')
    scores = pd.read_parquet(sources[2])
    intents = pd.read_parquet(sources[1])
    order = ['fold','decision_session_date','policy','candidate_rank']
    pd.testing.assert_frame_equal(intents.sort_values(order).reset_index(drop=True),
                                  selection_ledger(scores,cfg).sort_values(order).reset_index(drop=True))
    paths = pd.read_parquet(scope/'path_blockers.parquet')
    coverage = pd.read_parquet(scope/'policy_intent_coverage.parquet')
    mapped = intents.rename(columns={'decision_session_date':'entry_session'})
    id_cols = ['fold','research_uid','entry_session','policy','candidate_rank']
    pd.testing.assert_frame_equal(mapped[id_cols].sort_values(id_cols).reset_index(drop=True),
                                  coverage[id_cols].sort_values(id_cols).reset_index(drop=True))
    keys = ['fold','research_uid','entry_session']
    pd.testing.assert_frame_equal(scores.rename(columns={'decision_session_date':'entry_session'})[keys]
                                  .sort_values(keys).reset_index(drop=True),
                                  paths[keys].sort_values(keys).reset_index(drop=True))
    counts = inspect_scope(paths,coverage,cfg)
    if counts['candidate_paths'] != prior['candidate_paths'] or counts['qualified_common_paths'] != prior['qualified_common_paths']:
        raise ValueError('Effectifs de qualification divergents du rapport')
    frozen = build_protocol(cfg)
    hashes = {str(p):sha(p) for p in sources+[report_path,scope/'path_blockers.parquet',
                scope/'policy_intent_coverage.parquet',protocol_path,costs,eligibility,
                Path('service/fr/portfolio_replay_12b.py'),Path('service/fr/execution_costs.py'),Path(__file__)]}
    result = {'status': 'PROTOCOL_FROZEN_ECONOMIC_REPLAY_BLOCKED', **counts,
              'preparation_complete': True, 'sprint_13_complete': False,
              'gates': {'common_execution_evidence': counts['all_paths_qualified'],
                        'benchmark_total_return': False, 'qualified_execution_tapes': False,
                        'us_cn_representative_run_hashes': False},
              'protocol': frozen, 'input_hashes': hashes, 'net_pnl': None,
              'executed_orders': 0, 'models_refit': 0, 'canonical_writes': False,
              'serving_enabled': False, 'confirmation_2026_evaluated': False,
              'created_at': datetime.now(ZoneInfo('Europe/Paris')).isoformat()}
    output.mkdir(parents=True,exist_ok=False)
    (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'protocol.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
