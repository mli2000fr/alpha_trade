"""Exclude archival support/missingness from economic warning selection."""
from pathlib import Path
from unittest.mock import patch

from scripts.research import us_q051_protection_adaptive_audit_20261118 as adaptive
from scripts.research import us_q051_protection_feature_audit_20261118 as base
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=base.ROOT/'adaptive-qualified-v2'


def diagnostic_only(name):
    return any(marker in name for marker in ('coverage','last_closed_count','__count','_known','_expected'))


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    atomic_json(ROOT/'qualification-protocol.json',dict(script_sha256=digest(Path(__file__)),
        purpose='Availability/archival gaps are diagnostics, not economic warning evidence',
        excluded=['coverage','last_closed_count','cohort counts','known/expected outcome counts'],
        previous_studies_already_observed=True,threshold_changes=False,production_changes=False))
    original=base.screen
    def qualified(features,outcome):
        table=original(features,outcome)
        table['diagnostic_only']=table.feature.map(diagnostic_only)
        table['eligible']=table.eligible&~table.diagnostic_only
        return table
    with patch.object(adaptive,'ROOT',ROOT),patch.object(base,'screen',qualified):adaptive.main()


if __name__=='__main__':main()
