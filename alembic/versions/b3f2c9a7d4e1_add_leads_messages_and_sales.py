"""add leads messages and sales

Revision ID: b3f2c9a7d4e1
Revises: 962aa9e1ad66
Create Date: 2026-06-11 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b3f2c9a7d4e1"
down_revision: Union[str, None] = "962aa9e1ad66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


channel_enum = postgresql.ENUM(
    "whatsapp",
    "instagram",
    "web",
    name="channel_enum",
    create_type=False,
)
lead_status_enum = postgresql.ENUM(
    "new",
    "warm",
    "hot",
    "closed",
    "lost",
    name="lead_status_enum",
    create_type=False,
)
message_sender_enum = postgresql.ENUM(
    "customer",
    "ai",
    "agent",
    name="message_sender_enum",
    create_type=False,
)
sale_status_enum = postgresql.ENUM(
    "pending",
    "completed",
    "refunded",
    name="sale_status_enum",
    create_type=False,
)
sale_channel_enum = postgresql.ENUM(
    "whatsapp",
    "instagram",
    "web",
    name="sale_channel_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("whatsapp", "instagram", "web", name="channel_enum").create(bind, checkfirst=True)
    postgresql.ENUM("new", "warm", "hot", "closed", "lost", name="lead_status_enum").create(bind, checkfirst=True)
    postgresql.ENUM("customer", "ai", "agent", name="message_sender_enum").create(bind, checkfirst=True)
    postgresql.ENUM("pending", "completed", "refunded", name="sale_status_enum").create(bind, checkfirst=True)
    postgresql.ENUM("whatsapp", "instagram", "web", name="sale_channel_enum").create(bind, checkfirst=True)

    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("channel", channel_enum, nullable=False),
        sa.Column("status", lead_status_enum, nullable=False),
        sa.Column("intent_tags", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("unread_count", sa.Integer(), nullable=False),
        sa.Column("last_message", sa.String(), nullable=True),
        sa.Column("lead_score", sa.Integer(), nullable=False),
        sa.Column("is_human_mode", sa.Boolean(), nullable=False),
        sa.Column("human_assigned_to", sa.String(length=255), nullable=True),
        sa.Column("last_customer_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "phone", name="uq_leads_business_phone"),
    )
    op.create_index(op.f("ix_leads_business_id"), "leads", ["business_id"], unique=False)
    op.create_index(op.f("ix_leads_phone"), "leads", ["phone"], unique=False)
    op.create_index(op.f("ix_leads_status"), "leads", ["status"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("sender", message_sender_enum, nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("intent_tag", sa.String(length=64), nullable=True),
        sa.Column("wa_message_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "wa_message_id", name="uq_messages_business_wa_id"),
    )
    op.create_index(op.f("ix_messages_business_id"), "messages", ["business_id"], unique=False)
    op.create_index(op.f("ix_messages_lead_id"), "messages", ["lead_id"], unique=False)
    op.create_index(op.f("ix_messages_sender"), "messages", ["sender"], unique=False)

    op.create_table(
        "sales",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("business_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("customer", sa.String(length=255), nullable=False),
        sa.Column("product", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sale_status_enum, nullable=False),
        sa.Column("channel", sale_channel_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sales_business_id"), "sales", ["business_id"], unique=False)
    op.create_index(op.f("ix_sales_lead_id"), "sales", ["lead_id"], unique=False)
    op.create_index(op.f("ix_sales_status"), "sales", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sales_status"), table_name="sales")
    op.drop_index(op.f("ix_sales_lead_id"), table_name="sales")
    op.drop_index(op.f("ix_sales_business_id"), table_name="sales")
    op.drop_table("sales")

    op.drop_index(op.f("ix_messages_sender"), table_name="messages")
    op.drop_index(op.f("ix_messages_lead_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_business_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_leads_status"), table_name="leads")
    op.drop_index(op.f("ix_leads_phone"), table_name="leads")
    op.drop_index(op.f("ix_leads_business_id"), table_name="leads")
    op.drop_table("leads")

    bind = op.get_bind()
    sale_channel_enum.drop(bind, checkfirst=True)
    sale_status_enum.drop(bind, checkfirst=True)
    message_sender_enum.drop(bind, checkfirst=True)
    lead_status_enum.drop(bind, checkfirst=True)
    channel_enum.drop(bind, checkfirst=True)
