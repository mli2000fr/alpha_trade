"""Anonymous Euronext option OI collection, research SQL only.

Uses the same public directory/form/chain requests as the website. No login,
commercial feed, endpoint probing, inferred expiry day or invented OI date.
"""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import uuid

from bs4 import BeautifulSoup
from sqlalchemy import text

from common.public_data_http import verified_session
from database.router import get_market_engine
from service.fr.consensus_daily import reference_scope
from service.inpi.files import atomic

BASE = 'https://live.euronext.com'
DIRECTORY = BASE + '/en/markets/paris/stock-options/list'
BATCH = 'fr_options_open_interest_sync'
TABLES = ('fr_option_oi_public_runs', 'fr_option_oi_public_responses', 'fr_option_oi_public_contracts')


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def check_schema(engine):
    if engine.url.database != 'alpha_trade_fr':
        raise ValueError('OI options FR limitée à alpha_trade_fr')
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade_fr':
            raise ValueError('Base physique FR contradictoire')
        for table in TABLES:
            conn.execute(text(f'SELECT * FROM {table} LIMIT 0'))


def validate_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc != 'live.euronext.com' or p.fragment:
        raise ValueError('URL publique Euronext hors périmètre')
    if p.path == '/robots.txt':
        return
    if p.path == urlsplit(DIRECTORY).path:
        query = parse_qs(p.query)
        if set(query) <= {'page'} and all(len(v) == 1 and v[0].isdigit() for v in query.values()):
            return
    if not p.query and re.fullmatch(
        r'/en/ajax/(?:getUnderlying/[A-Za-z0-9]+/DPAR/options|'
        r'getPricesOptionsForm/[A-Za-z0-9]+/DPAR|'
        r'(?:getPricesOptionsAjax|submitOptionsForm)/stock-options/[A-Za-z0-9]+/DPAR)', p.path):
        return
    raise ValueError('Endpoint non utilisé par le collecteur public')


def parse_directory(body, url):
    soup = BeautifulSoup(body, 'html.parser')
    rows = []
    for tr in soup.select('main table tbody tr'):
        link = tr.select_one('.views-field-field-contract-name a')
        isin = tr.select_one('.views-field-field-contract-underlying-isin')
        code = tr.select_one('.views-field-field-contract-code')
        if not link or not isin or not code:
            raise ValueError('Schéma du répertoire options modifié')
        product_url = urljoin(BASE, link['href'])
        match = re.fullmatch(r'/en/product/stock-options/([a-z0-9]+)-dpar', urlsplit(product_url).path, re.I)
        if urlsplit(product_url).netloc != 'live.euronext.com' or not match:
            raise ValueError('Produit du répertoire hors Paris')
        product_code, underlying = code.get_text(strip=True).upper(), isin.get_text(strip=True)
        if match[1].upper() != product_code or not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', underlying):
            raise ValueError('Identité de produit publique contradictoire')
        rows.append(dict(product_code=product_code, underlying_isin=underlying,
                         product_name=link.get_text(' ', strip=True), product_url=product_url))
    if not rows:
        raise ValueError('Répertoire public vide ou schéma modifié')
    current = int(parse_qs(urlsplit(url).query).get('page', ['0'])[0])
    candidates = []
    for a in soup.find_all('a', href=True):
        href = urljoin(url, a['href'])
        if urlsplit(href).path == urlsplit(DIRECTORY).path:
            value = parse_qs(urlsplit(href).query).get('page', [])
            if len(value) == 1 and value[0].isdigit() and int(value[0]) > current:
                validate_url(href)
                candidates.append((int(value[0]), href))
    if candidates and min(candidates)[0] != current+1:
        raise ValueError('Pagination publique non contiguë')
    return rows, min(candidates)[1] if candidates else None


def parse_months(body):
    soup = BeautifulSoup(body, 'html.parser')
    values = [o.get('value') for o in soup.select('#maturityDates option')]
    if not values or len(set(values)) != len(values):
        raise ValueError('Échéances publiques absentes ou dupliquées')
    for value in values:
        if datetime.strptime(value, '%d-%m-%Y').day != 1:
            raise ValueError('Sélecteur de mois inattendu')
    return sorted(values, key=lambda v: datetime.strptime(v, '%d-%m-%Y'))


