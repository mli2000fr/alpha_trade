"""UI command helpers, no provider or database calls."""
from datetime import date
from pathlib import Path
import sys
from common.universe_files import list_universe_file_sources, universe_file_source_from_path, universe_file_label
from service.market.intraday_backfill import DEFAULT_SOURCE, intraday_defaults

PROJECT_ROOT=Path(__file__).resolve().parents[2]


def universe_options():
    sources=list(list_universe_file_sources())
    directory=PROJECT_ROOT/'config/univers_batch'
    if directory.is_dir():
        sources.extend(universe_file_source_from_path(p,root=PROJECT_ROOT) for p in sorted(directory.glob('*.txt')))
    return tuple(dict.fromkeys(sources))


def build_command(start:date,end:date,source:str,interval='5m',chunk_days=30,refresh=False,max_tasks=None,
                  *,provider=None,alpaca_feed=None,account_id=None):
    defaults=intraday_defaults()
    provider=provider or defaults['provider'];alpaca_feed=alpaca_feed or defaults['alpaca_feed']
    account_id=account_id or defaults['account_id']
    if provider not in ('alpaca','eodhd') or alpaca_feed not in ('iex','sip'):raise ValueError('Fournisseur/flux invalide')
    if end<start:raise ValueError('La date de fin precede la date de debut')
    if interval not in ('1m','5m','1h'):raise ValueError('Intervalle invalide')
    if source not in universe_options():raise ValueError('Univers non disponible')
    if not 1<=chunk_days<=120:raise ValueError('Tranche invalide')
    command=[sys.executable,'-u','-m','service.market.intraday_backfill',
        '--start-date',start.isoformat(),'--end-date',end.isoformat(),
        '--symbol-source',source,'--interval',interval,'--chunk-days',str(chunk_days),'--provider',provider]
    if provider=='alpaca':command.extend(['--alpaca-feed',alpaca_feed,'--account-id',account_id])
    if refresh:command.append('--refresh')
    if max_tasks is not None:
        if max_tasks<1:raise ValueError('Nombre de tranches invalide')
        command.extend(['--max-tasks',str(max_tasks)])
    return command
