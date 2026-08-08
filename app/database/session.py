"""
Database session management using SQLAlchemy async engine.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config.settings import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

# Async session factory
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager that yields an active database session and ensures it closes correctly.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
