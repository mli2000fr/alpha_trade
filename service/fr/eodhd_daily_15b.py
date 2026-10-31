"""Daily FR EODHD observations, SQL primary in operational sessions, never canonical bars."""
from __future__ import annotations

from service.fr.collection_storage import (active, read_bytes, read_text, exists, paths, write_bytes, identity_rows, take_lock, release_lock)

import gzip
import hashlib
import json
import math
import os
import time
from pathlib import Path
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

from common.market_calendar import get_market_calendar
from service.fr.eodhd_backfill import _fetch
from service.fr.load_eodhd_staging import classify_bar


def atomic(path: Path, payload: dict):
    if active():
        from service.fr.collection_storage import write_json
        return write_json(path,payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str), encoding='utf-8')
        # Windows readers/antivirus may briefly deny atomic replacement. Never
        # delete the destination or fall back to an in-place partial JSON write.
        for attempt in range(10):
            try:
                temp.replace(path)
                break
            except OSError as exc:
                transient = isinstance(exc, PermissionError) or getattr(exc, 'winerror', None) in (5, 32, 33)
                if not transient or attempt == 9:
                    raise
                time.sleep(min(.05 * 2 ** attempt, .5))
    finally:
        try:
            temp.unlink(missing_ok=True)
        except PermissionError:
            # Preserve the original replacement error rather than masking it.
            pass


def symbols_from_identities(path: Path) -> list[str]:
    rows = identity_rows(path)
    symbols = sorted({r['provider_symbol'] for r in rows if r.get('identity_state') == 'VERIFIED_RESEARCH'
                      and r.get('provider_status_current') == 'active'})
    if not symbols or any(not s.endswith('.PA') or '/' in s or '\\' in s for s in symbols):
        raise ValueError('Univers FR vérifié absent ou symbole non Paris')
    return symbols


def exclude_symbols(windows, excluded_symbols=None):
    """Operational scope only: never edit the frozen reference or old data."""
    if excluded_symbols is None:
        return windows
    if (not isinstance(excluded_symbols, list)
            or any(not isinstance(s, str) for s in excluded_symbols)
            or len(set(excluded_symbols)) != len(excluded_symbols)
            or not set(excluded_symbols).issubset(windows)):
        raise ValueError('excluded_symbols : liste unique de codes présents dans l’univers FR requise')
    selected = {s: bounds for s, bounds in windows.items() if s not in excluded_symbols}
    if not selected:
        raise ValueError('Univers FR vide après exclusions')
    return selected


def symbol_windows(path, start, end, migrations=None, *, excluded_symbols=None):
    """Reviewed, dated provider-code changes; no cross-venue substitution.

    Keep the frozen reference and old archives unchanged. New provider codes
    are collected/staged under their real names, never under a legacy alias.
    """
    windows = {s: (start, end) for s in symbols_from_identities(path)}
    if migrations is None:
        return exclude_symbols(windows, excluded_symbols)
    if not isinstance(migrations, list):
        raise ValueError('provider_symbol_migrations doit être une liste')
    records = identity_rows(path)
    seen = set()
    replacements = set()
    for migration in migrations:
        old, new = migration['old_symbol'], migration['new_symbol']
        matching = [r for r in records if r.get('provider_symbol') == old
                    and r.get('identity_state') == 'VERIFIED_RESEARCH'
                    and r.get('provider_status_current') == 'active']
        if (old in seen or new in replacements or new in windows or old not in windows
                or old == new or not isinstance(new, str) or not new.endswith('.PA')
                or not new[:-3].isalnum() or len(matching) != 1
                or matching[0].get('isin') != migration['isin']
                or migration.get('currency') != 'EUR' or migration.get('new_mic') != 'ALXP'
                or not migration.get('evidence_url', '').startswith('https://')
                or not migration.get('provider_checked_at')):
            raise ValueError('Migration code FR non qualifiée, ambiguë ou hors Paris')
        effective = date.fromisoformat(migration['effective_from'])
        observed = datetime.fromisoformat(migration['provider_checked_at'])
        if observed.tzinfo is None or observed > datetime.now(UTC):
            raise ValueError('Date de vérification fournisseur invalide')
        seen.add(old); replacements.add(new)
        del windows[old]
        if start < effective:
            windows[old] = (start, min(end, effective-timedelta(days=1)))
        if end >= effective:
            windows[new] = (max(start, effective), end)
    return exclude_symbols(dict(sorted(windows.items())), excluded_symbols)


