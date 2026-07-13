from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from resume_matcher.app import create_app
from resume_matcher.config.settings import AppEnvironment, Settings


@pytest.mark.integration
async def test_invalid_upload_returns_rfc_problem_details(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/resumes",
        files={"file": ("resume.pdf", b"not-a-pdf", "application/pdf")},
    )
    assert response.status_code == 400
    problem = response.json()
    assert problem["type"].startswith("urn:resume-matcher:error:")
    assert problem["status"] == 400
    assert problem["code"] == "invalid_document"
    assert problem["request_id"] == response.headers["x-request-id"]
    assert "not-a-pdf" not in response.text


@pytest.mark.integration
async def test_unknown_resources_do_not_expose_internal_errors(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/api/v1/resumes/00000000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert response.json()["code"] == "entity_not_found"


@pytest.mark.integration
async def test_api_key_is_required_when_configured(tmp_path: Path) -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        app_api_keys=("portfolio-test-key",),
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}",
        storage_path=tmp_path / "uploads",
        app_allowed_hosts=("testserver",),
        log_json=False,
    )
    app: FastAPI = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            denied = await client.get("/api/v1/resumes/00000000-0000-4000-8000-000000000000")
            assert denied.status_code == 401
            assert denied.headers["www-authenticate"] == "Bearer"

            allowed = await client.get(
                "/api/v1/resumes/00000000-0000-4000-8000-000000000000",
                headers={"Authorization": "Bearer portfolio-test-key"},
            )
            assert allowed.status_code == 404


@pytest.mark.integration
async def test_untrusted_host_is_rejected(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(
        "/api/v1/health/live",
        headers={"host": "attacker.example"},
    )
    assert response.status_code == 400


@pytest.mark.integration
async def test_chunked_request_body_cannot_bypass_size_limit(tmp_path: Path) -> None:
    settings = Settings(
        app_env=AppEnvironment.TEST,
        app_max_upload_bytes=1024,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'body-limit.db'}",
        storage_path=tmp_path / "uploads",
        app_allowed_hosts=("testserver",),
        log_json=False,
    )
    app = create_app(settings)

    async def oversized_body() -> AsyncIterator[bytes]:
        yield b'{"job_description":"'
        yield b"x" * (1024 * 1024 + 2048)
        yield b'"}'

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/jobs",
                content=oversized_body(),
                headers={"Content-Type": "application/json"},
            )

    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"
    assert response.json()["request_id"] == response.headers["x-request-id"]
