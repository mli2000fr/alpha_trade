from service.fr.guidance_free_sources_11f import within_archive_boundary


def test_capture_after_event_is_not_historical_proof():
    data = {"archived_snapshots":{"closest":{"available":True,"timestamp":"20200101080000","status":"200"}}}
    assert not within_archive_boundary(data, "20191205")
    assert within_archive_boundary(data, "20200101")


def test_absent_failed_and_malformed_capture_not_admitted():
    assert not within_archive_boundary({}, "20200101")
    assert not within_archive_boundary({"archived_snapshots":{"closest":{"available":True,"timestamp":"garbage","status":"200"}}}, "20200101")
    assert not within_archive_boundary({"archived_snapshots":{"closest":{"available":True,"timestamp":"20190101080000","status":"404"}}}, "20200101")
