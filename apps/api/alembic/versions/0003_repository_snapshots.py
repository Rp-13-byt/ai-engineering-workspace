"""Add repository snapshots and branches

Revision ID: 0003_snapshots
Revises: 0002_seed_demo_data
Create Date: 2026-06-07 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0003_snapshots'
down_revision: Union[str, None] = '0002_seed_demo_data'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create repository_branches table
    op.create_table(
        'repository_branches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('last_commit_sha', sa.String(length=80), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('repository_id', 'name', name='uq_repository_branch_name')
    )
    
    # Create repository_snapshots table
    op.create_table(
        'repository_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('repository_id', sa.UUID(), nullable=False),
        sa.Column('branch', sa.String(length=120), nullable=False),
        sa.Column('commit_sha', sa.String(length=80), nullable=False),
        sa.Column('documents_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='running'),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['repository_id'], ['repositories.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_repository_snapshots_repo_started', 'repository_snapshots', ['repository_id', 'started_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_repository_snapshots_repo_started', table_name='repository_snapshots')
    op.drop_table('repository_snapshots')
    op.drop_table('repository_branches')
