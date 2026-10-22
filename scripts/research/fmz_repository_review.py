"""Archive and screen public strategy documents; never execute downloaded code.

Only GitHub is contacted. No market-data API, SQL, trading or model calls.
The screen is mechanical, not a profitability assessment or a human code audit.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import quote

from common.verified_http import verified_session


LAST = 'The-Bollinger-Band-Automated-Trading-Strategy.md'
FIRST_PREFIX = '1-2-3-形态与-EMAMACD-和第四根蜡烛线延伸'
LOCAL = threading.local()
FAMILIES = {
    'volatility_compression': r'squeeze|compression|compressed|收缩|挤压|压缩',
    'breakout': r'breakout|突破|donchian|唐奇安|opening.range',
    'failed_breakout_retest': r'false.break|failed.break|retest|假突破|回踩|回测确认',
    'vwap_volume': r'\bvwap\b|\bvwma\b|volume.profile|relative.volume|成交量分布|量价|相对成交量',
    'mean_reversion': r'mean.rever|均值回归|回归均值|bollinger|布林|布林格',
    'trend': r'trend.follow|趋势|supertrend|moving.average|均线',
    'momentum': r'\brsi\b|\bmacd\b|momentum|动量|\badx\b',
    'adaptive_efficiency': r'kaufman|efficiency.ratio|\bkama\b|hurst|fractal|考夫曼|效率比|分形',
    'session_gap': r'opening.range|overnight|开盘|隔夜|gap|跳空',
    'pairs_statistical': r'cointegration|pairs.trad|statistical.arbitrage|协整|配对|统计套利',
    'grid_averaging': r'martingale|网格|马丁|safety.order|averag(?:e|ing).down|摊平|补仓',
    'microstructure': r'order.book|order.flow|订单簿|订单流|做市|market.mak|高频',
    'exit_management': r'trailing|chandelier|止损|止盈|移动止|跟踪止',
    'reinforcement': r'pyramid|加仓|增仓|金字塔',
}
FLAGS = {
    'lookahead_on_literal': r'\b(?:barmerge\.)?lookahead_on\b|lookahead\s*:\s*true',
    'security_or_multitimeframe': r'(?:request\.)?security\s*\(',
    'pivot_confirmation': r'(?:ta\.)?pivot(?:high|low)\s*\(|zigzag',
    'negative_visual_offset': r'offset\s*=\s*-',
    'intrabar_or_same_close': r'calc_on_every_tick\s*=\s*true|process_orders_on_close\s*=\s*true',
    'averaging_vocabulary': FAMILIES['grid_averaging'],
    'commission_literal': r'commission_(?:type|value)|slippage\s*=',
    'code_license_notice': r'mozilla.org/MPL|MIT License|GNU (?:General|Affero)|SPDX-License',
    'crypto_venue_literal': r'Futures_Binance|BTC_USDT|ETH_USDT|BitMEX|OKCoin|Huobi',
}


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def session():
    if not hasattr(LOCAL, 'http'):
        LOCAL.http = verified_session()
        LOCAL.http.headers.update({'User-Agent': 'AlphaTrade-public-strategy-review'})
    return LOCAL.http


def get(url: str):
    for attempt in range(4):
        response = session().get(url, timeout=45)
        if response.status_code not in (429, 500, 502, 503, 504):
            response.raise_for_status()
            return response
        if attempt == 3:
            response.raise_for_status()
        pause = min(60, max(2 ** attempt, float(response.headers.get('Retry-After', 0))))
        time.sleep(pause)
    raise AssertionError('unreachable')


def select_range(tree):
    files = sorted((item for item in tree if item['type'] == 'blob'
                    and '/' not in item['path'] and item['path'].endswith('.md')),
                   key=lambda item: item['path'])
    starts = [i for i, item in enumerate(files) if item['path'].startswith(FIRST_PREFIX)]
    ends = [i for i, item in enumerate(files) if item['path'] == LAST]
    if len(starts) != 1 or len(ends) != 1 or starts[0] > ends[0]:
        raise ValueError('Range endpoints missing or ambiguous')
    return files[starts[0]:ends[0] + 1]


def snippets(content, pattern, count=3):
    output = []
    for match in re.finditer(pattern, content, re.I):
        start = content.rfind('\n', 0, match.start()) + 1
        end = content.find('\n', match.end())
        line = content[start:end if end >= 0 else len(content)].strip()
        output.append({'line': content.count('\n', 0, start) + 1, 'text': line[:350]})
        if len(output) >= count:
            break
    return output


def screen(item, body, commit):
    content = body.decode('utf-8-sig')
    name = item['path']
    fence = content.find('```')
    prose = content[:fence] if fence >= 0 else content
    families = [key for key, pattern in FAMILIES.items() if re.search(pattern, content, re.I)]
    title_families = [key for key, pattern in FAMILIES.items() if re.search(pattern, name, re.I)]
    flags = {key: snippets(content, pattern) for key, pattern in FLAGS.items()
             if re.search(pattern, content, re.I)}
    # Labels describe source concepts, not proven causal behavior or profitability.
    return {
        'path': name, 'git_blob_sha1': item['sha'], 'sha256': hashlib.sha256(body).hexdigest(),
        'bytes': len(body), 'lines': len(content.splitlines()),
        'source_url': f'https://github.com/fmzquant/strategies/blob/{commit}/{quote(name)}',
        'title_families': title_families, 'content_families': families,
        'flags_for_manual_check': flags,
        'description_excerpt': prose[:1800],
        'status': 'FETCHED_HASH_VERIFIED_MECHANICAL_SCREEN',
    }


def fetch_one(item, root, commit):
    destination = root / 'raw' / (item['sha'] + '.md')
    body = destination.read_bytes() if destination.exists() else get(
        f'https://raw.githubusercontent.com/fmzquant/strategies/{commit}/{quote(item["path"])}').content
    git_sha = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
    if git_sha != item['sha']:
        raise ValueError('Git blob hash mismatch: ' + item['path'])
    if not destination.exists():
        destination.write_bytes(body)
    row = screen(item, body, commit)
    row['local_raw'] = str(destination.relative_to(root))
    return row


def index_markdown(rows, commit):
    lines = ['# Inventaire FMZ — criblage intégral automatisé', '',
             f'Commit figé : `{commit}`. {len(rows)} documents lus et vérifiés.', '',
             'Ce tableau ne constitue pas une revue manuelle de chaque stratégie. '
             'Les familles et alertes sont des correspondances textuelles, pas des '
             'preuves de rentabilité, de bug ou d’anticipation.', '',
             '| N° | Document source | Familles du titre | Alertes à examiner | Revue ciblée |',
             '|---:|---|---|---|---|']
    for number, row in enumerate(rows, 1):
        title = row['path'].replace('|', '\\|')
        families = ', '.join(row['title_families']) or 'non classé automatiquement'
        flags = ', '.join(row['flags_for_manual_check']) or 'aucune alerte textuelle détectée'
        note = row.get('targeted_code_review', {}).get('note', 'Criblage seulement, pas audit détaillé')
        lines.append(f'| {number} | [{title}]({row["source_url"]}) | {families} | {flags} | {note.replace("|", "/")} |')
    return '\n'.join(lines) + '\n'


def attach_targeted_review(rows, annotations, commit):
    if annotations['commit'] != commit:
        raise ValueError('Targeted review commit differs from snapshot')
    count = 0
    for annotation in annotations['entries']:
        matches = [row for row in rows if row['path'].startswith(annotation['prefix'])]
        if len(matches) != 1 or 'targeted_code_review' in matches[0]:
            raise ValueError('Targeted review prefix missing, ambiguous or duplicated')
        matches[0]['targeted_code_review'] = dict(annotation)
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=6, choices=range(1, 9))
    parser.add_argument('--targeted-review', type=Path)
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    (root / 'raw').mkdir(exist_ok=True)
    tree_path = root / 'tree.json'
    tree = json.loads(tree_path.read_text(encoding='utf-8')) if tree_path.exists() else get(
        'https://api.github.com/repos/fmzquant/strategies/git/trees/master?recursive=1').json()
    if tree.get('truncated'):
        raise ValueError('GitHub tree truncated: refuse partial inventory')
    if not tree_path.exists():
        save(tree_path, tree)
    selected = select_range(tree['tree'])
    commit = tree['sha']
    save(root / 'scope.json', {'commit': commit, 'count': len(selected),
         'first': selected[0]['path'], 'last': selected[-1]['path'],
         'sort': 'Unicode ordinal / Git UTF-8 filename order, inclusive endpoints',
         'review_level': 'full-file mechanical screening, not manual review of every implementation',
         'no_remote_code_executed': True, 'files': selected})
    rows, failures = [], []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_one, item, root, commit): item for item in selected}
        for future in as_completed(futures):
            item = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:
                failures.append({'path': item['path'], 'error': f'{type(exc).__name__}: {exc}'})
            completed = len(rows) + len(failures)
            if completed % 50 == 0 or completed == len(selected):
                progress = {'status': 'RUNNING', 'completed': completed, 'total': len(selected),
                            'failed': len(failures), 'elapsed_seconds': round(time.monotonic()-started, 1)}
                save(root / 'progress.json', progress)
                print(json.dumps(progress), flush=True)
    rows.sort(key=lambda row: row['path'])
    targeted_count = 0
    if args.targeted_review:
        targeted_count = attach_targeted_review(rows, json.loads(
            args.targeted_review.read_text(encoding='utf-8')), commit)
    save(root / 'screening.json', rows)
    (root / 'index.md').write_text(index_markdown(rows, commit), encoding='utf-8')
    summary = {
        'status': 'COMPLETED_SCREENING' if not failures else 'PARTIAL_FAILED',
        'commit': commit, 'expected': len(selected), 'read_and_hash_verified': len(rows),
        'failures': failures, 'review_level': 'mechanical screening of full document contents',
        'targeted_code_reviews_attached': targeted_count, 'no_performance_test': True,
        'family_counts_title': dict(Counter(f for row in rows for f in row['title_families'])),
        'flag_counts': dict(Counter(f for row in rows for f in row['flags_for_manual_check'])),
        'bytes': sum(row['bytes'] for row in rows), 'lines': sum(row['lines'] for row in rows),
        'finished_at_utc': datetime.now(timezone.utc).isoformat(),
    }
    save(root / 'report.json', summary)
    save(root / 'progress.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
