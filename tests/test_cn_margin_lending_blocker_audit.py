import io
import json
import zipfile

import pytest

from service.market.cn_margin_lending_blocker_audit import (
    archive,
    compare_panels,
    economic_panel,
    szse_summary,
)
from service.market.cn_margin_lending_pilot import SSE_FIELDS, SZSE_FIELDS


def test_economic_comparison_ignores_order():
    assert compare_panels({"a": (1,), "b": (2,)}, {"b": (2,), "a": (1,)})["economic_rows_changed"] == 0
    assert compare_panels({"a": (1,)}, {"a": (2,), "b": (1,)})["added"] == ["b"]
    assert compare_panels({"a": (1,)}, {"a": (2,)})["economic_rows_changed"] == 1


def test_wrong_date_rejected():
    row = {"stockCode": "600000", "opDate": "20200101", **dict.fromkeys(SSE_FIELDS, 0)}
    with pytest.raises(ValueError, match="wrong SSE date"):
        economic_panel(json.dumps({"result": [row]}).encode(), "2020-01-02")


def test_archive_preserves_receipt_and_detects_tampering(tmp_path, monkeypatch):
    monkeypatch.setattr("service.market.cn_margin_lending_blocker_audit.request_bytes",
                        lambda *a, **kw: b"raw")
    report = {"sources": {}}
    archive(tmp_path, "source", "https://www.szse.cn/test", report)
    receipt = report["sources"]["source"].copy()
    archive(tmp_path, "source", "https://www.szse.cn/test", report)
    assert report["sources"]["source"] == receipt
    assert receipt["historical_vintage_proven"] is False
    (tmp_path / "source").write_bytes(b"altered")
    with pytest.raises(ValueError, match="Altered"):
        archive(tmp_path, "source", "https://www.szse.cn/test", report)


@pytest.mark.parametrize("invalid_unit", [False, True])
def test_summary_matches_named_measures_not_column_position(invalid_unit):
    columns = list("ABCDEF")
    fields = list(reversed(SZSE_FIELDS))
    header = "".join(
        f'<c r="{c}1" t="inlineStr"><is><t>{field}'
        f'({"亿元" if invalid_unit else "股/份" if field in {"融券卖出量", "融券余量"} else "元"})'
        '</t></is></c>'
        for c, field in zip(columns, fields, strict=True))
    values = "".join(f'<c r="{c}2"><v>{i}</v></c>' for i, c in enumerate(columns))
    xml = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           f'<sheetData><row>{header}</row><row>{values}</row></sheetData></worksheet>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as workbook:
        workbook.writestr("xl/worksheets/sheet1.xml", xml)
    if invalid_unit:
        with pytest.raises(ValueError, match="unit"):
            szse_summary(buffer.getvalue())
    else:
        assert szse_summary(buffer.getvalue()) == dict(zip(fields, range(6), strict=True))
