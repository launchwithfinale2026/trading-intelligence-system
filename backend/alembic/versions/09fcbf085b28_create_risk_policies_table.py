"""create risk_policies table

Revision ID: 09fcbf085b28
Revises: c8ff9d11c1f8
Create Date: 2026-07-24 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09fcbf085b28'
down_revision: Union[str, Sequence[str], None] = 'c8ff9d11c1f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


risk_policies_table = sa.table(
    'risk_policies',
    sa.column('name', sa.String),
    sa.column('description', sa.String),
    sa.column('breakpoints', sa.JSON),
)

# Conservative/moderate/aggressive: a single breakpoint means "flat
# regardless of account size" (see risk/policy.py) — these reproduce the
# same fixed percents that used to live only in risk/calculator.py, now
# editable as data instead of code.
#
# Experimental: the account-size-scaled curve requested for the very small
# starting account — 50% risk per trade at $10, tapering linearly down to
# 1% by $10,000, flat 1% above that. Adjust by editing this row's
# breakpoints; no code change needed.
_SEED_POLICIES = [
    {
        "name": "conservative",
        "description": "Flat 0.5% risk per trade, any account size.",
        "breakpoints": [["0", "0.005"]],
    },
    {
        "name": "moderate",
        "description": "Flat 1% risk per trade, any account size.",
        "breakpoints": [["0", "0.01"]],
    },
    {
        "name": "aggressive",
        "description": "Flat 2% risk per trade, any account size.",
        "breakpoints": [["0", "0.02"]],
    },
    {
        "name": "experimental",
        "description": "50% risk per trade at $10, linearly tapering to 1% by $10,000, flat 1% beyond.",
        "breakpoints": [["10", "0.50"], ["999", "0.20"], ["10000", "0.01"]],
    },
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('risk_policies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=32), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('breakpoints', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_risk_policies_name'), 'risk_policies', ['name'], unique=True)

    op.bulk_insert(risk_policies_table, _SEED_POLICIES)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_risk_policies_name'), table_name='risk_policies')
    op.drop_table('risk_policies')
