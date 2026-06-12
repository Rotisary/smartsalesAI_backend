from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.config import settings as app_settings
from app.database import Base

from app.models.business import Business
from app.models.settings import BusinessSettings
from app.models.refresh_token import RefreshToken 
from app.models.whatsapp_connection import WhatsAppConnection
from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

config.set_main_option(
    "sqlalchemy.url",
    app_settings.DATABASE_URL.replace("+asyncpg", ""),
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script output only)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (sync psycopg2 driver)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
