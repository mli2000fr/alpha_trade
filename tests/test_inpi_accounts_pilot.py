from decimal import Decimal
import json

import pytest

from service.inpi.accounts_pilot import accounting_checks, collect_pages, number, run
from service.inpi.client import InpiClient, InpiError
from service.inpi.pilot_review import review


def document(kind='C'):
    codes = [('CO','m3','100'), ('EE','m1','100'), ('DL','m1','40'),
             ('CF','m3','10'), ('FJ','m3','50'), ('DI' if kind=='C' else 'P2','m1','5')]
    return {'siren':'438479941','confidentiality':'Public','deleted':False,
            'typeBilan':kind,'dateCloture':'2024-12-31',
            'bilanSaisi':{'bilan':{'identite':{
                'siren':'438479941','codeTypeBilan':kind,'codeSaisie':'00',
                'codeConfidentialite':'0','codeDevise':'EUR','dureeExerciceN':'12',
                'dateClotureExercice':'2024-12-31'},'detail':{'pages':[{
                    'liasses':[{'code':code,col:value} for code,col,value in codes]}]}}}}


@pytest.mark.parametrize('kind',['C','K'])
def test_documented_columns_and_balance(kind):
    payload=document(kind)
    payload['bilanSaisi']['bilan']['detail']['pages'][0]['liasses'][0]['m1']='999'
    result=accounting_checks(payload,'438479941')
    assert result['amounts_source_units']['assets_net']=='100'
    assert result['amounts_source_units']['income']=='5'
    assert result['balance_identity']=='PASS'
    assert result['normalization_status']=='TECHNICAL_CHECKS_PASS_REVIEW_PENDING'
    assert result['external_reconciliation']=='PENDING_ISSUER_REPORT_COMPARISON'


def test_missing_is_not_zero_and_source_incoherence_blocks_review():
    payload=document()
    payload['bilanSaisi']['bilan']['identite']['codeSaisie']='01'
    payload['bilanSaisi']['bilan']['detail']['pages'][0]['liasses'][3]['m3']=''
    result=accounting_checks(payload,'438479941')
    assert result['amounts_source_units']['cash'] is None
    assert {'SOURCE_ENTRY_CODE_NOT_00','MISSING_CORE_FIELDS'} <= set(result['issues'])
    assert result['normalization_status']=='REVIEW_REQUIRED'


def test_balance_mismatch_and_duplicate_codes_are_not_promoted():
    payload=document()
    payload['bilanSaisi']['bilan']['detail']['pages'][0]['liasses'].append({'code':'EE','m1':'1000'})
    result=accounting_checks(payload,'438479941')
    assert result['balance_identity']=='FAIL'
    assert 'DUPLICATE_CODES' in result['issues']


@pytest.mark.parametrize('value',['NaN','Infinity','1,000','1e3','private'])
def test_reject_ambiguous_amount(value):
    with pytest.raises(InpiError): number(value)


def test_number_missing_and_signed_decimal():
    assert number(None) is None and number('') is None
    assert number('-12.50')==Decimal('-12.50')
    assert number('0')==0


@pytest.mark.parametrize('rows,cursor',[([], 'next'),([{'id':'a'}],'same')])
def test_pagination_empty_cursor_or_loop_is_rejected(rows,cursor,monkeypatch):
    monkeypatch.setattr('service.inpi.accounts_pilot.time.sleep',lambda _:None)
    class Fake:
        def accounts(self,*args,**kwargs): return rows,cursor
    with pytest.raises(InpiError): collect_pages(Fake(),'438479941','bilans')


def test_bounded_pagination_is_not_exhaustive(monkeypatch):
    monkeypatch.setattr('service.inpi.accounts_pilot.time.sleep',lambda _:None)
    class Fake:
        count=0
        def accounts(self,*args,**kwargs):
            self.count+=1
            return [{'id':str(self.count)}],str(self.count)
    rows,coverage=collect_pages(Fake(),'438479941','bilans',max_pages=2)
    assert len(rows)==2 and coverage['complete'] is False


def test_client_cursor_and_siren_scope():
    client=InpiClient(); paths=[]
    def request(path):
        paths.append(path)
        return [{'siren':'438479941'}],None
    client._request=request
    client.accounts('438479941',search_after='abc123')
    assert 'searchAfter=abc123' in paths[0]
    with pytest.raises(InpiError): client.accounts('438479941',search_after='../x')
    client._request=lambda _:([{'siren':'000000000'}],None)
    with pytest.raises(InpiError): client.accounts('438479941')


def test_unexpected_failure_is_persisted_sanitized_and_client_closed(tmp_path,monkeypatch):
    monkeypatch.setattr('service.inpi.accounts_pilot.validate_manifest',lambda _: 'hash')
    class Fake:
        calls=1; closed=False
        def login(self): raise RuntimeError('secret-payload')
        def close(self): self.closed=True
    client=Fake(); result=run(client,{'issuers':[]},tmp_path/'pilot')
    assert result['status']=='FAILED' and client.closed
    saved=json.loads((tmp_path/'pilot/report.json').read_text(encoding='utf-8'))
    assert saved['sql_writes'] is False and saved['canonical_go'] is False
    assert 'secret-payload' not in str(saved)


def test_reconciliation_never_promotes_and_detects_versions():
    account={'id':'a','dateCloture':'2024-12-31','typeBilan':'K',
             'amounts_source_units':{'revenue':'100','cash':None},
             'balance_identity':'PASS','normalization_status':'REVIEW_REQUIRED'}
    alternate={**account,'id':'b','amounts_source_units':{'revenue':'101','cash':'5'}}
    report={'issuers':[{'symbol':'TEST','accounts':[account,alternate]}]}
    rule={'symbol':'TEST','id':'a','field':'revenue','expected_eur':'99','tolerance_eur':'1'}
    evidence={'checks':[rule,{**rule,'expected_eur':'90'}, {**rule,'field':'cash'}]}
    result=review(report,evidence)
    assert result['counts']=={'MATCH_WITHIN_TOLERANCE':1,'MISMATCH':1,'MISSING':1}
    assert result['duplicate_period_versions'][0]['different_amounts']
    assert not result['canonical_go'] and not result['historical_pit_qualified']