def parse_underlying(body, expected_isin):
    soup = BeautifulSoup(body, 'html.parser')
    matches = []
    for tr in soup.select('tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) >= 2 and cells[0].get_text(strip=True) == 'ISIN':
            matches.append(cells[1].get_text(strip=True))
    if matches != [expected_isin]:
        raise ValueError('Sous-jacent public différent du référentiel FR')


def integer(value):
    value = str(value).strip().replace('\xa0', ' ')
    if value in ('', '-', 'None'):
        return None, 'MISSING'
    if not re.fullmatch(r'(?:\d+|\d{1,3}(?:[, ]\d{3})+)', value):
        return None, 'INVALID'
    number = int(value.replace(',', '').replace(' ', ''))
    return (number, 'NUMERIC_ONLY') if number <= 2**63-1 else (None, 'INVALID')


def decimal(value):
    try:
        result = Decimal(str(value).replace(',', '').replace(' ', ''))
        return result if result.is_finite() and abs(result) < Decimal('1e26') and result.as_tuple().exponent >= -12 else None
    except InvalidOperation:
        return None


def parse_chain(body, product, months):
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get('extended'), list):
        raise ValueError('Réponse de chaîne publique non reconnue')
    records, seen, returned_months = [], set(), set()
    for group in data['extended']:
        volume_raw = group.get('volumeDate')
        volume_date = datetime.strptime(volume_raw, '%d/%m/%y').date() if volume_raw not in (None, '', '-') else None
        if volume_date and volume_date > datetime.now(UTC).date():
            raise ValueError('Date de volume future')
        for side, field in (('CALL', 'rowc'), ('PUT', 'rowp')):
            for row in group[field]:
                anchor = BeautifulSoup(row['strike'], 'html.parser').find('a', href=True)
                if anchor is None:
                    raise ValueError('Identité du contrat public absente')
                url = urljoin(BASE, anchor['href'])
                p, q = urlsplit(url), parse_qs(urlsplit(url).query)
                if (p.netloc != 'live.euronext.com'
                    or p.path.lower() != f'/en/product/stock-options/{product["product_code"].lower()}-dpar/instrument'
                    or q.get('Class_symbol') != [product['product_code']]
                    or q.get('Class_exchange') != ['DPAR'] or q.get('cOrP') != [side[0]]):
                    raise ValueError('Contrat public hors produit/côté demandé')
                selector = q.get('md', [None])[0]
                if selector not in months:
                    raise ValueError('Mois retourné hors sélection explicite')
                returned_months.add(selector)
                strike = decimal(anchor.get_text(strip=True))
                if strike is None or strike <= 0:
                    raise ValueError('Strike public invalide')
                oi, quality = integer(row.get('open_interest'))
                settlement = decimal(row.get('settl'))
                if oi is not None and settlement is not None and Decimal(oi) == settlement:
                    oi, quality = None, 'AMBIGUOUS_SETTLEMENT'
                volume, volume_quality = integer(row.get('daily_vol'))
                key = digest(encoded([product['product_code'], side, str(strike), selector]).encode())
                if key in seen:
                    raise ValueError('Contrat public dupliqué/conflictuel')
                seen.add(key)
                raw_oi, raw_volume = str(row.get('open_interest', '')), str(row.get('daily_vol', ''))
                if max(len(raw_oi), len(raw_volume)) > 128:
                    raise ValueError('Valeur publique anormalement longue')
                records.append(dict(contract_key=key, symbol=product['symbol'],
                    underlying_isin=product['underlying_isin'], product_code=product['product_code'], venue='DPAR',
                    option_type=side, strike=format(strike, 'f'), maturity_selector=selector,
                    expiry_month=datetime.strptime(selector, '%d-%m-%Y').date(), expiration_date=None,
                    contract_isin=None, oi_raw=raw_oi, open_interest=oi, oi_reference_date=None,
                    volume_date=volume_date, daily_volume_raw=raw_volume, daily_volume=volume,
                    settlement_price=format(settlement, 'f') if settlement is not None else None,
                    quality_status=quality, quality_json=encoded(dict(oi_date_qualified=False,
                        expiration_day_qualified=False, volume_quality=volume_quality, product_url=product['product_url'])),
                    raw_row_json=encoded(row), ml_eligible=False))
    if returned_months != set(months):
        raise ValueError('Mois demandés non retournés par la chaîne publique')
    return records


