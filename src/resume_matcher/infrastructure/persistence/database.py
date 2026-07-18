from __future__ import annotations

from pathlib import Path
from typing import cast

from sqlalchemy import event, inspect, text
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from resume_matcher.infrastructure.persistence.models import Base

# Keep this value aligned with the single Alembic head. A contract test compares
# it with the migration graph so readiness cannot silently accept an old schema.
CURRENT_DATABASE_REVISION = "20260713_0001"


class Database:
    def __init__(self, url: str, *, echo: bool = False) -> None:
        if url.startswith("sqlite") and "///" in url:
            path = url.split("///", 1)[1]
            if path not in {":memory:", ""}:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=echo,
            pool_pre_ping=True,
        )
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", self._enable_sqlite_foreign_keys)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def healthcheck(self, *, require_current_schema: bool = False) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

                def has_application_schema(sync_connection: object) -> bool:
                    inspector = cast(Inspector, inspect(sync_connection))
                    table_names = set(inspector.get_table_names())
                    return set(Base.metadata.tables).issubset(table_names)

                if not await connection.run_sync(has_application_schema):
                    return False
                if require_current_schema:
                    result = await connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    )
                    revisions = {str(value) for value in result.scalars().all()}
                    if revisions != {CURRENT_DATABASE_REVISION}:
                        return False
            return True
        except Exception:
            return False

    async def dispose(self) -> None:
        await self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(
        dbapi_connection: DBAPIConnection,
        _connection_record: object,
    ) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


class SqlAlchemyTransactionManager:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
