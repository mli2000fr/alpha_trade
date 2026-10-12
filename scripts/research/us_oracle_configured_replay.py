"""One offline Oracle replay using configurable exits; no fit, SQL or orders.

Existing historical grids stay frozen. This entry point records today's policy
in a NEW output directory rather than rewriting their protocols or results.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from backtesting.oracle_exit_policy import load_oracle_backtest_exit_policy
from common.config_loader import load_config, override_config_path, resolve_config_path
from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research import us_oracle_barrier_exit_grid as grid
from scripts.research.us_concentrated_contract_audit import frozen_backtest_config
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_oracle_barrier_comparison import ARMS, COUNTS, read
from scripts.research.us_oracle_barrier_grid_summary import verify_trade_contract
from service.market import parse_market_regimes


def configured_case(year, count, arm, policy):
    if type(year) is not int or year not in (2025, 2026):
        raise ValueError('Année supportée : 2025 ou 2026')
    if type(count) is not int or count not in COUNTS or arm not in ARMS:
        raise ValueError('TOP10/20/50 et modèle de comparaison figé requis')
    return year, count, arm, 'CONFIGURED', policy.take_profit_pct, policy.stop_loss_pct


def run(inputs, output, *, year=2026, count=10, arm='NEW_BARRIER_LONG', config=None):
    inputs, output = Path(inputs), Path(output)
    config_path = resolve_config_path(config).resolve()
    with override_config_path(config_path):
        policy = load_oracle_backtest_exit_policy()
        case = configured_case(year, count, arm, policy)
        prepared = read(inputs/'prepared.json')
        verify_hashes(inputs, prepared['files'])
        input_protocol = read(inputs/'input-protocol.json')
        verify_hashes(Path('.'), input_protocol['source_hashes'])
        original = read(Path(input_protocol['source'])/'protocol.json')
        risk = frozen_backtest_config('2025-01-01', original['as_of'])
        market = parse_market_regimes(load_config().get('market_regimes'))
        # The strategy contract does not change risk, fees, sectors or ranking.
        if (json.loads(json.dumps(asdict(risk.risk_config), default=str)) != original['portfolio']['risk']
                or json.loads(json.dumps(asdict(market), default=str)) != original['portfolio']['market']):
            raise ValueError('Risque/régime différents des inputs : qualifier une nouvelle campagne')
        code = [Path(__file__), Path('backtesting/oracle_exit_policy.py'),
            Path(grid.__file__), Path('scripts/research/us_concentrated_live_portfolio.py'),
            Path('scripts/research/us_oracle_merger_ledger.py'),
            Path('scripts/research/us_oracle_barrier_comparison.py'),
            Path('scripts/research/us_concentrated_contract_audit.py'),
            Path('backtesting/oracle_portfolio_ledger.py'), Path('backtesting/oracle_portfolio_session.py'),
            Path('backtesting/simulator.py'), config_path]
        hashes = {str(path): digest(path) for path in code}
        protocol = dict(case=case, exit_policy=asdict(policy), trailing=False,
            entry='J+1 open; actual fill anchors TP/SL', expiry='21st holding-session open',
            inputs=str(inputs.resolve()), prepared_sha256=digest(inputs/'prepared.json'),
            input_protocol_sha256=digest(inputs/'input-protocol.json'), source_hashes=hashes,
            input_source_hashes=input_protocol['source_hashes'],
            side='LONG', training=False, sql_writes=False, broker_orders=False, production_changed=False)
        # No overwrite/resume of an old experiment with a newly selected policy.
        output.mkdir(parents=True, exist_ok=False)
        atomic_json(output/'protocol.json', protocol)
        atomic_json(output/'progress.json', dict(status='RUNNING', case=case))
        try:
            grid.worker_init(str(inputs))
            result = grid.run_case(case, str(output))
            if result['status'] == 'FAILED':
                raise RuntimeError(str(result.get('failures', result)))
            trades = pd.read_parquet(Path(result['output'])/'trades.parquet')
            if not trades.empty and not trades['side'].astype(str).str.lower().eq('buy').all():
                raise ValueError('Ce replay est LONG uniquement')
            calendar = nyse_sessions(pd.Timestamp('2024-01-01').date(), pd.Timestamp(original['as_of']).date())
            result['trade_contract_audit'] = verify_trade_contract(trades, policy.take_profit_pct,
                                                                  policy.stop_loss_pct, calendar)
            verify_hashes(inputs, prepared['files'])
            verify_hashes(Path('.'), input_protocol['source_hashes'])
            for path, expected in hashes.items():
                if digest(path) != expected:
                    raise ValueError(f'Code/config changé pendant le replay : {path}')
            if (digest(inputs/'prepared.json') != protocol['prepared_sha256']
                    or digest(inputs/'input-protocol.json') != protocol['input_protocol_sha256']):
                raise ValueError('Provenance des inputs modifiée pendant le replay')
            result.update(exit_policy=asdict(policy), trailing=False, input_hashes_verified=True,
                          training=False, sql_writes=False, broker_orders=False, production_changed=False)
            atomic_json(output/'report.json', result)
            atomic_json(output/'progress.json', dict(status=result['status'], completed=1, total=1))
            return result
        except Exception as exc:
            failure = dict(status='FAILED', error_type=type(exc).__name__, error=str(exc))
            atomic_json(output/'report.json', failure)
            atomic_json(output/'progress.json', failure)
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Nouveau répertoire, jamais une ancienne campagne')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--year', type=int, choices=(2025, 2026), default=2026)
    parser.add_argument('--count', type=int, choices=COUNTS, default=10)
    parser.add_argument('--arm', choices=tuple(ARMS), default='NEW_BARRIER_LONG')
    result = run(**vars(parser.parse_args()))
    print(f"{result['status']} : TP {result['tp_pct']:.0%} / SL {result['sl_pct']:.0%}, sans trailing")
