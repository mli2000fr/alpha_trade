"""Prepare a future full-window pilot from existing archives, without collection or inference."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from pathlib import Path

from common.market_calendar import get_market_calendar
from service.fr.daily_feature_adapter_16b import action_checks, master_at, observed_payloads, select_bars
from service.fr.issuer_pilot_16g import PILOT, checked, select_candidates
from service.fr.prediction_contract_16a import ROOT, aware, scoped_path


def window(calendar, anchor, count):
    if type(count) is not int or count != 21:
        raise ValueError('Frozen feature contract requires 21 sessions')
    sessions = calendar.session_dates(anchor + timedelta(days=1), anchor + timedelta(days=90))[:count]
    if len(sessions) != count or len(set(sessions)) != count or sessions != sorted(sessions):
        raise ValueError('Incomplete or invalid XPAR window')
    if sessions[0] <= anchor:
        raise ValueError('Window must follow anchor')
    decision = calendar.next_session(sessions[-1])
    return sessions, decision, calendar.session(decision).open_at_utc


def validate(protocol):
    if (protocol.get('market_code'), protocol.get('calendar'), protocol.get('status')) != (
            'FR_EQ', 'XPAR', 'PREPARATION_ONLY_NOT_RELEASED'):
        raise ValueError('FR preparation-only protocol required')
    for field in ('serving_allowed', 'orders_allowed', 'sql_writes',
                  'model_inference_allowed', 'model_refit_allowed'):
        if protocol.get(field) is not False:
            raise ValueError('Preparation cannot enable capabilities')
    if protocol['pilot_symbols'] != list(PILOT):
        raise ValueError('Frozen three-name pilot required')
    if protocol.get('future_oracle_min_cross_section', 20) != 20:
        raise ValueError('Oracle cross-section requirement cannot be lowered by pilot')


def prepare(protocol, *, root=ROOT, now=None, calendar=None, phase='prepare'):
    validate(protocol)
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError('Aware actual inventory time required')
    calendar = calendar or get_market_calendar('FR_EQ', allow_us_weekday_fallback=False)
    anchor = date.fromisoformat(protocol['anchor_full_date'])
    sessions, decision, opening = window(calendar, anchor, protocol['warmup_sessions'])
    if phase not in ('prepare', 'confirm'):
        raise ValueError('Unknown phase')
    if phase == 'confirm' and now < opening:
        raise ValueError('Actual planned opening has not occurred')
    cutoff = opening if phase == 'confirm' else now
    packet_path = scoped_path(protocol['source_packet'], root)
    packet, packet_hash = checked(packet_path)
    candidates = select_candidates(packet)
    replay_path = scoped_path(protocol['preanchor_replay'], root)
    replay, replay_hash = checked(replay_path)
    if (replay['source_packet_sha256'] != packet_hash or replay['start'] != str(anchor)
            or replay['end'] != '2026-09-25' or replay['status'] != 'PREANCHOR_RESERVED'
            or replay['market_code'] != 'FR_EQ' or replay['anomalies']
            or replay['missing_publication_days'] or aware(replay['created_at']) > cutoff):
        raise ValueError('Replay is not a matched completed anchor reconstruction')
    if set(replay['sessions_before_new_anchor']) != {'2026-09-09', '2026-09-10', '2026-09-11'}:
        raise ValueError('Unexpected inherited window reserves')
    proofs = {str(packet_path): packet_hash, str(replay_path): replay_hash}
    bars, actions, errors = [], [], []
    bootstrap = scoped_path(protocol['bootstrap_dir'], root)
    for base in (root / 'artifacts/fr/operations', bootstrap):
        action_folder = 'corporate_actions' if base == bootstrap else 'fr_corporate_actions_sync'
        for folder, destination in (('eodhd_daily', bars), (action_folder, actions)):
            payloads, issues = observed_payloads(base / folder, cutoff, root, proofs)
            destination.extend(payloads)
            errors.extend(issues)
    closed = [day for day in sessions if calendar.session(day).close_at_utc <= cutoff]
    future = [str(day) for day in sessions if day not in closed]
    matrix = []
    for symbol, identity in candidates.items():
        try:
            values, missing = select_bars(bars, symbol, closed, calendar, cutoff)
            bar_error = None
        except (KeyError, ValueError, TypeError) as exc:
            values, missing, bar_error = [], [str(d) for d in closed], str(exc)[:160]
        matrix.append({'symbol': symbol, 'isin': identity['isin'], 'mic': identity['mic'],
            'valid_closed_session_bars': len(values), 'missing_closed_sessions': missing,
            'not_yet_closed_sessions': future, 'bar_error': bar_error,
            'provider_action_coverage_reserves': action_checks(actions, symbol, sessions),
            'trading_currency_interval_qualified': False, 'actions_independently_qualified': False,
            'servable': False})
    last_closed = closed[-1] if closed else None
    master, reasons, master_errors = master_at(root / 'artifacts/fr/operations/fr_security_master_sync',
        cutoff, last_closed or sessions[0], root, proofs)
    return {'market_code': 'FR_EQ', 'status': ('OPENING_INVENTORY_CONFIRMED_NOT_RELEASED'
        if phase == 'confirm' else 'FUTURE_WINDOW_PREPARED_NOT_RELEASED'),
        'phase': phase, 'prepared_at': now.isoformat(), 'inventory_cutoff': cutoff.isoformat(),
        'inventory_semantics': ('AS_KNOWN_AT_FROZEN_OPENING_NOT_RELEASE' if phase == 'confirm'
                                else 'AS_KNOWN_NOW_NOT_FUTURE_DECISION_PROOF'),
        'protocol': protocol, 'protocol_sha256': hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest(),
        'required_sessions': [str(d) for d in sessions], 'planned_decision_date': str(decision),
        'planned_decision_at': opening.isoformat(), 'closed_session_count': len(closed),
        'not_yet_closed_sessions': future, 'matrix': matrix,
        'current_master_end': master.get('end') if master else None,
        'current_master_reserves': reasons, 'archive_errors': errors + master_errors,
        'pilot_is_not_oracle_selection_universe': True, 'future_oracle_min_cross_section': 20,
        'proofs_sha256': proofs, 'original_test_changed': False,
        'future_reference_chain_qualified': False, 'future_release_qualified': False,
        'required_release_evidence': {
            'trading_currency': ['exact_ISIN_MIC', 'currency', 'effective_from', 'effective_to',
                                 'source_document_hash', 'actual_observed_at', 'qualified_at'],
            'corporate_actions': ['exact_ISIN_MIC', 'event_type', 'effective_session',
                                  'ratio_or_cash_terms_if_applicable', 'source_document_hash',
                                  'actual_observed_at', 'qualified_at', 'window_coverage_scope'],
            'reference': 'Checked Full September 12 and every Delta fragment through October 12',
            'availability': 'All evidence and qualifications actually available before decision opening',
            'model': 'Feature transform parity, model lineage/release and Sprint 15 operational reserves'},
        'model_inference_executed': False, 'serving_allowed': False, 'orders_allowed': False,
        'sql_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', default='config/research_fr/prospective_window_16g.json')
    parser.add_argument('--phase', choices=('prepare', 'confirm'), default='prepare')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    config = (ROOT / args.protocol).resolve()
    if not config.is_relative_to(ROOT / 'config/research_fr'):
        parser.error('FR research protocol required')
    output = scoped_path(args.output_dir, ROOT)
    if output.exists():
        parser.error('New output directory required')
    report = prepare(json.loads(config.read_text(encoding='utf-8')), phase=args.phase)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('status', 'planned_decision_at', 'closed_session_count',
                                         'not_yet_closed_sessions', 'matrix')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
