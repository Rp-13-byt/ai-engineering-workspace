"""hybrid retrieval and incremental indexing

Revision ID: 0003_hybrid_retrieval
Revises: 0002_seed_demo_data
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_hybrid_retrieval"
down_revision: str | None = "0002_seed_demo_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add columns to repositories
    op.add_column(
        "repositories",
        sa.Column("embedding_model", sa.String(length=80), nullable=True),
    )

    # 2. Add columns to code_chunks
    op.add_column(
        "code_chunks",
        sa.Column("symbol_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "code_chunks",
        sa.Column("parent_scope", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "code_chunks",
        sa.Column("embedding_model", sa.String(length=80), nullable=True),
    )

    # 3. Create indexes for symbol, model, path, and full-text search
    op.create_index("ix_code_chunks_symbol", "code_chunks", ["symbol"])
    op.create_index("ix_code_chunks_embedding_model", "code_chunks", ["embedding_model"])
    op.create_index("ix_code_documents_repo_path", "code_documents", ["repository_id", "path"])
    op.execute(
        "CREATE INDEX ix_code_chunks_search_vector "
        "ON code_chunks USING gin (to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_search_vector")
    op.drop_index("ix_code_documents_repo_path", table_name="code_documents")
    op.drop_index("ix_code_chunks_embedding_model", table_name="code_chunks")
    op.drop_index("ix_code_chunks_symbol", table_name="code_chunks")

    op.drop_column("code_chunks", "embedding_model")
    op.drop_column("code_chunks", "parent_scope")
    op.drop_column("code_chunks", "symbol_type")

    op.drop_column("repositories", "embedding_model")
