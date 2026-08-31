from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    from app.models.user import User
    from app.models.api_key import APIKey
    from app.models.trade import Trade
    from app.models.autonomous_agent import (
        AutonomousAgentState,
    )

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )