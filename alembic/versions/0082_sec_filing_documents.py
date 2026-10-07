"""Store SEC filing exhibits as separate bounded documents.

Revision ID: 0082_sec_filing_documents
Revises: 0081_widen_forward_pit_providers
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0082_sec_filing_documents"
down_revision: str | None = "0081_widen_forward_pit_providers"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
SCHEMA = "alpha_trade"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("sec_filing_documents", schema=SCHEMA):
        op.create_table(
            "sec_filing_documents",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("accession_number", sa.String(32), nullable=False),
            sa.Column("document_sequence", sa.Integer(), nullable=True),
            sa.Column("document_type", sa.String(32), nullable=False),
            sa.Column("document_name", sa.String(255), nullable=False),
            sa.Column("description", sa.String(512), nullable=True),
            sa.Column("document_url", sa.String(512), nullable=False),
            sa.Column("mime_type", sa.String(128), nullable=True),
            sa.Column("content_bytes", sa.BigInteger(), nullable=True),
            sa.Column("content_sha256", sa.String(64), nullable=True),
            sa.Column("content_blob", mysql.LONGBLOB(), nullable=True),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("available_at", sa.DateTime(), nullable=False),
            sa.Column("run_id", sa.String(64), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "accession_number", "document_name",
                name="uq_sfd_accession_document",
            ),
            schema=SCHEMA,
        )

    indexes = {
        str(index["name"])
        for index in sa.inspect(op.get_bind()).get_indexes(
            "sec_filing_documents", schema=SCHEMA,
        )
    }
    if "idx_sfd_type_available" not in indexes:
        op.create_index(
            "idx_sfd_type_available", "sec_filing_documents",
            ["document_type", "available_at"], schema=SCHEMA,
        )
    if "idx_sfd_accession" not in indexes:
        op.create_index(
            "idx_sfd_accession", "sec_filing_documents",
            ["accession_number"], schema=SCHEMA,
        )

def downgrade() -> None:
    op.drop_index("idx_sfd_accession", table_name="sec_filing_documents", schema=SCHEMA)
    op.drop_index("idx_sfd_type_available", table_name="sec_filing_documents", schema=SCHEMA)
    op.drop_table("sec_filing_documents", schema=SCHEMA)
