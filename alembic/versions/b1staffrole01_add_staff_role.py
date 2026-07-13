"""add staff role to userrole enum

Revision ID: b1staffrole01
Revises: 9a8946bfb50e
Create Date: 2026-07-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b1staffrole01"
down_revision: Union[str, Sequence[str], None] = "9a8946bfb50e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE transaction bloğu içinde çalışamaz;
    # autocommit_block ile ayrı çalıştırıyoruz.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'staff'")


def downgrade() -> None:
    # Postgres enum değeri silmeyi desteklemez; downgrade no-op.
    pass
