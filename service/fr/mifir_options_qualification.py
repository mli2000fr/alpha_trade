"""Offline qualification of archived MiFIR evidence; no promotion or SQL writes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from service.fr import mifir_options_poc as source
from service.inpi.files import atomic

SPEC = 'https://www.euronext.com/sites/default/files/euronext_cash_and_derivatives_markets_-_optiq_files_specifications_-_v2...._2.pdf'


def audit(snapshot):
    analysis = snapshot['analysis']
    accepted = analysis['accepted']
    universe = snapshot['universe']
    keys = [(r['Venue'], r['VenueOfPublication'], r['TradeUniqueIdentifier']) for r in accepted]
    invalid = []
    fractional = 0
    multipliers = Counter()
    mechanisms = Counter()
    for row in accepted:
        contract = row['contract']
        if (universe.get(contract['underlying_isin']) != contract['symbol']
                or contract['option_isin'] != row['MifidInstrumentID']):
            invalid.append('IDENTITY_JOIN')
        if source.instant(row['available_at']) > source.instant(snapshot['available_at']):
            invalid.append('AVAILABILITY')
        qty = source.number(row['MifidQuantity'])
        if qty <= 0:
            invalid.append('NONPOSITIVE_QUANTITY')
        fractional += qty != qty.to_integral_value()
        multipliers[contract['multiplier']] += 1
        mechanisms[row.get('MmtMarketMechanism', 'MISSING')] += 1
    covered = Counter(r['contract']['symbol'] for r in accepted)
    ratio = len(covered)/len(universe) if universe else None
    return {
        'status': 'TECHNICAL_FAILURE' if invalid or len(set(keys)) != len(keys) else 'PARTIAL_COLLECTION_VALIDATED_UNITS_NOT_QUALIFIED',
        'source_trade_dates': analysis['trade_dates'], 'requested_symbols': len(universe),
        'symbols_with_accepted_trades': len(covered), 'observed_activity_coverage': ratio,
        'symbols_without_accepted_trade': sorted(set(universe.values())-set(covered)),
        'accepted_trade_rows': len(accepted),
        'traded_option_series': len({r['MifidInstrumentID'] for r in accepted}),
        'duplicate_accepted_trade_keys': len(keys)-len(set(keys)),
        'validation_errors': dict(Counter(invalid)), 'fractional_quantity_rows': fractional,
        'multipliers': dict(multipliers), 'market_mechanisms': dict(mechanisms),
        'non_standard_multiplier_series': sorted({r['MifidInstrumentID'] for r in accepted
            if Decimal(r['contract']['multiplier']) not in (Decimal(10), Decimal(100))}),
        'quantity_fields': {k: dict(Counter(r.get(k, 'FIELD_ABSENT') for r in accepted))
            for k in ('MifidQtyInMeasurementUnitNotation', 'MifidQuantityMeasurementUnit')},
        'top_symbols_by_trade_rows': covered.most_common(10),
        'exclusion_counts': analysis['exclusion_counts'],
        'unit_assessment': {
            'quantity_unit_qualified': False, 'put_call_contract_volume_ratio': None,
            'documentation_source': SPEC, 'documentation_version': '2.6.1 (2019)',
            'measurement_fields_scope': 'commodity/emission measurement; blanks do not establish an option contract unit',
            'interpretation': 'integer quantities consistent with contract counts, not independently proven',
            'needed': ['current explicit Euronext mapping for this public CSV quantity',
                       'independent same-series/session contract-volume reconciliation',
                       'adjusted deliverables and multiplier qualification'],
        },
        'missing': ['open_interest', 'bid_ask', 'adjustment_history'],
        'ml_eligible': False, 'canonical': False,
        'historical_pit_qualified': False,
        'coverage_is_activity_not_complete_listed_options': True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--output-root', type=Path, default=Path('artifacts/fr/research/options_mifir_qualification'))
    args = parser.parse_args()
    raw = args.snapshot.read_bytes()
    report = audit(json.loads(raw))
    report.update(snapshot=str(args.snapshot.resolve()), snapshot_sha256=hashlib.sha256(raw).hexdigest(),
                  audited_at=datetime.now(timezone.utc).isoformat())
    path = args.output_root/(report['snapshot_sha256']+'.json')
    atomic(path, report)
    print(json.dumps({'report': str(path), 'status': report['status'],
                      'symbols': report['symbols_with_accepted_trades'], 'rows': report['accepted_trade_rows']}))
    if report['status'] == 'TECHNICAL_FAILURE':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
