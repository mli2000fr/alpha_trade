"""Daily first observation wins; preserve all fiscal periods, no Yahoo writes."""
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

TABLE = 'stock_analyst_consensus_eodhd_history'


def persist_rows(conn, rows):
    count = 0
    for row in rows:
        columns = list(row)
        query = text(f"INSERT INTO {TABLE} ({','.join(columns)}) VALUES "
                     f"({','.join(':'+c for c in columns)})")
        try:
            with conn.begin_nested():
                conn.execute(query, row)
        except IntegrityError as exc:
            # Only a duplicate logical key is idempotent. All other SQL failures
            # must propagate; do not use INSERT IGNORE which masks invalid data.
            code = exc.orig.args[0] if exc.orig.args else None
            if code != 1062 and 'UNIQUE constraint failed' not in str(exc.orig):
                raise
        else:
            count += 1
    return count
