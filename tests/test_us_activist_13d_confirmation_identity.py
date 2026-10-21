from scripts.research.us_activist_13d_confirmation_identity import plain_pbt_cover


def test_plain_cover_requires_exact_registered_class_and_official_annual_url():
    body=b'PERMIAN BASIN ROYALTY TRUST <table><tr><td>Units of Beneficial Interest</td><td>PBT</td><td>New York Stock Exchange</td></tr></table>'
    a={'accession':'0000950170-25-039308','filed':'2025-03-14'}
    receipt={'url':'https://www.sec.gov/Archives/edgar/data/319654/000095017025039308/pbt_10-k_2024-12-31.htm'}
    assert plain_pbt_cover(body,receipt,a)['symbol']=='PBT'
    assert plain_pbt_cover(body,{'url':'https://evil.test/pbt.htm'},a) is None
    assert plain_pbt_cover(body.replace(b'PBT',b'OTHER'),receipt,a) is None
