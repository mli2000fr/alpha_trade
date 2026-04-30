# Guide — Ajouter une nouvelle table (Phase 7.6)

> **Audience** : développeur Alpha Trade.
> **Objectif** : checklist normative pour introduire une nouvelle table dans
> le schéma SQL (Alembic source de vérité depuis Phase 1).

---

## 1. Décisions préalables

| Question | Décision attendue |
|---|---|
| La table est-elle **versionable** ? | Oui → ajouter `schema_version INT NOT NULL DEFAULT 1` |
| La table porte-t-elle un **run_id** ? | Préfixer (`<scope>r-<uuid12>` — cf. autres tables) |
| Y a-t-il un **producteur unique** ? | Documenter dans `doc/data_lineage_matrix.md` |
| Y a-t-il des **consommateurs** ? | Idem |
| Une **enum** est-elle sur la table ? | `CHECK (col IN ('A','B','C'))` obligatoire |

---

## 2. Checklist d'implémentation

### A. Migration Alembic

1. Numéro = `0NNN_<short_name>.py` (incrément continu).
2. Template :

```python
"""Phase X.Y — <description courte>.

Réf. ``prompt/refactor/plan.md`` Phase X + audit_<module> §Z.

Revision ID: 0NNN_<short_name>
Revises: 0NNN-1_<previous>
"""
from alembic import op
import sqlalchemy as sa


revision = "0NNN_<short_name>"
down_revision = "0NNN-1_<previous>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "<table_name>",
        sa.Column("run_id", sa.String(length=40), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # ... colonnes métier ...
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        # CHECK pour enums
        sa.CheckConstraint("status IN ('OK','WARN','ALERT')", name="chk_<table>_status"),
    )
    op.create_index("ix_<table>_<col>", "<table_name>", ["<col>"])


def downgrade() -> None:
    op.drop_index("ix_<table>_<col>", table_name="<table_name>")
    op.drop_table("<table_name>")
```

3. Lancer localement :

```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

### B. Repository

1. Créer `database/repositories/<domain>.py` (sous-classe `Repository`).
2. Méthodes typées (`insert_run`, `load_latest`, …).
3. Si table exposée hors module : ajouter un Protocol dans `core/interfaces.py`.

### C. Tests

- `tests/test_<table>_migration.py` : `alembic upgrade head` puis introspection
  `sqlalchemy.inspect(engine).get_columns("<table>")`.
- `tests/test_<table>_repository.py` : insert + load round-trip.
- Enregistrer la table dans `tests/conftest.py` si fixture testcontainers.

### D. Documentation

1. Mettre à jour `doc/database.md` (section "tables").
2. Mettre à jour `doc/data_lineage_matrix.md` (matrice impact).
3. Si la table porte un `run_summary` : `core/run_summary.py` doit poser
   `schema_version`.

### E. Observabilité

- Si métrique pertinente : ajouter une `Gauge` ou `Counter` dans
  `core/metrics.py`.
- Si fraîcheur critique : alimenter `alpha_trade_data_freshness_hours{table="..."}`.

---

## 3. Gardes-fous

- ❌ **Jamais** de DDL hors Alembic (les fichiers `database/sql/*.sql` sont
  legacy uniquement, à terme supprimés).
- ❌ Pas de `ALTER TABLE` sans migration.
- ❌ Pas de colonne sans commentaire SQL pour les enums et clés métier.
- ✅ Toute table métier doit avoir un repository typé.
- ✅ Toute table doit être référencée dans `doc/data_lineage_matrix.md`.

---

**Réf.** : audit_global §7.6 ; `doc/database.md` ; Phase 1.1 plan.

