"""Daily FR EODHD observations, versioned on disk, never canonical SQL bars."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

from common.market_calendar import get_market_calendar
from service.fr.eodhd_backfill import _fetch
from service.fr.load_eodhd_staging import classify_bar


def atomic(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str), encoding='utf-8')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def symbols_from_identities(path: Path) -> list[str]:
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    symbols = sorted({r['provider_symbol'] for r in rows if r.get('identity_state') == 'VERIFIED_RESEARCH'
                      and r.get('provider_status_current') == 'active'})
    if not symbols or any(not s.endswith('.PA') or '/' in s or '\\' in s for s in symbols):
        raise ValueError('Univers FR vérifié absent ou symbole non Paris')
    return symbols


def collect(cfg: dict, result: dict, *, root: Path, identities: Path, dry_run=False,
            today: date | None = None, resume=False, max_symbols: int | None = None):
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
    symbols = symbols_from_identities(identities)
    if max_symbols is not None:
        symbols = symbols[:max_symbols]
    if len(symbols) > int(cfg.get('max_symbol_requests', 400)):
        raise ValueError('Univers au-delà du budget de requêtes configuré')
    result.update(requested_count=len(symbols), window=[str(start), str(end)],
                  requested_unit='symbols', received_unit='symbols', persisted_unit='bar_rows',
                  sql_writes=False, universe_sha256=hashlib.sha256(identities.read_bytes()).hexdigest(),
                  unchanged_rows=0, changed_rows=0, resumed_symbols=0, errors=[],
                  universe_basis='FROZEN_S6C_CURRENT_ACTIVE_NOT_DAILY_MASTER')
    if dry_run:
        return
    token = os.environ.get('EODHD_API_TOKEN')
    if not token:
        raise ValueError('EODHD_API_TOKEN absent')
    root.mkdir(parents=True, exist_ok=True)
    lock = root/'.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError('Collecte FR déjà verrouillée ; vérifier le processus avant de retirer .lock') from None
    with os.fdopen(fd, 'w') as stream:
        stream.write(json.dumps({'pid':os.getpid(),'started_at':datetime.now(UTC).isoformat()}))
    try:
        state_path = root/'windows'/f'{start}_{end}.json'
        state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'symbols': {}}
        state.update(window=[str(start),str(end)], market_code='FR_EQ')
        sessions = set(get_market_calendar('FR_EQ').session_dates(start, end))
        for index, symbol in enumerate(symbols, 1):
            key = hashlib.sha256(symbol.encode()).hexdigest()
            prior = state['symbols'].get(symbol, {})
            # Resume only explicit; regular reruns refetch to discover vendor corrections.
            if resume and prior.get('status') == 'COMPLETED':
                raw = root/'raw'/f"{prior['sha256']}.json"
                latest = root/'latest'/f'{key}.json'
                if (raw.exists() and latest.exists()
                    and hashlib.sha256(raw.read_bytes()).hexdigest() == prior['sha256']
                    and hashlib.sha256(latest.read_bytes()).hexdigest() == prior.get('latest_sha256')):
                    result['resumed_symbols'] += 1
                    continue
            try:
                rows = _fetch(f'eod/{quote(symbol, safe=".")}', token, {'from':str(start),'to':str(end),'period':'d'}, pace=pace)
                observed = datetime.now(UTC).isoformat()
                result['received_count'] += 1
                raw_content = {'symbol':symbol,'window':[str(start),str(end)],'rows':rows}
                payload = json.dumps(raw_content, ensure_ascii=False, sort_keys=True, default=str).encode()
                digest = hashlib.sha256(payload).hexdigest()
                raw = root/'raw'/f'{digest}.json'
                raw.parent.mkdir(parents=True, exist_ok=True)
                if not raw.exists():
                    atomic(raw, raw_content)
                if hashlib.sha256(raw.read_bytes()).hexdigest() != digest:
                    raise ValueError('Archive brute corrompue')
                atomic(root/'observations'/key/f'{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json',
                       {'symbol':symbol,'window':[str(start),str(end)],'observed_at':observed,
                        'available_at':observed,'raw_sha256':digest,'rows':len(rows)})
                prepared = {}
                for row in rows:
                    session, quality, _ = classify_bar(row, sessions)
                    if not start <= session <= end or str(session) in prepared:
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
                latest = json.loads(latest_path.read_text(encoding='utf-8')) if latest_path.exists() else {'symbol':symbol,'market_code':'FR_EQ','bars':{}}
                persisted = changed = unchanged = 0
                for session, item in prepared.items():
                    old = latest['bars'].get(session)
                    if old and old['row'] == item['row']:
                        unchanged += 1
                        continue  # Keep first availability of this unchanged version.
                    changed += int(old is not None)
                    latest['bars'][session] = item
                    persisted += 1
                atomic(latest_path, latest)
                result['persisted_count'] += persisted
                result['changed_rows'] += changed
                result['unchanged_rows'] += unchanged
                state['symbols'][symbol] = {'status':'COMPLETED','sha256':digest,'rows':len(rows),'observed_at':observed,
                    'latest_sha256':hashlib.sha256(latest_path.read_bytes()).hexdigest()}
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
        lock.unlink(missing_ok=True)
