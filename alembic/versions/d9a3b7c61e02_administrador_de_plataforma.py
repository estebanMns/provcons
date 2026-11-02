"""Administrador de la plataforma (distinto del admin de cada empresa)

Revision ID: d9a3b7c61e02
Revises: c4d1e8f20a57
Create Date: 2026-11-01 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9a3b7c61e02'
down_revision: Union[str, None] = 'c4d1e8f20a57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'is_platform_admin', sa.Boolean(), nullable=False, server_default=sa.false(),
    ))


def downgrade() -> None:
    op.drop_column('users', 'is_platform_admin')
