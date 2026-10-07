import hashlib
import io
import json
import zipfile
from datetime import date

import pytest

from service.market.cn_margin_lending_pilot import (
    analyse_sse,
    analyse_szse,
    completed_raw_verified,
)


def test_sse_rejects_incomplete_pagination():
    raw = json.dumps({"result": [{"stockCode": "600519", "opDate": "20250630", "rzye": 1}],
                      "pageHelp": {"total": 2}}).encode()
    with pytest.raises(ValueError, match="pagination incomplète"):
        analyse_sse(raw, date(2025, 6, 30), {"600519"})


def test_sse_coverage_does_not_confuse_missing_with_zero():
    raw = json.dumps({"result": [{"stockCode": "600519", "opDate": "20250630",
                                  "rzye": 10, "rzmre": 0, "rzche": 1,
                                  "rqyl": 0, "rqmcl": 0, "rqchl": 0}],
                      "pageHelp": {"total": 1}}).encode()
    report = analyse_sse(raw, date(2025, 6, 30), {"600519", "600000"})
    assert report["active_matched"] == 1
    assert report["active_coverage_pct"] == 50
    assert report["sample_missing_active_codes"] == ["600000"]
    assert report["negative_values"] == 0


def test_szse_xlsx_analysis():
    output = io.BytesIO()
    columns = ["证券代码", "证券简称", "融资买入额(元)", "融资余额(元)",
               "融券卖出量(股/份)", "融券余量(股/份)", "融券余额(元)", "融资融券余额(元)"]
    def xml_row(number, values):
        cells = "".join(
            f"<c r='{chr(65 + index)}{number}' t='inlineStr'><is><t>{value}</t></is></c>"
            for index, value in enumerate(values)
        )
        return f"<row r='{number}'>{cells}</row>"
    sheet = ("<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>"
             "<sheetData>" + xml_row(1, columns)
             + xml_row(2, ["000001", "A", "100", "1000", "10", "20", "200", "1200"])
             + xml_row(3, ["000002", "B", "0", "0", "0", "0", "0", "0"])
             + "</sheetData></worksheet>")
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    report = analyse_szse(output.getvalue(), {"000001", "000003"})
    assert report["rows"] == 2
    assert report["active_matched"] == 1
    assert report["active_coverage_pct"] == 50
    assert report["sample_missing_active_codes"] == ["000003"]
    assert report["missing_numeric_cells"] == 0


def test_resume_requires_matching_raw_hashes(tmp_path):
    raw = b"raw"
    for name in ("sse.json", "szse.xlsx"):
        (tmp_path / name).write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    session = {
        "sse": {"raw_file": "sse.json", "sha256": digest},
        "szse": {"raw_file": "szse.xlsx", "sha256": digest},
    }
    assert completed_raw_verified(tmp_path, session)
    (tmp_path / "szse.xlsx").write_bytes(b"changed")
    assert not completed_raw_verified(tmp_path, session)
