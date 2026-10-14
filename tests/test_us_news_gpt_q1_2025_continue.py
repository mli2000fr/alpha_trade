from decimal import Decimal
import pytest

from scripts.research import us_news_gpt_q1_2025_continue as study
from tests.test_us_news_gpt_q1_2025_run import packet,response


def test_cache_write_premium_included_and_read_discount_ignored():
    value=response();value['usage']={'input_tokens':1000,'output_tokens':100,
        'input_tokens_details':{'cache_write_tokens':600,'cached_tokens':200}}
    actual=study.usage_with_cache(value)
    assert actual['gross_cost_estimate_usd']==pytest.approx(.000165)
    assert actual['cache_write_tokens']==600


def test_inconsistent_cache_details_stop():
    value=response();value['usage']['input_tokens_details']={'cache_write_tokens':80,'cached_tokens':30}
    with pytest.raises(ValueError):study.usage_with_cache(value)


def test_invalid_quote_is_unknown_not_veto_or_abstain():
    import json
    value=response();parsed=json.loads(value['output'][0]['content'][0]['text'])
    parsed['evidence'][0]['quote']='Invented sentence, no source proof'
    value['output'][0]['content'][0]['text']=json.dumps(parsed)
    out=study.qualify_or_unknown(value,packet())
    assert out['decision']=='UNKNOWN_INVALID_RESPONSE'
    assert out['technical_status']=='INVALID_PRESERVED' and not out['veto_long']


def test_valid_bearish_unchanged():
    out=study.qualify_or_unknown(response(),packet())
    assert out['veto_long'] and out['technical_status']=='VALID'


def test_worst_call_assumes_every_input_token_cache_written():
    payload={'model':'gpt-6-luna','input':'abc'}
    assert study.worst_call_cost(payload)>Decimal('0.0009')
