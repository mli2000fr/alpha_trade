import pytest
from scripts.research.us_self_tender_review import proof,check_proof,fee_gate,GROUPS


def test_explicit_decisions_unique_and_include_foreign_reserved():
    ids=[a for values in GROUPS.values() for a in values]
    assert len(ids)==len(set(ids))==51
    assert GROUPS['RESERVED_FIXED_LOCAL_SHARES_ADS_AND_RECORD_DATE']==['0001193125-25-286157']


def test_exact_clause_requires_unique_original_part():
    parts=[{'filename':'offer.htm','text':'We offer  shares at a price not greater than $20 nor less than $18 per Share.'}]
    clause=proof(parts,[r'not greater than.{0,50}per Share'])
    check_proof(parts,clause)
    with pytest.raises(ValueError):
        check_proof(parts,dict(filename='other.htm',contains=clause['contains']))
    with pytest.raises(ValueError):
        proof(parts,[r'fixed cash price of 22'])


def test_current_fee_is_burden_not_profitable_tender_assumption():
    gate=fee_gate(4000,100)
    assert gate['fee_to_notional']==.025
    assert gate['cash_needed_before_other_fees']==4100
    assert gate['not_a_pnl'] is True
    with pytest.raises(ValueError):
        fee_gate(0,100)
