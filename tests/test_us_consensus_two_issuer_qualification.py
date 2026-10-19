import pytest
from scripts.research.us_consensus_two_issuer_qualification import qualify,REQUIRED


def complete(): return {k:True for k in REQUIRED}


def test_exact_field_evidence_before_cutoff_can_pass_not_global_defaults():
    r=qualify(complete(),True,'calendar/trends:earningsEstimateAvg','2026-10-18T20:00Z','2026-10-19T13:30Z')
    assert r['semantically_complete'] and r['admissible_at_frozen_entry']


@pytest.mark.parametrize('field',REQUIRED)
def test_one_missing_component_never_qualifies(field):
    c=complete();c[field]=False
    r=qualify(c,True,'calendar/trends:earningsEstimateAvg','2026-10-18T20:00Z','2026-10-19T13:30Z')
    assert not r['semantically_complete'] and not r['admissible_at_frozen_entry']


@pytest.mark.parametrize('wrong',['epsActual','Fundamentals/Earnings/History','ISSUER_NON_GAAP_GUIDANCE_NOT_VENDOR_CONSENSUS_FIELD'])
def test_actual_eps_or_company_guidance_is_not_consensus_field_definition(wrong):
    r=qualify(complete(),True,wrong,'2026-10-18T20:00Z','2026-10-19T13:30Z')
    assert not r['semantically_complete'] and 'EPS_EVIDENCE_WRONG_FIELD_OR_PRODUCT' in r['reasons']


def test_future_review_cannot_change_what_was_qualified_at_entry():
    r=qualify(complete(),True,'calendar/trends:earningsEstimateAvg','2026-10-19T22:00Z','2026-10-19T13:30Z')
    assert r['semantically_complete'] and not r['admissible_at_frozen_entry']
    assert 'REVIEW_AFTER_FROZEN_ENTRY_CUTOFF' in r['reasons']


def test_missing_raw_receipt_blocks_even_plausible_numbers():
    r=qualify(complete(),False,'calendar/trends:earningsEstimateAvg','2026-10-18T20:00Z','2026-10-19T13:30Z')
    assert not r['semantically_complete']


def test_truthy_strings_not_accepted_as_verified_components():
    r=qualify({k:'true' for k in REQUIRED},True,'calendar/trends:earningsEstimateAvg','2026-10-18T20:00Z','2026-10-19T13:30Z')
    assert not r['semantically_complete']
