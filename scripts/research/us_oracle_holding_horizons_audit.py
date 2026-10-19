"""Offline controls for common cohorts, frozen memberships and horizon exits."""
import argparse
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_oracle_holding_horizons as study
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def key_hash(frame, columns):
    normalized = frame[columns].copy()
    for column in ('symbol', 'side'):
        if column in normalized: normalized[column] = normalized[column].astype(str)
    normalized = normalized.sort_values(study.KEYS).reset_index(drop=True)
    return sha256(pd.util.hash_pandas_object(normalized, index=False).values.tobytes()).hexdigest()


def audit(root):
    p = study.read(root/'protocol.json'); report = study.read(root/'report.json')
    verify_hashes(Path('.'), p['sources']); verify_hashes(root, report['files'])
    verify_hashes(root, report['case_reports']); manifest = study.read(root/'paths-manifest.json')
    verify_hashes(root, manifest['files'])
    assert report['protocol_sha256'] == digest(root/'protocol.json')
    from modelFactory.oracle.build_labels import nyse_sessions
    days = nyse_sessions('2023-01-01', '2026-10-09')
    rows = []; reference_keys = {}
    for name in p['profiles']:
        for scope, source in [('FULL_TRADABLE', study.FULL), ('ORACLE_TOP20PCT', study.TOP)]:
            reference = pd.read_parquet(source/name/'evaluations.parquet').sort_values(study.KEYS).reset_index(drop=True)
            ref_hash = key_hash(reference, study.KEYS+study.FLAGS+['entry_date', 'last_path_date'])
            h20_key = key_hash(reference, study.KEYS)
            if scope in reference_keys: assert reference_keys[scope] == h20_key
            reference_keys[scope] = h20_key
            h20_net = reference.net_outcome.to_numpy()
            independent_counts = {}
            for h in study.HORIZONS:
                folder = root/name/f'H{h}'
                case = study.read(folder/'report.json'); verify_hashes(folder, case['files'])
                assert case['protocol_sha256'] == digest(root/'protocol.json')
                f = pd.read_parquet(folder/f'{scope}.parquet').sort_values(study.KEYS).reset_index(drop=True)
                assert len(f) == len(reference) and not f.duplicated(study.KEYS).any()
                assert key_hash(f, study.KEYS+study.FLAGS+['entry_date', 'last_path_date']) == ref_hash
                assert f.entry_date.eq(days[days.get_indexer(f.date)+1]).all()
                assert f.holding_last_date.eq(days[days.get_indexer(f.date)+h]).all()
                assert f.exit_session.between(1, h).all()
                assert f.loc[f.outcome.eq('TIMEOUT'), 'exit_session'].eq(h).all()
                assert f.terminal_direction_right.eq(f.terminal_signed_return.gt(0)).all()
                recomputed = study.gate.attach_costs(f)
                for field in ('assumed_cost', 'assumed_borrow', 'net_outcome'):
                    np.testing.assert_array_equal(f[field], recomputed[field])
                early = reference.outcome.ne('TIMEOUT') & reference.exit_session.le(h)
                for field in ('outcome', 'exit_price', 'exit_session', 'path_return', 'net_outcome', 'tp_first', 'sl_first'):
                    np.testing.assert_array_equal(f.loc[early, field], reference.loc[early, field])
                if h < 20: assert f.loc[~early, 'outcome'].eq('TIMEOUT').all()
                if h == 20:
                    pd.testing.assert_frame_equal(f[reference.columns], reference, check_dtype=False, check_categorical=False)
                if name == 'TP10_NO_SL':
                    assert not f.sl_first.any() and not f.gap_stop.any() and not f.ambiguity.any()
                result = case['results'][scope]
                for row in result['summary']:
                    group = study.gate.chosen(f[f.year.eq(row['year'])], row['arm'])
                    assert row['n'] == len(group)
                    assert abs(row['mean_net_outcome']-float(group.net_outcome.mean())) < 1e-12
                    assert abs(row['profitable_rate']-float(group.net_outcome.gt(0).mean())) < 1e-12
                counts = {(r['year'], r['arm']): r['n'] for r in result['nonoverlapping']}
                if independent_counts: assert counts == independent_counts
                independent_counts = counts
                # Check the year/arm paired daily deltas use the same selected keys.
                delta = f.net_outcome.to_numpy()-h20_net
                for row in result['paired_h20']:
                    group = study.gate.chosen(f[f.year.eq(row['year'])], row['arm'])
                    actual = pd.Series(delta[group.index], index=group.date).groupby(level=0).mean().mean()
                    assert abs(row['net_gain_vs_h20']['delta']-actual) < 1e-12
                rows.append(dict(profile=name, scope=scope, horizon=h, rows=len(f), keys_and_membership_sha256=ref_hash,
                    identical_cohort_and_flags=True, same_independent_control_counts=True,
                    known_early_exits_identical=True, horizon_expiry_and_costs_pass=True,
                    raw_price_reserve_losses_below75pct=int(f.path_return.lt(-.75).sum())))
    audit_result = dict(status='PASS_EXPLORATORY_ONLY', report_sha256=digest(root/'report.json'),
        protocol_sha256=digest(root/'protocol.json'), audit_code_sha256=digest(Path(__file__)), cases=rows,
        raw_h20_formula_parity_rows=manifest['h20_formula_parity_rows'], same_entries_and_frozen_gates=True,
        fixed20_nonoverlapping_keys=True, no_retraining=True, sql=False, api_calls=0, orders=False,
        reserve='Horizon comparison, not newly trained directional prediction or certified portfolio PnL; price/OST reserves remain')
    atomic_json(root/'final-audit.json', audit_result)
    return audit_result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(audit(parser.parse_args().output))
