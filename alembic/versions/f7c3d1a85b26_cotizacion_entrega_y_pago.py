"""Cotización con dirección de entrega, descripción y forma de pago

Revision ID: f7c3d1a85b26
Revises: e5b2c9d47a13
Create Date: 2026-11-02 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7c3d1a85b26'
down_revision: Union[str, None] = 'e5b2c9d47a13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Opcionales: las cotizaciones y órdenes anteriores quedan con null
    op.add_column('quotations', sa.Column('delivery_address', sa.String(length=300), nullable=True))
    op.add_column('quotations', sa.Column('description', sa.String(length=1000), nullable=True))
    op.add_column('quotations', sa.Column('payment_installments', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('requested_installments', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'requested_installments')
    op.drop_column('quotations', 'payment_installments')
    op.drop_column('quotations', 'description')
    op.drop_column('quotations', 'delivery_address')
