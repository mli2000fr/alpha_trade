import pytest
from scripts.research.us_cash_merger_tapes import reconcile_action,executable_tape


def event():return dict(symbol='X',target_cik='1',cash_per_share_usd=10.,completed_on='2024-03-04',initial_filed='2024-02-28')


def test_two_rows_one_cash_right_not_double_payment_or_legal_date_shift():
    rows=[dict(acquiree_symbol='X',acquiree_cusip='123456789',rate=10.,effective_date='2024-03-04'),
          dict(acquiree_symbol='X',acquiree_cusip='123456789',rate=10.,effective_date='2024-03-06',payable_date='2024-03-06')]
    r=reconcile_action(rows,event(),'CUSIP 123456 789')
    assert r['economic_event_count']==1 and r['provider_record_count']==2
    assert r['sec_legal_closing']=='2024-03-04' and r['provider_payable_date']=='2024-03-06'
    assert r['broker_spendable_date'] is None and not r['broker_credit_qualified']


def test_missing_or_conflicting_pay_date_no_imputation():
    row=dict(acquiree_symbol='X',acquiree_cusip='123456789',rate=10.)
    assert reconcile_action([row],event(),'123456789')['provider_payable_date'] is None
    with pytest.raises(ValueError,match='Conflicting'):
        reconcile_action([dict(row,payable_date='2024-03-05'),dict(row,payable_date='2024-03-06')],event(),'123456789')


def test_identity_and_cash_contract_cannot_be_silently_changed():
    row=dict(acquiree_symbol='X',acquiree_cusip='123456789',rate=10.)
    with pytest.raises(ValueError,match='CUSIP'):reconcile_action([row],event(),'987654321')
    with pytest.raises(ValueError,match='amount'):reconcile_action([dict(row,rate=20.)],event(),'123456789')


def test_weekend_last_session_and_closing_mark_never_executable():
    def bar(t,v=1,n=1):return dict(t=t+'T05:00:00Z',o=10.,h=10.,l=10.,c=10.,v=v,n=n)
    rows=[bar('2024-02-29'),bar('2024-03-01'),bar('2024-03-04',0,0)]
    tape,excluded=executable_tape(rows,event())
    assert len(tape)==2 and len(excluded)==1
    assert excluded[0]['date']=='2024-03-04'
    with pytest.raises(ValueError,match='Missing'):executable_tape(rows[1:],event())
    with pytest.raises(ValueError,match='post-closing'):executable_tape(rows[:2]+[bar('2024-03-04')],event())
