from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.logger import get_logger
from infrastructure.environment import env
from infrastructure.database.models import Base


def get_db_url():
    pg = env.postgres

    db_url: URL = URL.create(
        drivername=pg.drivername,
        username=pg.user,
        password=pg.password,
        host=pg.host,
        port=pg.port,
        database=pg.db,
    )
    return db_url


logger = get_logger(f"{__name__}.DBSessionFactory", 20)


class DBSessionFactory:
    session_count: int = 0

    def __init__(self):
        database_url = get_db_url()
        self.engine = create_async_engine(database_url, echo=False)
        self.session_maker = async_sessionmaker(self.engine)

    async def create_tables(self) -> None:
        """Создаёт отсутствующие таблицы по метаданным моделей (идемпотентно)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("DB initiated")

    async def get_session(self) -> AsyncSession:
        """Возращает новую сессию"""
        DBSessionFactory.session_count += 1
        logger.debug(f"new session open - opened {DBSessionFactory.session_count}")
        return self.session_maker()

    async def dispose(self) -> None:
        logger.debug("dispose request")
        await self.engine.dispose()
        DBSessionFactory.session_count = 0
        logger.debug(f"engine disposed - open {DBSessionFactory.session_count}")
