from service.fr.operational_closure_15g import observed_day, run_evidence


def row(day, **extra):
    return {'started_at': f'{day}T22:00:00+02:00', 'market_code': 'FR_EQ',
            'status': 'SUCCESS', 'failed_count': 0, 'warning_count': 0, **extra}


def test_five_distinct_sessions_required_not_five_reruns():
    days = ['2026-09-28','2026-09-29','2026-09-30','2026-10-01','2026-10-02']
    assert run_evidence([row(d) for d in days], days)['week_verified']
    assert not run_evidence([row(days[-1])]*5, days)['week_verified']


def test_smoke_dryrun_alerts_and_failures_do_not_qualify():
    day = '2026-10-02'
    for changes in ({'limited_smoke': True}, {'dry_run': True},
                    {'status': 'FAILED'}, {'failed_count': 1}, {'warning_count': 1},
                    {'market_code': 'US_EQ'}):
        assert run_evidence([row(day, **changes)], [day])['successful_sessions_without_alerts'] == []


def test_latest_failure_not_masked_by_prior_success_or_catchup_window():
    day = '2026-10-02'
    rows = [row(day, started_at=f'{day}T21:00:00+02:00'),
            row(day, status='FAILED', window=['2026-09-28',day])]
    result = run_evidence(rows, ['2026-09-28', day])
    assert result['latest_status'] == 'FAILED'
    assert not result['successful_sessions_without_alerts']


def test_timestamp_needs_timezone_and_uses_paris_day():
    assert observed_day({'started_at':'2026-10-01T23:30:00+00:00'}) == '2026-10-02'
    assert observed_day({'started_at':'2026-10-01T23:30:00'}) is None
    assert observed_day({}) is None
