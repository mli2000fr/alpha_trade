from service.fr.usable_subset_qualification import classify


def sample(**overrides):
    args = dict(identity={'provider_symbol': 'X.PA', 'isin': 'FR0000000000',
                          'research_uid': 'research-only'},
        diagnostic={'features_computed': True, 'missing_sessions': [],
                    'reasons': ['MASTER_CONTINUITY_UNQUALIFIED']},
        resolution={'mic': 'XPAR', 'reasons': []}, missing=[], retained=[],
        nonpositive=[], sql_missing=[], archive_errors=False)
    args.update(overrides)
    return classify(**args)


def test_complete_provider_inputs_are_never_shadow_admission():
    row = sample()
    assert row['price_only_recent_panel_usable']
    assert row['observed_provider_feature_inputs_usable']
    assert not row['shadow_eligible'] and not row['orders_allowed']
    assert 'MASTER_CONTINUITY_UNQUALIFIED' in row['input_reserves']


def test_retained_old_price_is_not_complete_research_panel():
    row = sample(retained=['2026-10-05'])
    assert not row['price_only_recent_panel_usable']
    assert not row['observed_provider_feature_inputs_usable']


def test_zero_volume_and_missing_sql_block_price_panel():
    for overrides in ({'nonpositive': ['2026-10-05']},
                      {'sql_missing': ['2026-10-05']}, {'missing': ['2026-10-05']},
                      {'archive_errors': True}):
        assert not sample(**overrides)['price_only_recent_panel_usable']


def test_computable_features_do_not_override_identity_or_actions():
    for reason in ('DAILY_IDENTITY_VERSION_AMBIGUOUS',
                   'UNQUALIFIED_DIV_IN_FEATURE_WINDOW',
                   'INCOMPLETE_SPLITS_OBSERVED_COVERAGE',
                   'MASTER_STALE_OR_WRONG_SESSION'):
        row = sample(diagnostic={'features_computed': True, 'missing_sessions': [],
                                 'reasons': [reason]})
        assert row['price_only_recent_panel_usable']
        assert not row['observed_provider_feature_inputs_usable']


def test_incomplete_warmup_cannot_qualify_features():
    row = sample(diagnostic={'features_computed': False,
        'missing_sessions': ['2026-09-10'], 'reasons': ['INCOMPLETE_21_SESSION_WARMUP']})
    assert not row['observed_provider_feature_inputs_usable']
