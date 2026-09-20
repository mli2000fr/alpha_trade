"""Produit les preuves de parité et de couverture du Sprint 5.

Le contrôle compare les mêmes faits lus par l'ancienne clé ``symbol`` et par
la clé canonique ``instrument_id``. Il audite aussi les jointures SQL critiques
restant exclusivement basées sur ``symbol`` et confirme qu'aucune identité CN
n'a été chargée dans les faits US.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine
from service.market.bootstrap_us_instruments import FACT_TABLES, audit_us_fact_coverage

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts" / "audits" / "market_integration" / "sprint_05"
PARITY_TABLES = {
    "stock_bars_daily": "date",
    "model_predictions": "prediction_date",
    "global_rank_history": "date",
    "global_oracle_labels": "prediction_date",
    "oracle_extreme_predictions": "prediction_date",
}
SOURCE_ROOTS = ("database", "backtesting", "modelFactory", "screener", "selector", "service")
SYMBOL_JOIN = re.compile(r"\b\w+\.symbol\s*=\s*\w+\.symbol\b", re.IGNORECASE)
ALLOWED_SYMBOL_JOIN_FILES = {
    "service/market/bootstrap_us_instruments.py",
    "service/forward_pit/batch.py",
}


def _stable_frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.copy()
    for column in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[column]):
            normalized[column] = normalized[column].astype("string")
    normalized = normalized.fillna("__NULL__").astype(str)
    if len(normalized.columns):
        normalized = normalized.sort_values(list(normalized.columns), kind="stable").reset_index(drop=True)
    payload = normalized.to_json(orient="split", date_format="iso", default_handler=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compare_symbol_and_instrument_reads(
    engine: Engine,
    table: str,
    date_column: str,
    *,
    sample_size: int,
) -> dict[str, Any]:
    columns = [column["name"] for column in inspect(engine).get_columns(table) if column["name"] != "instrument_id"]
    select_columns = ",".join(f"`{column}`" for column in columns)
    with engine.connect() as connection:
        samples = connection.execute(
            text(f"""
            SELECT instrument_id, MIN(symbol) AS symbol
            FROM `{table}`
            WHERE instrument_id IS NOT NULL
            GROUP BY instrument_id
            ORDER BY instrument_id
            LIMIT :sample_size
        """),
            {"sample_size": sample_size},
        ).mappings().all()
        maximum = connection.execute(text(f"SELECT MAX(`{date_column}`) FROM `{table}`")).scalar()
    if not samples or maximum is None:
        return {"status": "EMPTY", "rows_symbol": 0, "rows_instrument": 0}
    instrument_ids = [int(row["instrument_id"]) for row in samples]
    symbols = [str(row["symbol"]) for row in samples]
    symbol_params = {f"symbol_{index}": symbol for index, symbol in enumerate(symbols)}
    id_params = {f"id_{index}": value for index, value in enumerate(instrument_ids)}
    symbol_bindings = ",".join(f":symbol_{index}" for index in range(len(symbols)))
    id_bindings = ",".join(f":id_{index}" for index in range(len(instrument_ids)))
    order = ",".join(f"`{column}`" for column in ("symbol", date_column) if column in columns)
    with engine.connect() as connection:
        by_symbol = pd.read_sql(
            text(f"SELECT {select_columns} FROM `{table}` WHERE symbol IN ({symbol_bindings}) ORDER BY {order}"),
            connection,
            params=symbol_params,
        )
        by_instrument = pd.read_sql(
            text(
                f"SELECT {select_columns} FROM `{table}` WHERE instrument_id IN ({id_bindings}) ORDER BY {order}"
            ),
            connection,
            params=id_params,
        )
    symbol_hash = _stable_frame_hash(by_symbol)
    instrument_hash = _stable_frame_hash(by_instrument)
    return {
        "status": "PASS" if symbol_hash == instrument_hash else "FAIL",
        "sample_instruments": len(instrument_ids),
        "max_date": str(maximum),
        "rows_symbol": len(by_symbol),
        "rows_instrument": len(by_instrument),
        "symbol_hash": symbol_hash,
        "instrument_hash": instrument_hash,
    }


def audit_symbol_only_joins(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for source_root in SOURCE_ROOTS:
        for path in (root / source_root).rglob("*.py"):
            relative = path.relative_to(root).as_posix()
            if relative in ALLOWED_SYMBOL_JOIN_FILES or "__pycache__" in relative:
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            for match in SYMBOL_JOIN.finditer(source):
                line_number = source.count("\n", 0, match.start()) + 1
                line = source.splitlines()[line_number - 1]
                findings.append({"file": relative, "line": line_number, "sql": line.strip()})
    return {"critical_count": len(findings), "findings": findings}


def run(
    engine: Engine,
    output_dir: Path,
    sample_size: int = 25,
    *,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage = coverage or audit_us_fact_coverage(engine)
    parity = {
        table: compare_symbol_and_instrument_reads(engine, table, date_column, sample_size=sample_size)
        for table, date_column in PARITY_TABLES.items()
        if table in inspect(engine).get_table_names()
    }
    joins = audit_symbol_only_joins()
    with engine.connect() as connection:
        cn_instruments = int(
            connection.execute(
                text("SELECT COUNT(*) FROM instruments WHERE market_code IN ('CN_A','CN_BJ')")
            ).scalar()
            or 0
        )
        # Tant qu'aucun instrument CN n'existe dans le registre canonique, aucune
        # table de faits ne peut contenir une écriture CN valide. Éviter ici 33
        # scans complets coûteux avant la création des index de la migration 0088.
        cn_fact_rows = 0
        if cn_instruments:
            existing_tables = set(inspect(engine).get_table_names())
            for table in FACT_TABLES:
                if table not in existing_tables:
                    continue
                cn_fact_rows += int(
                    connection.execute(
                        text(f"""
                        SELECT COUNT(*) FROM `{table}` t
                        JOIN instruments i ON i.instrument_id=t.instrument_id
                        WHERE i.market_code IN ('CN_A','CN_BJ')
                    """)
                    ).scalar()
                    or 0
                )
    parity_pass = all(row["status"] in {"PASS", "EMPTY"} for row in parity.values())
    gate = (
        "GO"
        if coverage["gate"] == "PASS" and parity_pass and joins["critical_count"] == 0 and cn_fact_rows == 0
        else "NO_GO"
    )
    report = {
        "sprint": 5,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": gate,
        "coverage_gate": coverage["gate"],
        "parity": parity,
        "symbol_only_joins": joins,
        "cn_canonical_writes": {"instrument_rows": cn_instruments, "fact_rows": cn_fact_rows},
    }
    (output_dir / "coverage_report.json").write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    (output_dir / "parity_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output_dir / "gate_result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-size", type=int, default=25)
    parser.add_argument(
        "--reuse-coverage-report",
        action="store_true",
        help="Réutilise le rapport exhaustif produit juste avant par le bootstrap.",
    )
    args = parser.parse_args()
    coverage = None
    coverage_path = args.output_dir / "coverage_report.json"
    if args.reuse_coverage_report and coverage_path.exists():
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        if coverage.get("gate") != "PASS":
            raise SystemExit("Le rapport de couverture réutilisé n'est pas PASS.")
    result = run(
        get_sqlalchemy_engine(),
        args.output_dir,
        max(1, args.sample_size),
        coverage=coverage,
    )
    print(json.dumps({"status": result["status"], "output_dir": str(args.output_dir)}, sort_keys=True))
    if result["status"] != "GO":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
