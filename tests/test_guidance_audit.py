from service.forward_pit.guidance_audit import guidance_candidates
from service.forward_pit.guidance_audit import money_range_candidates


def test_numeric_guidance_is_only_unconfirmed_candidate():
    result=guidance_candidates('<p>The company raises its 2026 revenue guidance to $500 million.</p>')
    assert len(result)==1
    assert result[0]['status']=='UNCONFIRMED_MANUAL_REVIEW'
    assert result[0]['year_cues']==['2026']


def test_boilerplate_without_metric_and_number_is_not_candidate():
    assert guidance_candidates('<p>Our outlook is subject to risks.</p>')==[]


def test_scripts_and_styles_do_not_supply_numeric_labels():
    assert guidance_candidates('<script>Revenue guidance 2026 $500 million</script><p>Our outlook.</p>')==[]


def test_historical_numbers_can_be_false_positive_never_confirmed():
    result=guidance_candidates('<p>Revenue was $100 million in 2025. Our outlook is uncertain.</p>')
    assert result and all(r['status']=='UNCONFIRMED_MANUAL_REVIEW' for r in result)


def test_money_ranges_keep_explicit_units_but_do_not_invent_table_units():
    rows=money_range_candidates('<p>Sales $1.49 billion to $1.53 billion; EPS between $4.60 and $5.00.</p>')
    assert [(r['low'],r['high'],r['explicit_unit']) for r in rows]==[(1.49,1.53,'billion'),(4.6,5.,None)]
    assert money_range_candidates('<p>Total revenue $3,129 to $3,141.</p>')[0]['low']==3129
    assert money_range_candidates('<p>Total revenue $3,129 to $3,141.</p>')[0]['explicit_unit'] is None
