# app/database.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

logger = logging.getLogger(__name__)

# Build engine kwargs — pool_size/max_overflow not supported by SQLite StaticPool
_engine_kwargs = dict(
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300,
)
if "sqlite" not in settings.DATABASE_URL:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


async def get_db() -> AsyncSession:
    """Dependency to get database session.
    
    ✅ FIX #3: Removed the duplicate commit() here.
    Services call db.commit() themselves. Adding a second commit() after
    the service already committed causes InvalidRequestError on some
    SQLAlchemy async builds and is always wrong.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully.")


async def close_db():
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed.")
