import datetime
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timezone

from sqlalchemy import Column, DateTime
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector 

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_development,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class BaseModel(Base):
    """Base model with automatic timestamp tracking for all entities."""
    __abstract__ = True

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
        nullable=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends-compatible session; commits on success, rolls back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Same lifecycle for service-layer `async with get_db_cm() as db`."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


get_db_cm = asynccontextmanager(get_db_context)
