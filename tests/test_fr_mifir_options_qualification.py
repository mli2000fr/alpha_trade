from service.fr import mifir_options_poc as source
from service.fr.mifir_options_qualification import audit
from test_fr_mifir_options_poc import trade, reference, OBSERVED


def snapshot(rows=None, doc=None):
    universe = {'FR0000120321': 'OR.PA', 'FR0000120644': 'BN.PA'}
    return {'analysis': source.analyze(rows or [trade()], [doc or reference()], OBSERVED, universe),
            'universe': universe, 'available_at': OBSERVED}


def test_integer_quantity_and_blank_measurement_do_not_certify_contracts():
    report = audit(snapshot())
    assert report['fractional_quantity_rows'] == 0
    assert report['unit_assessment']['quantity_unit_qualified'] is False
    assert report['unit_assessment']['put_call_contract_volume_ratio'] is None
    assert report['observed_activity_coverage'] == 0.5
    assert report['symbols_without_accepted_trade'] == ['BN.PA']
    assert report['ml_eligible'] is False


def test_adjusted_multiplier_flag_is_not_automatic_adjustment_validation():
    report = audit(snapshot(doc=reference(drv_price_multiplier='101')))
    assert report['non_standard_multiplier_series'] == ['FREX03807457']
    assert 'adjustment_history' in report['missing']


def test_duplicate_or_wrong_identity_blocks_technical_qualification():
    data = snapshot()
    data['analysis']['accepted'].append(data['analysis']['accepted'][0].copy())
    assert audit(data)['status'] == 'TECHNICAL_FAILURE'
    data = snapshot()
    data['universe']['FR0000120321'] = 'OTHER.PA'
    assert audit(data)['validation_errors'] == {'IDENTITY_JOIN': 1}
