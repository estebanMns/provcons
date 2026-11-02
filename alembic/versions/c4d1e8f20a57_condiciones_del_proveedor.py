"""Condiciones del proveedor: cuotas, tasa, tiempo de entrega y propuesta

Revision ID: c4d1e8f20a57
Revises: b7e4c2a91f30
Create Date: 2026-11-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c4d1e8f20a57'
down_revision: Union[str, None] = 'b7e4c2a91f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Todas opcionales: las órdenes existentes quedan con null y se ven como antes
_COLUMNS = [
    sa.Column('installments', sa.Integer(), nullable=True),
    sa.Column('monthly_rate_pct', sa.Float(), nullable=True),
    sa.Column('installment_amount', sa.Float(), nullable=True),
    sa.Column('financed_total', sa.Float(), nullable=True),
    sa.Column('delivery_days', sa.Integer(), nullable=True),
    sa.Column('promised_delivery_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('proposal', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
]


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column('orders', column)


def downgrade() -> None:
    for column in reversed(_COLUMNS):
        op.drop_column('orders', column.name)
