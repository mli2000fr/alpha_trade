from scripts.research.us_index_deletion_feasibility import allowed, nearby


def test_only_sec_no_provider_or_list_mirror():
    assert allowed('https://efts.sec.gov/LATEST/search-index?q=Russell&from=0')
    assert allowed('https://www.sec.gov/Archives/edgar/data/123/000000012326000001/issuer10k.htm')
    assert not allowed('https://www.lseg.com/content/dam/list.pdf')
    assert not allowed('https://content.ftserussell.com/list.pdf')
    assert not allowed('https://www.sec.gov.evil.test/Archives/edgar/data/123/000000012326000001/issuer10k.htm')
    assert not allowed('https://efts.sec.gov/LATEST/search-index?q=Russell&redirect=evil')
    assert not allowed('http://efts.sec.gov/LATEST/search-index?q=Russell')


def test_discovery_retains_conditional_risk_but_does_not_admit_it():
    text='If our stock is removed from the Russell 3000, investors may sell.'
    assert nearby(text)==[text]
    assert nearby('Russell is our director. There is no index event here.')==[]
