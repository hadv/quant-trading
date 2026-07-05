"""initial tables

Revision ID: 001
Revises: 
Create Date: 2026-07-05 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create fundamental_data_cache table
    op.create_table(
        'fundamental_data_cache',
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('pe_ratio', sa.Float(), nullable=False),
        sa.Column('pb_ratio', sa.Float(), nullable=False),
        sa.Column('free_cash_flow', sa.Float(), nullable=False),
        sa.Column('revenue_growth_yoy', sa.Float(), nullable=False),
        sa.Column('profit_margin', sa.Float(), nullable=False),
        sa.Column('debt_to_equity', sa.Float(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('ticker')
    )

    # Create fundamental_assessments table
    op.create_table(
        'fundamental_assessments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('intrinsic_value', sa.Float(), nullable=False),
        sa.Column('moat_score', sa.Integer(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('fundamental_assessments')
    op.drop_table('fundamental_data_cache')
