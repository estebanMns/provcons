"""Inventario con código por producto (sku) y borrado lógico (is_active)

Revision ID: e5b2c9d47a13
Revises: d9a3b7c61e02
Create Date: 2026-11-02 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b2c9d47a13'
down_revision: Union[str, None] = 'd9a3b7c61e02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('provider_inventory', sa.Column('sku', sa.String(length=60), nullable=True))
    op.add_column('provider_inventory', sa.Column(
        'is_active', sa.Boolean(), nullable=False, server_default=sa.true(),
    ))
    # Los productos que ya existen reciben un código automático por proveedor:
    # P-0001, P-0002... en el orden en que se crearon
    op.execute("""
        UPDATE provider_inventory AS p
        SET sku = 'P-' || lpad(s.rn::text, 4, '0')
        FROM (
            SELECT id, row_number() OVER (PARTITION BY provider_org_id ORDER BY id) AS rn
            FROM provider_inventory
        ) AS s
        WHERE p.id = s.id
    """)
    op.alter_column('provider_inventory', 'sku', existing_type=sa.String(length=60), nullable=False)
    op.create_index('uq_inventory_provider_sku', 'provider_inventory', ['provider_org_id', 'sku'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_inventory_provider_sku', table_name='provider_inventory')
    op.drop_column('provider_inventory', 'is_active')
    op.drop_column('provider_inventory', 'sku')
