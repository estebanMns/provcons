"""Órdenes con varios materiales (order_items)

Revision ID: b7e4c2a91f30
Revises: 099ceff98c05
Create Date: 2026-10-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e4c2a91f30'
down_revision: Union[str, None] = '099ceff98c05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('quotation_id', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('total_amount', sa.Float(), nullable=True))
    op.create_foreign_key('orders_quotation_id_fkey', 'orders', 'quotations', ['quotation_id'], ['id'])
    op.alter_column('orders', 'match_id', existing_type=sa.Integer(), nullable=True)

    op.create_table('order_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('match_id', sa.Integer(), nullable=True),
    sa.Column('quotation_item_id', sa.Integer(), nullable=True),
    sa.Column('requested_material', sa.String(length=200), nullable=False),
    sa.Column('material_name', sa.String(length=200), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=False),
    sa.Column('unit_price', sa.Float(), nullable=True),
    sa.Column('subtotal', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ),
    sa.ForeignKeyConstraint(['quotation_item_id'], ['quotation_items.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_order_items_order_id', 'order_items', ['order_id'])

    # Las órdenes antiguas (un material por orden, vía match_id) pasan a tener
    # su material como una línea en order_items, con su cotización y total.
    op.execute("""
        INSERT INTO order_items (order_id, match_id, quotation_item_id, requested_material,
                                 material_name, quantity, unit, unit_price, subtotal)
        SELECT o.id, m.id, qi.id, qi.material_name, pi.material_name, qi.quantity, qi.unit,
               pi.unit_price, pi.unit_price * qi.quantity
        FROM orders o
        JOIN matches m ON m.id = o.match_id
        JOIN quotation_items qi ON qi.id = m.quotation_item_id
        JOIN provider_inventory pi ON pi.id = m.provider_inventory_id
    """)
    op.execute("""
        UPDATE orders o
        SET quotation_id = qi.quotation_id,
            total_amount = oi.subtotal
        FROM order_items oi
        JOIN quotation_items qi ON qi.id = oi.quotation_item_id
        WHERE oi.order_id = o.id AND o.match_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index('ix_order_items_order_id', table_name='order_items')
    op.drop_table('order_items')
    # Las órdenes nuevas no tienen match_id: no se puede volver a NOT NULL
    # sin borrarlas, así que se eliminan antes de restaurar la restricción.
    op.execute("DELETE FROM orders WHERE match_id IS NULL")
    op.alter_column('orders', 'match_id', existing_type=sa.Integer(), nullable=False)
    op.drop_constraint('orders_quotation_id_fkey', 'orders', type_='foreignkey')
    op.drop_column('orders', 'total_amount')
    op.drop_column('orders', 'quotation_id')
