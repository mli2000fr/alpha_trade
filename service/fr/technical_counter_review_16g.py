"""Second technical reading by the same assistant; not independent attestation."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import xml.sax
from xml.sax.handler import ContentHandler, feature_external_ges, feature_external_pes
import zipfile

from service.fr.prediction_contract_16a import ROOT, scoped_path
from service.fr.qualification_dossier_16g import read_proof
from service.fr.release_review_check_16g import check

FIELDS = {
    ('FinInstrmGnlAttrbts', 'Id'): 'isin',
    ('TradgVnRltdAttrbts', 'Id'): 'mic',
    ('FinInstrmGnlAttrbts', 'NtnlCcy'): 'currency',
    ('FinInstrmGnlAttrbts', 'ClssfctnTp'): 'cfi',
    ('FinInstrmGnlAttrbts', 'FullNm'): 'name',
    ('TradgVnRltdAttrbts', 'FrstTradDt'): 'first_trade_reported',
    ('TradgVnRltdAttrbts', 'TermntnDt'): 'termination_reported',
    ('TechAttrbts', 'PblctnPrd', 'FrDt'): 'publication_from_reported',
}


class TargetReader(ContentHandler):
    """SAX reader distinct from the replay's ElementTree parser, bounded to targets."""
    def __init__(self, pairs):
        super().__init__()
        self.pairs, self.stack, self.text, self.current = pairs, [], [], None
        self.matches, self.records = [], 0

    def startElement(self, name, attrs):
        name = name.split(':')[-1]
        self.stack.append(name)
        self.text = []
        if name in {'RefData', 'FinInstrm'}:
            self.current = {'event': 'Full' if name == 'RefData' else None}
        elif self.current is not None and len(self.stack) > 1 and self.stack[-2] == 'FinInstrm':
            if name not in {'NewRcrd', 'ModfdRcrd', 'TermntdRcrd', 'CancRcrd'}:
                raise ValueError('Unknown Delta event')
            self.current['event'] = name

    def characters(self, content):
        self.text.append(content)

    def endElement(self, name):
        name = name.split(':')[-1]
        if self.current is not None:
            for suffix, field in FIELDS.items():
                if tuple(self.stack[-len(suffix):]) == suffix:
                    self.current[field] = ''.join(self.text).strip() or None
            if name in {'RefData', 'FinInstrm'}:
                self.records += 1
                if (self.current.get('isin'), self.current.get('mic')) in self.pairs:
                    self.matches.append(self.current)
                self.current = None
        self.stack.pop()
        self.text = []


def scan(path, pairs):
    reader = TargetReader(pairs)
    parser = xml.sax.make_parser()
    parser.setFeature(feature_external_ges, False)
    parser.setFeature(feature_external_pes, False)
    parser.setContentHandler(reader)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].endswith('.xml'):
            raise ValueError('Single XML member required')
        with archive.open(names[0]) as stream:
            parser.parse(stream)
    return reader.records, reader.matches


def publication_check(files, start, end):
    groups = {}
    names = set()
    for item in files:
        name = Path(item['path']).name
        match = re.fullmatch(r'(FULINS_E|DLTINS)_(\d{8})_(\d+)of(\d+)\.zip', name)
        if not match or name in names:
            raise ValueError('Unexpected or duplicate fragment')
        names.add(name)
        day = datetime.strptime(match[2], '%Y%m%d').date()
        if str(day) != item['date'] or item['type'] != match[1]:
            raise ValueError('Fragment date/type mismatch')
        if (match[1] == 'FULINS_E' and day != start) or (match[1] == 'DLTINS' and not start < day <= end):
            raise ValueError('Fragment outside review interval')
        groups.setdefault((match[1], day), []).append((int(match[3]), int(match[4])))
    required = {('FULINS_E', start)}
    day = start + timedelta(days=1)
    while day <= end:
        required.add(('DLTINS', day))
        day += timedelta(days=1)
    if set(groups) != required:
        raise ValueError('Missing publication day')
    for parts in groups.values():
        totals = {total for _, total in parts}
        if len(totals) != 1 or sorted(n for n, _ in parts) != list(range(1, next(iter(totals)) + 1)):
            raise ValueError('Incomplete fragment numbering')


def run(packet_path, *, root=ROOT, progress=None):
    root = root.resolve()
    handoff = check(packet_path, root=root)
    packet, digest = read_proof(scoped_path(str(packet_path), root))
    replay, _ = read_proof(scoped_path(packet['replay_report'], root))
    start, end = date.fromisoformat(replay['full_date']), date.fromisoformat(replay['end'])
    publication_check(replay['files'], start, end)
    pairs = {(r['isin'], r['mic']) for r in packet['matrix']}
    full, deltas, files = [], [], []
    for index, item in enumerate(replay['files'], 1):
        path = scoped_path(item['path'], root)
        md5 = hashlib.md5()  # Published checksum verification, not security identity.
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                md5.update(block)
        if not item['official_md5_available'] or md5.hexdigest() != item['md5']:
            raise ValueError('Official MD5 check unavailable or inconsistent')
        count, selected = scan(path, pairs)
        (full if item['type'] == 'FULINS_E' else deltas).extend(selected)
        files.append({'path': item['path'], 'records_scanned': count, 'target_records': len(selected)})
        if progress:
            progress(index, len(replay['files']), path.name)
    counts = Counter((r['isin'], r['mic']) for r in full)
    duplicates_or_missing = [list(pair) for pair in sorted(pairs) if counts[pair] != 1]
    actual = {(r['isin'], r['mic']): r for r in full}
    differences = []
    for row in replay['comparisons']:
        pair = (row['isin'], row['mic'])
        expected = row['current_payload']
        changed = [field for field, value in expected.items() if actual.get(pair, {}).get(field) != value]
        if changed:
            differences.append({'symbol': row['symbol'], 'fields': changed})
    # This review intentionally does not reuse the event application logic.
    # With target deltas it cannot conclude unchanged; a separate event review is needed.
    passed = not duplicates_or_missing and not differences and not deltas
    return {'schema_version': 1, 'market_code': 'FR_EQ',
        'review_kind': 'SAME_ASSISTANT_TECHNICAL_COUNTER_REVIEW', 'reviewer': 'Codex same assistant',
        'independence_declared': False, 'reviewed_at': datetime.now(UTC).isoformat(),
        'packet_sha256': digest, 'status': 'TECHNICAL_COUNTER_REVIEW_PASSED_WITH_RESERVES' if passed else 'TECHNICAL_COUNTER_REVIEW_RESERVED',
        'different_xml_reader': 'xml.sax (replay uses ElementTree)', 'same_source_archives': True,
        'archive_count': len(files), 'evidence_files_verified': handoff['evidence_files_verified'],
        'full_target_records': len(full), 'delta_target_records': len(deltas),
        'duplicate_or_missing_pairs': duplicates_or_missing, 'payload_differences': differences,
        'files': files, 'remaining_gates': packet['remaining_gates'],
        'independent_human_review_completed': False,
        'decision': 'RECORD_TECHNICAL_COUNTER_REVIEW_NOT_RELEASE',
        'serving_allowed': False, 'orders_allowed': False, 'sql_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed = (ROOT / 'artifacts/fr/research/release_review_16g3').resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error('New isolated FR review folder required')
    output.mkdir(parents=True, exist_ok=False)
    def progress(done, total, name):
        with (output / 'journal.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'done': done, 'total': total, 'file': name}) + '\n')
        print(f'{done}/{total} {name}', flush=True)
    result = run(args.packet, progress=progress)
    with (output / 'report.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
    print(result['status'], flush=True)


if __name__ == '__main__':
    main()
