import contextlib
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ayejax._interface.api.settings import settings


class SessionManager:
    def __init__(self, uri: str, **engine_kwargs) -> None:
        self._uri = uri
        self._engine_kwargs = engine_kwargs
        self._engine = None
        self._sessionmaker = None

    async def __aenter__(self):
        self._engine = create_async_engine(self._uri, **self._engine_kwargs)
        self._sessionmaker = async_sessionmaker(autocommit=False, bind=self._engine)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._engine:
            await self._engine.dispose()

        self._engine = None
        self._sessionmaker = None

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if not self._engine:
            raise RuntimeError("Engine not created. Use 'async with' context on SessionManager instance.")
        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if not self._sessionmaker:
            raise RuntimeError("Engine not created. Use 'async with' context on SessionManager instance.")
        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


sessionmanager = SessionManager(settings.POSTGRES_URI)  # This context will be entered in main.py


async def get_db_session():
    async with sessionmanager.session() as session:
        yield session


DBSessionDependency = Annotated[AsyncSession, Depends(get_db_session)]

__all__ = ["DBSessionDependency", "get_db_session"]
