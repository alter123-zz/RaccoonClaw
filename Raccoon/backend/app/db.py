"""SQLAlchemy async 引擎与 session 管理。"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

_engine_kwargs = {
    "echo": settings.debug,
    "pool_pre_ping": True,
}
# SQLite 不支持 pool_size / max_overflow
if "sqlite" not in settings.database_url:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入 — 获取异步数据库 session。"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """开发用 — 创建所有表（生产用 Alembic）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
