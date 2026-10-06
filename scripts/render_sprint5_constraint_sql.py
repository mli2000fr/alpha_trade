"""Génère le SQL autonome de la migration Sprint 5 / phase 2."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "0088_us_fact_instrument_constraints.py"
OUTPUT = ROOT / "database" / "sql" / "migration_0088_us_fact_instrument_constraints.sql"


def _migration_module():
    spec = importlib.util.spec_from_file_location("migration_0088", MIGRATION)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Migration illisible: {MIGRATION}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render() -> str:
    module = _migration_module()
    lines = [
        "-- Généré par scripts/render_sprint5_constraint_sql.py.",
        "-- Exécuter uniquement après PASS de bootstrap_us_instruments --mode audit.",
        "-- Alembic reste le chemin d'application canonique.",
        "",
    ]
    for table, date_column in module.TABLE_DATES.items():
        columns = "`instrument_id`" + (f", `{date_column}`" if date_column else "")
        index_name = f"ix_iid_{table}"[:64]
        foreign_key = f"fk_iid_{table}"[:64]
        lines.extend(
            [
                f"ALTER TABLE `{table}`",
                f"  ADD INDEX `{index_name}` ({columns}),",
                f"  ADD CONSTRAINT `{foreign_key}` FOREIGN KEY (`instrument_id`)",
                "    REFERENCES `instruments` (`instrument_id`) ON DELETE RESTRICT;",
                "",
            ]
        )
    lines.append("DELIMITER $$")
    for table in module.TABLE_DATES:
        for suffix, timing in (("bi", "INSERT"), ("bu", "UPDATE")):
            name = f"trg_iid_{table}_{suffix}"
            body = module._trigger_sql(table, timing).strip()
            lines.extend([f"DROP TRIGGER IF EXISTS `{name}`$$", f"{body}$$", ""])
    lines.extend(["DELIMITER ;", ""])
    return "\n".join(lines)


def main() -> None:
    OUTPUT.write_text(render(), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
