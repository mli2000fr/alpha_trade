"""Versioned, run-local repair: preserve monthly runtime's requested campaign scope."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import logging
import os

import pandas as pd

from scripts.research import us_winner_monthly_selector_20261024 as study
from execution_engine.models import ExecutionTarget
from common.winner_pyramiding import aware

AMENDMENT = 'scope-repair-20261024-v1'
DOC = Path('doc/ml/winner_monthly_scope_repair_20261024.md')
TEST = Path('tests/test_us_winner_monthly_scope_repair_20261024.py')


@contextmanager
def campaign_adapter(config, selector):
    """Same policies as sealed predecessor; never expand a runtime subset."""
    native, capacity = study.native, study.capacity
    old_stage, old_runtime = native.stage_targets, native.WinnerCampaignRuntime
    metadata = {}

    def name_at(now):
        return selector(pd.Timestamp(now).tz_convert('America/New_York').date())

    def register(store, name, originals):
        for row in store.rows(active_only=False):
            state = row['state']
            if state['campaign_id'] not in metadata:
                metadata[state['campaign_id']] = dict(profile=name, signal_date=state['signal_date'],
                    policy=deepcopy(state['policy']), entry_expires_at=state['entry_expires_at'],
                    admission_target=asdict(originals[(state['target']['risk_run_id'], state['symbol'])]))

    def stage(store, targets, cfg, exec_run_id, *, now=None, calendar=None):
        name = name_at(now); policy = study.profile_policy(cfg, name)
        originals = {(t.risk_run_id, t.symbol): t for t in targets}
        resized = [study.resize_target(t, cfg, policy) for t in targets]
        resized = [t for t in resized if t.target_shares >= 1]
        result = old_stage(store, resized, replace(cfg, winner_pyramiding=policy), exec_run_id, now=now, calendar=calendar)
        register(store, name, originals)
        return result

    class MonthlyRuntime(old_runtime):
        def run(self, records):
            name = name_at(self.now)
            requested = []
            for record in records:
                current = self.store.get(record['state']['campaign_id'])
                state = current['state']
                if not study.unfilled_rearm_allowed(state, self.now) or metadata[state['campaign_id']]['profile'] == name:
                    requested.append(current)
                    continue
                original_expiry = state['entry_expires_at']
                state['status'] = 'CANCELED'; self.store.save(state, current['version'])
                target = ExecutionTarget(**metadata[state['campaign_id']]['admission_target'])
                origin = target.risk_run_id.split('|monthly:')[0]
                target = replace(target, risk_run_id=origin+'|monthly:'+self.now.strftime('%Y-%m')+'|'+name)
                stage(self.store, [target], self.config, state['exec_run_id'], now=self.now,
                      calendar=capacity.grid.whole.CachedCalendar(capacity.grid.calendar()))
                replacements = [r for r in self.store.rows() if r['state']['symbol'] == state['symbol']]
                if len(replacements) > 1:
                    raise ValueError('Ambiguous monthly replacement')
                if replacements:
                    if replacements[0]['state']['entry_expires_at'] != original_expiry:
                        raise ValueError('Monthly rearm must not extend original signal expiry')
                    requested.append(replacements[0])
            # Pre-open receives due campaigns ONLY and intentionally no bars.
            # Include only requested identities, or their own pending replacement.
            return super().run(requested)

        def book_buy(self, intent, operation, raw):
            super().book_buy(intent, operation, raw)
            if self.state['lots']:
                item = metadata[self.state['campaign_id']]
                item.update(first_fill_at=self.state['first_fill_at'], symbol=self.state['symbol'], due_open=self.state['due_open'])
                if item['profile'] != name_at(aware(self.state['first_fill_at'])):
                    raise ValueError('Actual entry policy differs from monthly selection')

    native.stage_targets, native.WinnerCampaignRuntime = stage, MonthlyRuntime
    try:
        yield metadata
    finally:
        native.stage_targets, native.WinnerCampaignRuntime = old_stage, old_runtime


def prepare_amendment():
    root, base = study.ROOT, study.capacity.grid.base
    folder = root/AMENDMENT
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/'amendment.json'
    if path.exists():
        receipt = study.capacity.read_json(path)
        base.verify(receipt['sources'])
        return path, receipt
    failure = study.capacity.read_json(root/'progress.json')
    if failure.get('status') != 'FAILED' or 'Pre-open exit reconciliation failed' not in failure.get('error', ''):
        raise ValueError('Expected original pre-open failure before repair')
    if (root/'report.json').exists():
        raise ValueError('Do not amend a completed experiment')
    protocol = study.prepare()
    manifest = study.capacity.read_json(root/'inputs/manifest.json')
    base.verify({str(root/'inputs'/n): h for n, h in manifest['files'].items()})
    base.save_new(folder/'original-failure.json', failure)
    sources = dict(protocol['sources'])
    for p in [Path(__file__), DOC, TEST, root/'protocol.json', root/'inputs/manifest.json',
              folder/'original-failure.json', Path('log/winner-monthly-selector-20261024-v1.stdout.log'),
              Path('log/winner-monthly-selector-20261024-v1.stderr.log')]:
        sources[str(p)] = base.digest(p)
    preserved = {str(p): base.digest(p) for p in (root/'cases').glob('*/report.json')}
    sources.update(preserved)
    receipt = dict(amendment=AMENDMENT, created_at_utc=datetime.now(timezone.utc).isoformat(),
        correction='Preserve requested runtime subset, replacing only its own untouched pending plans',
        original_failure=failure, sources=sources, completed_cases_preserved=preserved,
        snapshot_count=len(manifest['receipts']), profiles_changed=False, risk_changed=False,
        fees_changed=False, inputs_changed=False, SQL_reads=0, SQL_writes=0, provider_calls=0,
        original_sources_modified=False)
    base.save_new(path, receipt)
    return path, receipt


def run():
    path, receipt = prepare_amendment()
    base = study.capacity.grid.base
    saved_adapter, saved_run_case = study.campaign_adapter, study.run_case
    saved_prepare = study.inputs.prepare
    amendment_sha = base.digest(path)

    def archived_inputs(root):
        manifest = study.capacity.read_json(root/'inputs/manifest.json')
        base.verify({str(root/'inputs'/n): h for n, h in manifest['files'].items()})
        return manifest  # Never open a SQL connection or redownload on resume.

    def run_case(*args, **kwargs):
        base.verify(receipt['sources'])
        result = saved_run_case(*args, **kwargs)
        case_path = study.ROOT/'cases'/args[1]/'report.json'
        marker = path.parent/(args[1]+'-receipt.json')
        if not marker.exists():
            base.save_new(marker, dict(amendment_sha256=amendment_sha,
                report_sha256=base.digest(case_path), original_sources_modified=False))
        return result

    study.campaign_adapter, study.run_case, study.inputs.prepare = campaign_adapter, run_case, archived_inputs
    try:
        study.run()
        base.verify(receipt['sources'])
        resolution = path.parent/'resolution.json'
        if not resolution.exists():
            base.save_new(resolution, dict(status='RESOLVED', amendment_sha256=amendment_sha,
                report_sha256=base.digest(study.ROOT/'report.json'), completed_runs=10))
    finally:
        study.campaign_adapter, study.run_case, study.inputs.prepare = saved_adapter, saved_run_case, saved_prepare


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare', 'resume'], default='resume')
    args = parser.parse_args()
    os.environ['SSLKEYLOGFILE'] = ''
    if os.name == 'nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR, force=True)
    prepare_amendment() if args.phase == 'prepare' else run()
