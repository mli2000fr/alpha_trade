from scripts.operations.build_ordinary_shares_inventory_20261103 import classify


def test_preferred_bank_is_common_equity_not_preferred_stock():
    name='Preferred Bank - Common Stock'
    status,_=classify('PFBC',{'company_name':name},{'company_name':name},None,{'type':'Common Stock'})
    assert status=='INCLUDE_ORDINARY'


def test_explicit_preferred_share_description_stays_excluded():
    name='Example Bank Depositary Shares Representing Preferred Stock'
    status,_=classify('BANKP',{'company_name':name},{'company_name':name},None,{'type':'Common Stock'})
    assert status=='EXCLUDE_PREFERRED'
