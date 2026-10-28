"""Exact immutable local evidence and run binding, separate from LLM tables."""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'artifacts' / 'options_directional'
PROTOCOL = 'options-volume-oi-equal-rank-v1'


def dumps(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, default=str)


def digest(value):
    return hashlib.sha256(dumps(value).encode('utf-8')).hexdigest()


def directory(run_id, root=None):
    if not isinstance(run_id, str) or not re.fullmatch(r'opt-[a-f0-9]{32}', run_id):
        raise ValueError('Identifiant exact filtre options requis')
    return (Path(root) if root is not None else ROOT) / run_id


def write_new(path, value):
    # No overwrites, retries never silently replace a published selection/claim.
    with path.open('x', encoding='utf-8') as stream:
        stream.write(dumps(value))


def seal(run_id, report, inputs, *, root=None):
    folder = directory(run_id, root)
    folder.mkdir(parents=True, exist_ok=False)
    write_new(folder / 'inputs.json', inputs)
    report = {**report, 'protocol': PROTOCOL, 'inputs_sha256': digest(inputs)}
    write_new(folder / 'report.json', report)
    write_new(folder / 'seal.json', {'report_sha256': digest(report), 'inputs_sha256': digest(inputs)})
    return report


def validate_window(day, now=None, calendar=None):
    from common.market_calendar import get_market_calendar
    now = now or datetime.now(timezone.utc)
    day = date.fromisoformat(str(day))
    if now.tzinfo is None:
        raise ValueError('Cutoff UTC explicite requis')
    calendar = calendar or get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    if day not in calendar.session_dates(day, day):
        raise ValueError('Date options hors séance US')
    _, close = calendar.session_bounds(day)
    next_open, _ = calendar.session_bounds(calendar.next_session(day))
    if not close <= now < next_open:
        raise ValueError('Filtre options : attendre clôture J et agir avant ouverture J+1')


def qualified(run_id, *, trade_date, batch_id=None, account_id='default', symbol_source=None,
              capital_preset_key=None, now=None, root=None):
    folder = directory(run_id, root)
    report, inputs, seal_data = [json.loads((folder / name).read_text(encoding='utf-8'))
                                for name in ('report.json', 'inputs.json', 'seal.json')]
    if (digest(report) != seal_data['report_sha256'] or digest(inputs) != seal_data['inputs_sha256']
            or report['inputs_sha256'] != digest(inputs) or report.get('protocol') != PROTOCOL):
        raise ValueError('Archive filtre options altérée')
    if report['status'] != 'COMPLETED' or report['run_id'] != run_id:
        raise ValueError('Filtre options non finalisé')
    for key, value in [('trade_date', str(trade_date)), ('account_id', account_id),
                       ('batch_id', batch_id), ('symbol_source', symbol_source),
                       ('capital_preset_key', capital_preset_key)]:
        if value is not None and report[key] != value:
            raise ValueError(f'Filtre options incompatible : {key}')
    now = now or datetime.now(timezone.utc)
    cutoff = datetime.fromisoformat(report['cutoff_utc'])
    if not cutoff <= now <= cutoff + timedelta(hours=report['config']['max_age_hours']):
        raise ValueError('Filtre options périmé ou futur')
    validate_window(trade_date, now)
    selected = [r['symbol'] for r in report['rows'] if r['selected']]
    if selected != report['selected'] or len(selected) != len(set(selected)):
        raise ValueError('Sélection options incohérente')
    return report


def latest_matching(**kwargs):
    """Manual 11/12 only: latest exact context, never another date/batch/account."""
    root = kwargs.get('root') or ROOT
    matches = []
    for file in (*Path(root).glob('opt-*/report.json'), *Path(root).glob('opt-*/failure.json')):
        try:
            report = json.loads(file.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        if all(value is None or report.get(key) == str(value) for key, value in kwargs.items()
               if key in ('trade_date', 'batch_id', 'account_id', 'symbol_source', 'capital_preset_key')):
            matches.append(report)
    if not matches:
        raise ValueError('Aucun filtre options terminé pour cette date/modèle/univers ; lancer étape 10')
    latest = max(matches, key=lambda r: (r['cutoff_utc'], r['run_id']))
    if latest.get('status') != 'COMPLETED':
        raise ValueError('Dernière analyse options échouée pour ce périmètre ; '
                         'aucune ancienne sélection substituée. Corriger puis relancer étape 10.')
    # A newer corrupt/expired exact-context run must fail, never silently use an older selection.
    return qualified(latest['run_id'], **kwargs)
