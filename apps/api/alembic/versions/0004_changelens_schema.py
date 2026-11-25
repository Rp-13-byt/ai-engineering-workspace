"""changelens persistence tables

Revision ID: 0004_changelens_schema
Revises: 0003_hybrid_retrieval
Create Date: 2026-11-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_changelens_schema"
down_revision: str | None = "0003_hybrid_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "repository_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_sha", sa.String(length=64), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("blast_radius", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "dimensions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_change_analyses_repo_created",
        "change_analyses",
        ["repository_id", "created_at"],
    )
    op.create_index(
        "ix_change_analyses_commits",
        "change_analyses",
        ["repository_id", "base_sha", "head_sha"],
    )

    op.create_table(
        "change_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("change_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("symbol_name", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_change_findings_analysis",
        "change_findings",
        ["analysis_id", "severity"],
    )

    op.create_table(
        "change_test_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("change_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("selection_mode", sa.String(length=30), nullable=False),
        sa.Column(
            "selected_tests_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "omitted_tests_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("estimated_duration_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("coverage_ratio", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("fallback_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_change_test_plans_analysis",
        "change_test_plans",
        ["analysis_id", "selection_mode"],
    )


def downgrade() -> None:
    op.drop_index("ix_change_test_plans_analysis", table_name="change_test_plans")
    op.drop_table("change_test_plans")

    op.drop_index("ix_change_findings_analysis", table_name="change_findings")
    op.drop_table("change_findings")

    op.drop_index("ix_change_analyses_commits", table_name="change_analyses")
    op.drop_index("ix_change_analyses_repo_created", table_name="change_analyses")
    op.drop_table("change_analyses")
