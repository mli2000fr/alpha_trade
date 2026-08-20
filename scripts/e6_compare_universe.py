"""Compare l'univers Oracle O0 (405) vs ticket_recherche.txt et vs global_rank_history."""
import sys
sys.path.insert(0, "f:/projets")
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text
import pandas as pd

B = "model-factory-20260811223551-ef2cd0"

# 1. ticket_recherche.txt
with open("config/ticket_recherche.txt", "r", encoding="utf-8-sig") as f:
    raw = f.read()
ticket = sorted({s.strip().upper() for s in raw.replace("\n", ",").split(",") if s.strip()})
print(f"ticket_recherche.txt : {len(ticket)} symboles uniques")

# 2. univers Oracle (global_oracle_labels)
e = get_sqlalchemy_engine()
with e.connect() as c:
    oracle = sorted([str(s) for s in c.execute(
        text("SELECT DISTINCT symbol FROM global_oracle_labels WHERE batch_id=:b AND horizon=20"),
        {"b": B}).scalars().all()])
print(f"global_oracle_labels (batch {B}) : {len(oracle)} symboles")

# 3. pool OOS O0 (parquet)
oos = pd.read_parquet("artifacts/models/oracle/oracle-wf-20260820025255/oos_predictions.parquet", columns=["symbol"])
pool = sorted(oos["symbol"].astype(str).str.upper().unique())
print(f"pool OOS O0 (parquet) : {len(pool)} symboles")

set_t = set(ticket); set_o = set(oracle); set_p = set(pool)
print(f"\nticket ∩ oracle = {len(set_t & set_o)}")
print(f"oracle ∩ pool    = {len(set_o & set_p)}")
print(f"ticket ∩ pool    = {len(set_t & set_p)}")

extra_pool = sorted(set_p - set_t)
missing_from_ticket = sorted(set_t - set_p)
print(f"\nPool OOS PAS dans ticket ({len(extra_pool)}): {extra_pool[:40]}")
print(f"Ticket PAS dans pool OOS ({len(missing_from_ticket)}): {missing_from_ticket[:40]}")
