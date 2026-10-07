import io
import zipfile

from service.fr.bnains_price_reference_pilot import read_archive


def test_nested_archive_filters_isins_and_reads_ohlcv(tmp_path):
    month_buffer = io.BytesIO()
    with zipfile.ZipFile(month_buffer, "w") as month:
        month.writestr("20160104.txt", "FR0000000001\tTEST\t1.0\t1.2\t0.9\t1.1\t123\r\n"
                       "FR0000000002\tOTHER\t2\t2\t2\t2\t5\r\n")
    archive = tmp_path / "2016.ZIP"
    with zipfile.ZipFile(archive, "w") as year:
        year.writestr("201601.ZIP", month_buffer.getvalue())

    rows = list(read_archive(archive, {"FR0000000001"}))
    assert rows == [("2016-01-04", "FR0000000001", "TEST", (1.0, 1.2, 0.9, 1.1), 123.0)]