def insert(conn, table, rows):
    if table not in TABLES:
        raise ValueError('Table OI publique inconnue')
    if rows:
        query = text(f'INSERT INTO {table} ({",".join(rows[0])}) '
                     f'VALUES ({",".join(":"+key for key in rows[0])})')
        for start in range(0, len(rows), 300):
            conn.execute(query, rows[start:start+300])


def collect(cfg, result, *, root, identities, dry_run=False, max_symbols=None,
            engine=None, fetcher=None, sleep=time.sleep):
    _, scope, _ = reference_scope(identities)
    selected = cfg.get('selected_symbols')
    if selected is not None:
        if not selected or not set(selected) <= set(scope):
            raise ValueError('Sélection OI hors univers FR vérifié')
        scope = {s: scope[s] for s in selected}
    if max_symbols is not None:
        if max_symbols < 1:
            raise ValueError('Limite de titres invalide')
        scope = dict(sorted(scope.items())[:max_symbols])
    universe = {r['isin']: symbol for symbol, (r, _) in scope.items()}
    pace = float(cfg.get('request_interval_seconds', 1.0))
    max_calls, max_products = int(cfg.get('max_http_requests', 800)), int(cfg.get('max_products', 200))
    max_pages, max_months = int(cfg.get('max_directory_pages', 12)), int(cfg.get('max_maturity_months', 3))
    max_seconds = int(cfg.get('max_runtime_seconds', 1200))
    if any(type(cfg.get(k, True)) is not bool for k in ('exclude_weeklies', 'exclude_minis')):
        raise ValueError('Exclusions produits OI : booléens requis')
    if (not universe or len(universe) != len(scope) or not 0.5 <= pace <= 60
            or not 1 <= max_calls <= 2000 or not 1 <= max_products <= 400
            or not 1 <= max_pages <= 20 or not 1 <= max_months <= 12 or not 30 <= max_seconds <= 1800):
        raise ValueError('Budgets OI publique ou univers invalides')
    result.update(requested_count=len(universe), received_count=0, persisted_count=0,
        requested_unit='underlying_symbols', received_unit='symbols_with_public_chain',
        persisted_unit='public_contract_observations', sql_writes=not dry_run, ml_eligible=False,
        directional_filter_ready=False, historical_pit_qualified=False, parser_version='public_oi_v1_form_submission',
        http_requests=0, numeric_oi_rows=0, invalid_oi_rows=0, missing_oi_rows=0, products=0,
        coverage={s: {'state': 'NO_PUBLIC_PRODUCT_DISCOVERED'} for s in scope}, errors=[])
    if dry_run:
        return
    owned = engine is None
    engine = engine if engine is not None else get_market_engine('FR_EQ', database_alias='fr_primary')
    run = 'fr-public-oi-'+datetime.now(UTC).strftime('%Y%m%d%H%M%S')+'-'+uuid.uuid4().hex[:8]
    started = time.monotonic()
    rules = None
    result['run_id'] = run
    run_created, status = False, 'FAILED'
    try:
        check_schema(engine)
        with engine.begin() as conn:
            insert(conn, TABLES[0], [dict(run_id=run, market_code='FR_EQ', started_at=datetime.now(UTC).replace(tzinfo=None),
                finished_at=None, status='RUNNING', config_json=encoded(cfg), details_json=encoded(result))])
        run_created = True
        atomic(root/'progress.json', {**result, 'status':'RUNNING', 'updated_at':datetime.now(UTC).isoformat()})
        with verified_session() as session:
            session.headers.update({'User-Agent': 'AlphaTrade-Research/1.0', 'X-Requested-With': 'XMLHttpRequest'})

            def get(method, url, params=None):
                validate_url(url)
                if rules is not None and not rules.can_fetch('AlphaTrade-Research', url):
                    raise PermissionError('Accès refusé par robots.txt')
                if result['http_requests'] >= max_calls or time.monotonic()-started >= max_seconds:
                    raise RuntimeError('Budget de collecte publique atteint, couverture incomplète')
                if result['http_requests']:
                    sleep(pace)
                result['http_requests'] += 1
                if fetcher:
                    body, code = fetcher(method, url, params)
                else:
                    with session.request(method, url, data=params, timeout=30, allow_redirects=False, stream=True) as response:
                        code = response.status_code
                        chunks, length = [], 0
                        for chunk in response.iter_content(65536):
                            length += len(chunk)
                            if length > 4_000_000:
                                raise RuntimeError('Réponse publique trop volumineuse')
                            chunks.append(chunk)
                        body = b''.join(chunks)
                observed = datetime.now(UTC).replace(tzinfo=None)
                response_id = digest((run+':'+str(result['http_requests'])).encode())
                raw_hash = digest(body)
                target = root/'raw'/raw_hash
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    with target.open('xb') as stream:
                        stream.write(body)
                if digest(target.read_bytes()) != raw_hash:
                    raise ValueError('Archive OI publique corrompue')
                with engine.begin() as conn:
                    insert(conn, TABLES[1], [dict(response_id=response_id, run_id=run, endpoint=url, method=method,
                        request_json=encoded(params or {}), http_status=code, body_sha256=raw_hash, body=body,
                        observed_at=observed, available_at=None, parse_status='RECEIVED')])
                atomic(root/'receipts'/f'{response_id}.json', dict(response_id=response_id, run_id=run,
                    url=url, request=params, http_status=code, body_sha256=raw_hash, observed_at=str(observed),
                    ml_eligible=False))
                if code != 200:
                    finish(response_id, 'HTTP_ERROR')
                    if code in (401,403,429) or 300 <= code < 400:
                        raise PermissionError(f'Collecte publique arrêtée : HTTP {code}, aucun contournement')
                    raise RuntimeError(f'Page publique HTTP {code}')
                return body, response_id

            def finish(response_id, status='METADATA', rows=None):
                with engine.begin() as conn:
                    if rows:
                        insert(conn, TABLES[2], [dict(response_id=response_id, **row) for row in rows])
                    conn.execute(text('UPDATE fr_option_oi_public_responses SET parse_status=:status '
                        'WHERE response_id=:id'), dict(status=status,id=response_id))
                # Actual SQL availability is confirmed after body/rows commit.
                with engine.begin() as conn:
                    conn.execute(text('UPDATE fr_option_oi_public_responses SET available_at=:stamp '
                        'WHERE response_id=:id AND available_at IS NULL'),
                        dict(stamp=datetime.now(UTC).replace(tzinfo=None),id=response_id))

            body, response_id = get('GET', BASE+'/robots.txt')
            if not re.search(r'^User-agent\s*:', body.decode('utf-8'), flags=re.I|re.M):
                raise ValueError('robots.txt absent ou non reconnaissable')
            rules = RobotFileParser()
            rules.parse(body.decode('utf-8').splitlines())
            finish(response_id)
            products, visited, url = {}, set(), DIRECTORY
            for _ in range(max_pages):
                if url in visited:
                    raise ValueError('Boucle de pagination du répertoire')
                visited.add(url)
                body, response_id = get('GET', url)
                page, following = parse_directory(body, url)
                finish(response_id)
                for p in page:
                    if p['underlying_isin'] not in universe:
                        continue
                    if cfg.get('exclude_weeklies', True) and 'weekly' in p['product_name'].lower():
                        continue
                    if cfg.get('exclude_minis', True) and 'mini' in p['product_name'].lower():
                        continue
                    p['symbol'] = universe[p['underlying_isin']]
                    old = products.get(p['product_code'])
                    if old and old != p:
                        raise ValueError('Produit public contradictoire entre pages')
                    products[p['product_code']] = p
                if not following:
                    break
                url = following
            else:
                raise RuntimeError('Répertoire tronqué par la limite de pages')
            if len(products) > max_products:
                raise RuntimeError('Nombre de produits au-delà du budget, aucun TOP arbitraire')
            result.update(products=len(products), directory_complete=True)
            print(f'FR OI public univers={len(universe)} produits={len(products)} run={run}',flush=True)
            for p in products.values():
                result['coverage'][p['symbol']] = {'state':'PENDING'}
            received = set()
            for p in products.values():
                code = p['product_code']
                try:
                    body, rid = get('GET', BASE+f'/en/ajax/getUnderlying/{code}/DPAR/options')
                    parse_underlying(body,p['underlying_isin']); finish(rid)
                    body, rid = get('GET', BASE+f'/en/ajax/getPricesOptionsForm/{code}/DPAR')
                    months = parse_months(body); finish(rid)
                    selected_months = months[:max_months]
                    # Refresh uses the session selection, not its posted values.
                    # Apply the public form first, or only the compact first month appears.
                    selection = {'ps':'999','md[]':selected_months}
                    body, rid = get('POST', BASE+f'/en/ajax/submitOptionsForm/stock-options/{code}/DPAR', selection)
                    if not BeautifulSoup(body, 'html.parser').select('[id^="price_option_details_"]'):
                        raise ValueError('Soumission du formulaire public non reconnue')
                    finish(rid)
                    body, rid = get('POST', BASE+f'/en/ajax/getPricesOptionsAjax/stock-options/{code}/DPAR',
                                    selection)
                    rows = parse_chain(body,p,selected_months)
                    finish(rid,'CONTRACTS',rows)
                    result['persisted_count'] += len(rows)
                    counts = Counter(row['quality_status'] for row in rows)
                    result['numeric_oi_rows'] += counts['NUMERIC_ONLY']
                    result['missing_oi_rows'] += counts['MISSING']
                    result['invalid_oi_rows'] += counts['INVALID']+counts['AMBIGUOUS_SETTLEMENT']
                    if rows:
                        received.add(p['symbol'])
                    result['coverage'][p['symbol']] = dict(state='UNQUALIFIED_PUBLIC_OBSERVATION',
                        last_product=code, months_selected=selected_months, months_available=len(months))
                except PermissionError:
                    raise
                except Exception as exc:
                    result['errors'].append(dict(symbol=p['symbol'],product=code,error=str(exc)))
                    result['coverage'][p['symbol']] = dict(state='PARTIAL_OR_FAILED',error=str(exc))
                    if 'Budget' in str(exc):
                        raise
                result['received_count'] = len(received)
                atomic(root/'progress.json', {**result, 'status':'RUNNING', 'updated_at':datetime.now(UTC).isoformat()})
                print(f'FR OI public {code}: lignes={result["persisted_count"]} OI_numérique={result["numeric_oi_rows"]}',flush=True)
            result['warning_count'] = result.get('warning_count',0)+int(bool(result['invalid_oi_rows']))+1
            result['qualification_notice'] = 'Mois uniquement, dates exactes expiration/OI absentes ; interdit filtre/ML'
            if result['errors'] or not received:
                raise RuntimeError('Collecte OI publique incomplète ; réponses et lignes partielles conservées')
        status = 'PARTIAL'  # Collection completed, but data is deliberately not promoted.
    except Exception as exc:
        result['collection_error'] = str(exc)
        status = 'FAILED'
        raise
    finally:
        try:
            result['data_status'] = status
            result['failed_count'] = max(result.get('failed_count', 0), len(result['errors']), int(status == 'FAILED'))
            if run_created:
                with engine.begin() as conn:
                    conn.execute(text('UPDATE fr_option_oi_public_runs SET status=:status,finished_at=:stamp,'
                        'details_json=:details WHERE run_id=:run'), dict(status=status,
                        stamp=datetime.now(UTC).replace(tzinfo=None),details=encoded(result),run=run))
                atomic(root/'reports'/f'{run}.json', {**result, 'status': status})
                atomic(root/'progress.json', {**result, 'status':status, 'updated_at':datetime.now(UTC).isoformat()})
        finally:
            if owned:
                engine.dispose()
