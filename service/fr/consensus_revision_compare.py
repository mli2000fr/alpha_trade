"""Compare actual prospective observations on different Paris dates, without SQL."""
from datetime import datetime
import argparse
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from service.inpi.files import atomic


def load_observations(folder):
    report = json.loads((folder/'report.json').read_text(encoding='utf-8'))
    if report.get('status') != 'SUCCESS_RESEARCH_ONLY':
        raise ValueError('Collecte POC non réussie')
    rows = {}
    for path in sorted((folder/'observations').glob('*/*.json')):
        row = json.loads(path.read_text(encoding='utf-8'))
        target = Path(row['object_path']).resolve()
        if not target.is_relative_to(folder.resolve()/'objects'):
            raise ValueError('Objet hors dossier observation')
        payload = target.read_bytes()
        if hashlib.sha256(payload).hexdigest() != row['source_sha256']:
            raise ValueError('Objet corrompu')
        if row.get('identity_qualified') is not True:
            raise ValueError('Identité pilote non revue')
        if row.get('available_at') != row.get('observed_at'):
            raise ValueError('Provenance PIT inattendue')
        stamp = datetime.fromisoformat(row['observed_at'])
        if stamp.tzinfo is None:
            raise ValueError('Horodatage sans timezone')
        symbol = row['symbol']
        if symbol in rows:
            raise ValueError('Plusieurs observations du même titre dans le POC')
        rows[symbol] = (row, json.loads(payload), stamp)
    if not rows or len(rows) != report.get('persisted_count'):
        raise ValueError('Observations absentes ou compteurs incohérents')
    return rows


def flatten(value, prefix=''):
    if isinstance(value, dict):
        return {key: leaf for k, v in value.items()
                for key, leaf in flatten(v, prefix+'/'+str(k)).items()}
    return {prefix: value}


def compare(baseline, later):
    before, after = load_observations(baseline), load_observations(later)
    if set(before) != set(after):
        raise ValueError('Périmètres différents ; comparaison complète impossible')
    result = {'status': 'OBSERVED_DIFFERENCES_ONLY', 'baseline': str(baseline),
              'later': str(later), 'sql_writes': False, 'ml_eligible': False,
              'warning': 'Périodes 0y/+1y relatives : exercice non certifié. Changement observé ne prouve pas une révision à exercice constant.',
              'symbols': {}}
    for symbol in sorted(before):
        old_row, old, old_time = before[symbol]
        new_row, new, new_time = after[symbol]
        if (old_row['reference_identity']['isin'] != new_row['reference_identity']['isin']
            or old_row['identity_review'] != new_row['identity_review']):
            raise ValueError('Rattachement ou contrat identité différent')
        if new_time <= old_time or old_time.astimezone(ZoneInfo('Europe/Paris')).date() == new_time.astimezone(ZoneInfo('Europe/Paris')).date():
            raise ValueError('Deux dates Paris distinctes et chronologiques requises')
        for table in set(old['tables']) | set(new['tables']):
            old_table, new_table = old['tables'].get(table), new['tables'].get(table)
            if isinstance(old_table, dict) and isinstance(new_table, dict):
                if old_table.get('currency') != new_table.get('currency'):
                    raise ValueError('Devise/périodes de tableau différentes : unités à qualifier')
        a, b = flatten({'info': old['info'], 'tables': old['tables']}), flatten({'info': new['info'], 'tables': new['tables']})
        changes = []
        for field in sorted(set(a) | set(b)):
            x, y = a.get(field), b.get(field)
            if x == y:
                continue
            change = {'field': field, 'before': x, 'after': y, 'kind': 'VALUE_CHANGE'}
            if x is None or y is None:
                change['kind'] = 'COVERAGE_CHANGE'
            elif all(type(v) in (int, float) and math.isfinite(v) for v in (x, y)):
                change['delta'] = y-x
                change['relative_change'] = (y-x)/abs(x) if x != 0 else None
            changes.append(change)
        result['symbols'][symbol] = {'before_observed_at': old_time.isoformat(),
                                    'after_observed_at': new_time.isoformat(),
                                    'changes': changes, 'changed_fields': len(changes)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--later', type=Path, required=True)
    args = parser.parse_args()
    output = compare(args.baseline, args.later)
    atomic(args.later/'revision_comparison.json', output)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