def collect(cfg: dict, result: dict, *, root: Path, identities: Path, dry_run=False,
            today: date | None = None, resume=False, max_symbols: int | None = None,
            selected_symbols: list[str] | None = None):
    now = datetime.now(ZoneInfo('Europe/Paris'))
    day = today or now.date()
    lookback = int(cfg.get('lookback_days', 7))
    pace = float(cfg.get('request_interval_seconds', 0.5))
    close_hour = int(cfg.get('after_close_hour_paris', 22))
    if not 18 <= close_hour <= 23:
        raise ValueError('Heure de sécurité après clôture Paris : 18..23 requise')
    if not 1 <= lookback <= 31 or not math.isfinite(pace) or pace < 0.1:
        raise ValueError('Fenêtre 1..31 jours et intervalle >=0.1 seconde requis')
    if max_symbols is not None and max_symbols < 1:
        raise ValueError('max_symbols doit être positif')
    # Never request an unfinished current session. Scheduler normally runs 22h Paris.
    end = day if today is not None or now.hour >= close_hour else day-timedelta(days=1)
    start = day-timedelta(days=lookback)
    windows = symbol_windows(identities, start, end, cfg.get('provider_symbol_migrations'),
                             excluded_symbols=cfg.get('excluded_symbols'))
    symbols = list(windows)
    if selected_symbols is not None:
        if (not selected_symbols or len(selected_symbols) != len(set(selected_symbols))
                or not set(selected_symbols).issubset(symbols)):
            raise ValueError('Sélection absente, dupliquée ou hors univers FR vérifié')
        symbols = sorted(selected_symbols)
        result['limited_smoke'] = True
        result['selected_symbols'] = symbols
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    if len(symbols) > int(cfg.get('max_symbol_requests', 400)):
        raise ValueError('Univers au-delà du budget de requêtes configuré')
    result.update(requested_count=len(symbols), window=[str(start), str(end)],
                  requested_unit='symbols', received_unit='symbols', persisted_unit='bar_rows',
                  sql_writes=False, universe_sha256=hashlib.sha256(read_bytes(identities)).hexdigest(),
                  unchanged_rows=0, changed_rows=0, resumed_symbols=0, errors=[],
                  universe_basis='FROZEN_S6C_CURRENT_ACTIVE_NOT_DAILY_MASTER')
    if cfg.get('excluded_symbols'):
        result['excluded_symbols'] = cfg['excluded_symbols']
    if cfg.get('provider_symbol_migrations'):
        result['provider_symbol_migrations'] = cfg['provider_symbol_migrations']
        result['symbol_request_windows'] = {s: [str(d) for d in windows[s]] for s in symbols}
    if dry_run:
        return
    token = os.environ.get('EODHD_API_TOKEN')
    if not token:
        raise ValueError('EODHD_API_TOKEN absent')
    root.mkdir(parents=True, exist_ok=True) if not active() else None
    lock = take_lock(root/'.lock')
    try:
        state_path = root/'windows'/f'{start}_{end}.json'
        state = json.loads(read_text(state_path,encoding='utf-8')) if exists(state_path) else {'symbols': {}}
        state.update(window=[str(start),str(end)], market_code='FR_EQ')
        calendar = get_market_calendar('FR_EQ')
        for index, symbol in enumerate(symbols, 1):
            symbol_start, symbol_end = windows[symbol]
            sessions = set(calendar.session_dates(symbol_start, symbol_end))
            key = hashlib.sha256(symbol.encode()).hexdigest()
            prior = state['symbols'].get(symbol, {})
            # Resume only explicit; regular reruns refetch to discover vendor corrections.
            if (resume and prior.get('status') == 'COMPLETED'
                    and prior.get('coverage_complete') is True):
                raw = root/'raw'/f"{prior['sha256']}.json"
                latest = root/'latest'/f'{key}.json'
                if (exists(raw) and exists(latest)
                    and hashlib.sha256(read_bytes(raw)).hexdigest() == prior['sha256']
                    and hashlib.sha256(read_bytes(latest)).hexdigest() == prior.get('latest_sha256')
                    and json.loads(read_text(raw,encoding='utf-8')).get('window') == [str(symbol_start),str(symbol_end)]):
                    result['resumed_symbols'] += 1
                    continue
            try:
                rows = _fetch(f'eod/{quote(symbol, safe=".")}', token, {'from':str(symbol_start),'to':str(symbol_end),'period':'d'}, pace=pace)
                observed = datetime.now(UTC).isoformat()
                result['received_count'] += 1
                raw_content = {'symbol':symbol,'window':[str(symbol_start),str(symbol_end)],'rows':rows}
                payload = json.dumps(raw_content, ensure_ascii=False, sort_keys=True, default=str).encode()
                digest = hashlib.sha256(payload).hexdigest()
                raw = root/'raw'/f'{digest}.json'
                raw.parent.mkdir(parents=True, exist_ok=True) if not active() else None
                if not exists(raw):
                    atomic(raw, raw_content)
                if hashlib.sha256(read_bytes(raw)).hexdigest() != digest:
                    raise ValueError('Archive brute corrompue')
                atomic(root/'observations'/key/f'{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json',
                       {'symbol':symbol,'window':[str(symbol_start),str(symbol_end)],'observed_at':observed,
                        'available_at':observed,'raw_sha256':digest,'rows':len(rows)})
                prepared = {}
                for row in rows:
                    session, quality, _ = classify_bar(row, sessions)
                    if not symbol_start <= session <= symbol_end or str(session) in prepared:
                        raise ValueError('Date hors fenêtre ou dupliquée')
                    if quality not in ('VALID','ZERO_VOLUME'):
                        raise ValueError(f'Barre quarantinée {session}: {quality}')
                    prepared[str(session)] = {'row':row,'quality':quality,'observed_at':observed,'available_at':observed,'raw_sha256':digest}
                if not prepared and sessions:
                    raise ValueError('Réponse vide sur une fenêtre contenant des séances XPAR')
                missing = sorted(str(s) for s in sessions if str(s) not in prepared)
                if missing:
                    result['warning_count'] += 1
                    result.setdefault('coverage_warnings', []).append({'symbol':symbol,'missing_sessions':missing})
                latest_path = root/'latest'/f'{key}.json'
                latest = json.loads(read_text(latest_path,encoding='utf-8')) if exists(latest_path) else {'symbol':symbol,'market_code':'FR_EQ','bars':{}}
                persisted = changed = unchanged = 0
                for session, item in prepared.items():
                    old = latest['bars'].get(session)
                    if old and old['row'] == item['row']:
                        unchanged += 1
                        continue  # Keep first availability of this unchanged version.
                    changed += int(old is not None)
                    latest['bars'][session] = item
                    persisted += 1
                latest['last_coverage'] = {'window': [str(symbol_start), str(symbol_end)],
                    'missing_sessions': missing, 'observed_at': observed,
                    'raw_sha256': digest,
                    'retained_old_rows_not_reconfirmed': [s for s in missing if s in latest['bars']]}
                atomic(latest_path, latest)
                result['persisted_count'] += persisted
                result['changed_rows'] += changed
                result['unchanged_rows'] += unchanged
                state['symbols'][symbol] = {'status':'COMPLETED_WITH_GAPS' if missing else 'COMPLETED',
                    'coverage_complete': not missing, 'missing_sessions': missing,
                    'sha256':digest,'rows':len(rows),'observed_at':observed,
                    'latest_sha256':hashlib.sha256(read_bytes(latest_path)).hexdigest()}
            except Exception as exc:
                # _fetch strips signed URLs/tokens from its errors.
                message = str(exc)[:240]
                result['failed_count'] += 1
                result['errors'].append({'symbol':symbol,'error':message})
                state['symbols'][symbol] = {'status':'FAILED','error':message}
            atomic(state_path, state)
            print(f'FR EODHD quotidien {index}/{len(symbols)} reçus={result["received_count"]} persistés={result["persisted_count"]} échecs={result["failed_count"]}', flush=True)
        result['state_path'] = str(state_path)
        if result['failed_count']:
            raise RuntimeError(f'{result["failed_count"]} titre(s) en échec ; reprise disponible')
    finally:
        release_lock(lock)
