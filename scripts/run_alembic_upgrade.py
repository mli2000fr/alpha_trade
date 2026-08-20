"""Outils alembic avec l'URL DB réelle du projet.

Contourne l'URL placeholder de alembic.ini (driver://user:pass@localhost/dbname)
en injectant le DSN résolu par database.connection.get_database_url().

Usage :
    python scripts/run_alembic_upgrade.py stamp <rev>   # marque rev comme appliquée SANS l'exécuter
    python scripts/run_alembic_upgrade.py upgrade <rev> # exécute les migrations jusqu'à rev
"""
from __future__ import annotations

import os
import sys

from alembic import command
from alembic.config import Config

from database.connection import get_database_url


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "upgrade"
    rev = args[1] if len(args) > 1 else "head"

    url = get_database_url()
    print(f"DB URL: {url.split('@')[-1] if '@' in url else url}  (host/base masqué)")
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    os.environ.setdefault("PYTHONPATH", os.path.dirname(os.path.abspath(__file__)))

    if cmd == "stamp":
        command.stamp(cfg, rev)
        print(f"stamp -> {rev}")
    else:
        command.upgrade(cfg, rev)
        print(f"upgrade -> {rev}")


if __name__ == "__main__":
    main()
