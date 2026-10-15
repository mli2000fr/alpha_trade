"""Offline technical continuation; preserve the frozen script and paid answers.

The original evaluator eagerly required macro even for a potentially cash-only
tail. Defer that requirement to the EXISTING native chronological guard: it still
fails on missing macro while holding a position, but needs none for cash alone.
No macro value is filled or regime guard disabled. Never make an API call here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import logging
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts.research import us_news_gpt_september_pilot as study
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def archived_macro_only(root, frame, required_days):
    # Missing days remain missing. Native run_portfolio explicitly rejects them
    # unless no position and no remaining entry decision make them irrelevant.
    return frame.copy()


def run(root):
    root=Path(root)
    study.sealed(root,'prepare');analysis=study.sealed(root,'analysis')
    p=study.read(root/'protocol.json');verify_hashes(Path('.'),p['sources'])
    if (root/'technical-evaluation-amendment.json').exists():
        amendment=study.read(root/'technical-evaluation-amendment.json')
        verify_hashes(Path('.'),amendment['sources'])
    else:
        amendment=dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
            after_gpt_answers_before_any_economic_result=True,
            earlier_failure=study.read(root/'progress.json'),
            change='Defer missing-macro necessity to original native cash-only expiry-tail guard',
            no_macro_interpolation=True,no_risk_guard_disabled=True,no_rule_or_date_change=True,
            no_new_api_calls=True,selection_unchanged=True,
            sources={str(Path(__file__)):digest(__file__),
                'tests/test_us_news_gpt_september_pilot_review.py':digest('tests/test_us_news_gpt_september_pilot_review.py')},
            frozen_analysis_sha256=digest(root/'analysis.json'))
        atomic_json(root/'technical-evaluation-amendment.json',amendment)
    if amendment['frozen_analysis_sha256']!=digest(root/'analysis.json'):
        raise ValueError('Paid answers changed during technical continuation')
    try:
        with patch.object(study,'complete_macro_tail',archived_macro_only):
            report=study.evaluate(root)
        report.update(technical_continuation='NATIVE_EXISTING_CASH_ONLY_MACRO_GUARD',
            risk_guard_disabled=False,macro_interpolated=False)
    except Exception as exc:
        if 'Missing macro date ' not in str(exc):
            raise
        # Individual outcome diagnostics can be complete while full portfolio
        # accounting cannot be certified. Never promote a partial PnL as final.
        report=dict(status='COMPLETED_LLM_DIAGNOSTIC_PORTFOLIO_BLOCKED',analysis=analysis,
            portfolio_error=str(exc),verdict='NO_FILTER_ACTION_ON_THIS_SAMPLE' if not analysis['vetoed']
            else 'PORTFOLIO_UNQUALIFIED',portfolio_pnl_complete=False,
            identical_candidate_sets=not bool(analysis['vetoed']),
            no_directional_prediction_proven=True,independent_holdout=False,
            files={n:digest(root/n) for n in ['protocol.json','prepare.json','analysis.json',
                'unit-outcomes.json','assessments.json','usage.json','technical-evaluation-amendment.json']})
    outcomes=study.read(root/'unit-outcomes.json')
    valid=[r for r in outcomes if r['reason']=='QUALIFIED_EXPLORATORY_VENDOR_PATH']
    positive=[r for r in valid if r['gpt']=='BULLISH']
    report['unit_diagnostic']=dict(rows=len(outcomes),qualified=len(valid),excluded=len(outcomes)-len(valid),
        exclusions=dict(Counter(r['reason'] for r in outcomes if r['reason']!='QUALIFIED_EXPLORATORY_VENDOR_PATH')),
        tp_before_sl=sum(r['tp_before_sl'] for r in valid),
        positive_gross_paths=sum(r['gross_return_pct']>0 for r in valid),
        bullish_cases=positive,unit_gross_not_portfolio_pnl=True)
    report.setdefault('files',{})['technical-evaluation-amendment.json']=digest(root/'technical-evaluation-amendment.json')
    atomic_json(root/'report.json',report)
    atomic_json(root/'progress.json',dict(status=report['status'],verdict=report['verdict'],
        new_api_calls=0,unit_diagnostic_complete=True))
    return report


def main():
    from scripts.research.oracle_path_confirmation import exclusive_run
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    with exclusive_run(args.output):
        result=run(args.output)
    print(study.json.dumps(result,default=str))


if __name__=='__main__':
    main()
