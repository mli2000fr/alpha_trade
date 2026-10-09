from datetime import date
import zipfile

import pytest

from service.fr.technical_counter_review_16g import publication_check, scan
from service.fr.release_review_16g3 import validate_review


def test_sax_reader_extracts_exact_pair_and_nominal_currency(tmp_path):
    path = tmp_path / 'full.zip'
    xml = '''<d:Document xmlns:d="urn:test"><d:RefData>
      <d:FinInstrmGnlAttrbts><d:Id>FR123</d:Id><d:FullNm> A &amp; B </d:FullNm>
      <d:NtnlCcy>EUR</d:NtnlCcy><d:ClssfctnTp>ESXXXX</d:ClssfctnTp></d:FinInstrmGnlAttrbts>
      <d:TradgVnRltdAttrbts><d:Id>XPAR</d:Id></d:TradgVnRltdAttrbts>
      <d:TechAttrbts><d:PblctnPrd><d:FrDt>2026-09-26</d:FrDt></d:PblctnPrd></d:TechAttrbts>
      </d:RefData><d:RefData><d:FinInstrmGnlAttrbts><d:Id>OTHER</d:Id></d:FinInstrmGnlAttrbts>
      <d:TradgVnRltdAttrbts><d:Id>XPAR</d:Id></d:TradgVnRltdAttrbts></d:RefData></d:Document>'''
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('full.xml', xml)
    count, rows = scan(path, {('FR123', 'XPAR')})
    assert count == 2 and len(rows) == 1
    assert rows[0]['name'] == 'A & B'
    assert rows[0]['currency'] == 'EUR'
    assert rows[0]['publication_from_reported'] == '2026-09-26'
    assert 'trading_currency' not in rows[0]
    assert scan(path, {('FR123', 'ALXP')})[1] == []


def test_sax_reader_detects_target_delta(tmp_path):
    path = tmp_path / 'delta.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('delta.xml', '''<Document><FinInstrm><ModfdRcrd>
        <FinInstrmGnlAttrbts><Id>FR123</Id></FinInstrmGnlAttrbts>
        <TradgVnRltdAttrbts><Id>XPAR</Id></TradgVnRltdAttrbts>
        </ModfdRcrd></FinInstrm></Document>''')
    assert scan(path, {('FR123', 'XPAR')})[1][0]['event'] == 'ModfdRcrd'


def fragments():
    return [{'path': f'artifacts/fr/{kind}_202609{day}_{n}of{total}.zip',
             'type': kind, 'date': f'2026-09-{day}'}
            for kind, day, n, total in [('FULINS_E', '26', 1, 2), ('FULINS_E', '26', 2, 2),
                                       ('DLTINS', '27', 1, 1), ('DLTINS', '28', 1, 1)]]


def test_complete_publication_numbering():
    publication_check(fragments(), date(2026, 9, 26), date(2026, 9, 28))


@pytest.mark.parametrize('mutation', ['missing_day', 'missing_fragment', 'duplicate', 'wrong_date'])
def test_incomplete_publication_rejected(mutation):
    files = fragments()
    if mutation == 'missing_day': files.pop()
    if mutation == 'missing_fragment': files.pop(0)
    if mutation == 'duplicate': files.append(files[0])
    if mutation == 'wrong_date': files[0]['date'] = '2026-09-25'
    with pytest.raises(ValueError):
        publication_check(files, date(2026, 9, 26), date(2026, 9, 28))


def test_assistant_counter_review_is_not_human_attestation():
    review = {'market_code': 'FR_EQ', 'packet_sha256': 'hash', 'serving_allowed': False,
              'orders_allowed': False, 'review_kind': 'SAME_ASSISTANT_TECHNICAL_COUNTER_REVIEW',
              'reviewer': 'Codex same assistant', 'independence_declared': False}
    with pytest.raises(ValueError, match='independent reviewer'):
        validate_review(review, 'hash')
