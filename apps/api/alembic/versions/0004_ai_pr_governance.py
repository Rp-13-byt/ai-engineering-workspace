"""Add AI pull request governance metadata

Revision ID: 0004_ai_pr_governance
Revises: 0003_snapshots
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_ai_pr_governance"
down_revision: Union[str, None] = "0003_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pull_requests",
        sa.Column("approval_status", sa.String(length=40), nullable=False, server_default="Not Required"),
    )
    op.add_column(
        "pull_requests",
        sa.Column("labels_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column(
        "pull_requests",
        sa.Column("risk_assessment_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "pull_requests",
        sa.Column("policy_evaluation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "pull_requests",
        sa.Column("security_scan_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "pull_requests",
        sa.Column("approval_history_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
    )
    op.add_column(
        "pull_requests",
        sa.Column("governance_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("pull_requests", "governance_metadata_json")
    op.drop_column("pull_requests", "approval_history_json")
    op.drop_column("pull_requests", "security_scan_json")
    op.drop_column("pull_requests", "policy_evaluation_json")
    op.drop_column("pull_requests", "risk_assessment_json")
    op.drop_column("pull_requests", "labels_json")
    op.drop_column("pull_requests", "approval_status")
