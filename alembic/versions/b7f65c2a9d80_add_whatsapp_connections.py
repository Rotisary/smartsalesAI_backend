"""add whatsapp connections

Revision ID: b7f65c2a9d80
Revises: 962aa9e1ad66
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f65c2a9d80"
down_revision: Union[str, None] = "962aa9e1ad66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_connections",
        sa.Column("phone_number_id", sa.String(length=64), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("whatsapp_business_account_id", sa.String(length=64), nullable=False),
        sa.Column("display_phone_number", sa.String(length=32), nullable=False),
        sa.Column("verified_name", sa.String(length=255), nullable=True),
        sa.Column("encrypted_access_token", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("phone_number_id"),
    )
    op.create_index(
        op.f("ix_whatsapp_connections_business_id"),
        "whatsapp_connections",
        ["business_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_whatsapp_connections_whatsapp_business_account_id"),
        "whatsapp_connections",
        ["whatsapp_business_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_whatsapp_connections_whatsapp_business_account_id"),
        table_name="whatsapp_connections",
    )
    op.drop_index(
        op.f("ix_whatsapp_connections_business_id"),
        table_name="whatsapp_connections",
    )
    op.drop_table("whatsapp_connections")
