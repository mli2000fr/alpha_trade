import gzip

import pytest

from scripts.research.restore_analyst_archive import TABLES, extract


def test_extract_only_allowlisted_data_no_archive_ddl_execution(tmp_path):
    archive = tmp_path / "source.sql.gz"
    blocks = ["DROP TABLE IF EXISTS `unrelated`;\nCREATE TABLE `unrelated` (\n  `id` int\n) ENGINE=InnoDB;\nINSERT INTO `unrelated` VALUES (1);\n"]
    for table in TABLES:
        blocks.append(f"DROP TABLE IF EXISTS `{table}`;\nCREATE TABLE `{table}` (\n  `id` int,\n  `run_id` varchar(64)\n) ENGINE=InnoDB;\nINSERT INTO `{table}` VALUES (1,'original');\n")
    with gzip.open(archive, "wt", encoding="utf-8") as stream:
        stream.write("".join(blocks))
    output = tmp_path / "extract"
    report = extract(archive, output)
    assert set(report["tables"]) == set(TABLES)
    for table, meta in report["tables"].items():
        assert meta["columns"] == ["id", "run_id"]
        assert meta["insert_statements"] == 1
        assert (output / (table + ".sql")).read_text() == f"INSERT INTO `{table}` VALUES (1,'original');\n"
    assert not (output / "unrelated.sql").exists()
    assert extract(archive, output) == report
    (output / "stock_analyst_estimate_history.sql").write_text("corrupted")
    with pytest.raises(ValueError, match="integrity"):
        extract(archive, output)


def test_missing_schema_fails_closed(tmp_path):
    archive = tmp_path / "source.sql.gz"
    with gzip.open(archive, "wt") as stream:
        stream.write("INSERT INTO `stock_analyst_estimate_history` VALUES (1);\n")
    with pytest.raises(ValueError, match="Missing archived column layout"):
        extract(archive, tmp_path / "extract")
