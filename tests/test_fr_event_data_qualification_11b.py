import pytest

from service.fr.event_data_qualification_11b import inventory, parse_positions, public_day, recent_count

HEADER = 'Detenteur de la position courte nette;Ratio;code ISIN;Date de debut position;Date de debut de publication position;Date de fin de publication position\n'


def test_position_date_is_not_publication_and_no_zero_inference():
    rows, rejected = parse_positions((HEADER + 'Fund;0.45;FR0000054470;2024-01-02;2024-01-04;\n').encode())
    assert not rejected
    assert rows[0]['publication_date'] == '2024-01-04'
    result = inventory(rows, {'FR0000054470', 'FR0000000000'})
    assert result['matched_isins'] == 1
    assert result['absence_state'] == 'NOT_OBSERVED_NOT_ZERO'


@pytest.mark.parametrize('ratio,position,publication,end', [
    ('nan','2024-01-02','2024-01-04',''),
    ('0.5','2024-01-05','2024-01-04',''),
    ('0.5','2024-01-02','2024-01-04','2024-01-03'),
])
def test_bad_rows_not_promoted(ratio, position, publication, end):
    rows, rejected = parse_positions((HEADER + f'Fund;{ratio};FR0000054470;{position};{publication};{end}\n').encode())
    assert not rows and len(rejected) == 1


def test_schema_drift_fails():
    with pytest.raises(ValueError, match='schema'):
        parse_positions(b'isin;ratio\n')


def test_same_day_updates_ambiguous_and_2026_excluded():
    rows, _ = parse_positions((HEADER +
        'Fund;0.5;FR0000054470;2024-01-02;2024-01-04;\n' +
        'Fund;0.6;FR0000054470;2024-01-03;2024-01-04;\n' +
        'Fund;0.9;FR0000054470;2026-01-02;2026-01-04;\n').encode())
    report = inventory(rows, {'FR0000054470'})
    assert report['matched_rows'] == 2
    assert report['same_publication_day_ambiguous_groups'] == 1


def test_same_day_excluded_and_calendar_window_boundary():
    assert recent_count(['2024-01-01', '2024-01-02', '2024-01-08', '2024-01-09'], '2024-01-09') == 2


def test_latest_explicit_timestamp_and_paris_day():
    assert public_day({'uin_dat_amf': '2024-01-02T23:30:00Z',
                       'uin_dat_mar': '2024-01-03T22:30:00Z'}) == '2024-01-03'
    assert public_day({'uin_dat_amf': '2024-01-02T12:00:00'}) is None
