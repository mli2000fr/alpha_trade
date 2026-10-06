import hashlib
import zipfile

import pytest

from service.fr.esma_firds_reference_pilot import extract_reference_files, summarize


XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<BizData xmlns="urn:head"><Pyld><Document xmlns="urn:auth">
<FinInstrmRptgRefDataRpt><RefData>
<FinInstrmGnlAttrbts><Id>FR0000120271</Id><FullNm>Example</FullNm>
<ClssfctnTp>ESVUFR</ClssfctnTp><NtnlCcy>EUR</NtnlCcy></FinInstrmGnlAttrbts>
<TradgVnRltdAttrbts><Id>XPAR</Id><FrstTradDt>2016-01-01</FrstTradDt></TradgVnRltdAttrbts>
</RefData></FinInstrmRptgRefDataRpt></Document></Pyld></BizData>"""


def test_esma_snapshot_extracts_target_only_and_never_auto_approves(tmp_path):
    path = tmp_path / "FULINS_E_20240113_01of01.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("reference.xml", XML)
    checksum = hashlib.md5(path.read_bytes()).hexdigest()
    matches, files = extract_reference_files([path], {"FR0000120271"}, {path.name: checksum})
    assert len(matches) == 1
    assert matches[0]["mic"] == "XPAR"
    subset = {"symbols": [{"symbol": "TTE.PA", "isin_reported": "FR0000120271",
                           "status": "CANDIDATE_REQUIRES_EXTERNAL_PROOFS",
                           "provider_status_current": "active"}]}
    report = summarize(subset, matches, files)
    assert report["by_snapshot"]["20240113"]["xpar"] == 1
    assert report["symbols"][0]["canonical_go"] is False


def test_esma_snapshot_rejects_checksum_mismatch(tmp_path):
    path = tmp_path / "FULINS_E_20240113_01of01.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("reference.xml", XML)
    with pytest.raises(ValueError, match="checksum ESMA incorrect"):
        extract_reference_files([path], {"FR0000120271"}, {path.name: "0" * 32})
