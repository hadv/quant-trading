"""init

Revision ID: 001
Revises: 
Create Date: 2026-07-04 15:24:00.000000

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
    op.create_table('local_daily_candles',
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('trade_date', sa.Date(), nullable=False),
    sa.Column('open_price', sa.Numeric(precision=15, scale=4), nullable=True),
    sa.Column('high_price', sa.Numeric(precision=15, scale=4), nullable=True),
    sa.Column('low_price', sa.Numeric(precision=15, scale=4), nullable=True),
    sa.Column('close_price', sa.Numeric(precision=15, scale=4), nullable=True),
    sa.Column('volume', sa.BigInteger(), nullable=True),
    sa.UniqueConstraint('ticker', 'trade_date', name='uq_ticker_trade_date')
    )

    op.create_table('fractal_risk_assessments',
    sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('hurst_exponent', sa.Float(), nullable=False),
    sa.Column('fractal_dimension', sa.Float(), nullable=False),
    sa.Column('risk_level', sa.Float(), nullable=False),
    sa.Column('regime', sa.String(length=50), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False)
    )

def downgrade() -> None:
    op.drop_table('fractal_risk_assessments')
    op.drop_table('local_daily_candles')
