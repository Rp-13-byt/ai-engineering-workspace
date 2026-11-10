"""seed demo data

Revision ID: 0002_seed_demo_data
Revises: 0001_initial_schema
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_demo_data"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO users (id, email, password_hash, display_name, is_verified)
        VALUES (
          '11111111-1111-1111-1111-111111111111',
          'demo@ai-workspace.local',
          '$2b$12$uLIt75eqGDmmCwVCQD7Z8OFGaozD83hPxMq3CeythkEC9yZqUhLQq',
          'Demo Engineer',
          true
        )
        ON CONFLICT (email) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO organizations (id, slug, name)
        VALUES ('22222222-2222-2222-2222-222222222222', 'demo-lab', 'Demo Lab')
        ON CONFLICT (slug) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO memberships (user_id, organization_id, role)
        VALUES (
          '11111111-1111-1111-1111-111111111111',
          '22222222-2222-2222-2222-222222222222',
          'owner'
        )
        ON CONFLICT (user_id, organization_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO repositories (
          id, organization_id, provider, owner, name, default_branch, remote_url, indexing_status
        )
        VALUES (
          '33333333-3333-3333-3333-333333333333',
          '22222222-2222-2222-2222-222222222222',
          'github',
          'openai',
          'openai-python',
          'main',
          'https://github.com/openai/openai-python',
          'queued'
        )
        ON CONFLICT (organization_id, provider, owner, name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM repositories WHERE id = '33333333-3333-3333-3333-333333333333'"))
    op.execute(sa.text("DELETE FROM memberships WHERE organization_id = '22222222-2222-2222-2222-222222222222'"))
    op.execute(sa.text("DELETE FROM organizations WHERE id = '22222222-2222-2222-2222-222222222222'"))
    op.execute(sa.text("DELETE FROM users WHERE id = '11111111-1111-1111-1111-111111111111'"))
