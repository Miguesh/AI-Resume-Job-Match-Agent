from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from resume_matcher.app import create_app
from resume_matcher.config.settings import AppEnvironment, Settings
from resume_matcher.infrastructure.persistence.database import (
    CURRENT_DATABASE_REVISION,
    Database,
)


@pytest.mark.integration
async def test_database_healthcheck_requires_application_tables(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'empty.db'}")
    try:
        assert await database.healthcheck() is False

        await database.create_schema()
        assert await database.healthcheck() is True
    finally:
        await database.dispose()


@pytest.mark.integration
async def test_database_healthcheck_can_require_current_migration(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'revision.db'}")
    try:
        await database.create_schema()
        assert await database.healthcheck(require_current_schema=True) is False

        async with database.engine.begin() as connection:
            await connection.execute(
                text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
            )
            await connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": CURRENT_DATABASE_REVISION},
            )

        assert await database.healthcheck(require_current_schema=True) is True

        async with database.engine.begin() as connection:
            await connection.execute(
                text("UPDATE alembic_version SET version_num = 'outdated_revision'")
            )

        assert await database.healthcheck(require_current_schema=True) is False
    finally:
        await database.dispose()


def test_runtime_schema_revision_matches_alembic_head() -> None:
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    assert script.get_heads() == [CURRENT_DATABASE_REVISION]


@pytest.mark.integration
async def test_readiness_is_degraded_when_migrations_are_missing(tmp_path: Path) -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        database_auto_create_schema=False,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'not-migrated.db'}",
        storage_path=tmp_path / "uploads",
        app_allowed_hosts=("testserver",),
        log_json=False,
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["database"] == "unavailable"
