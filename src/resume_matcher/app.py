from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from resume_matcher.config.settings import Settings
from resume_matcher.container import AppContainer
from resume_matcher.infrastructure.logging import configure_logging
from resume_matcher.presentation.api.errors import install_exception_handlers
from resume_matcher.presentation.api.middleware import (
    ContentLengthLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from resume_matcher.presentation.api.routers import health, jobs, matches, resumes

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()
    configure_logging(level=resolved.log_level, json_output=resolved.log_json)
    container = AppContainer.build(resolved)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if resolved.database_auto_create_schema:
            await container.database.create_schema()
        logger.info(
            "Application started",
            extra={"event": "application_started", "environment": resolved.app_env.value},
        )
        try:
            yield
        finally:
            await container.database.dispose()
            logger.info("Application stopped", extra={"event": "application_stopped"})

    app = FastAPI(
        title=resolved.app_name,
        version=resolved.app_version,
        summary="Explainable, fact-guarded resume optimization for a target job",
        description=(
            "Upload a PDF or DOCX resume, extract structured evidence, compare it with a job "
            "description using deterministic scoring, generate recommendations, and export an "
            "optimized draft. LLMs never assign the numeric match score."
        ),
        debug=resolved.app_debug,
        docs_url="/docs" if resolved.docs_enabled else None,
        redoc_url="/redoc" if resolved.docs_enabled else None,
        openapi_url="/openapi.json" if resolved.docs_enabled else None,
        lifespan=lifespan,
        contact={
            "name": "Miguel Angel Sierra Hayer",
            "url": "https://github.com/Miguesh/AI-Resume-Job-Match-Agent",
        },
        license_info={"name": "MIT", "identifier": "MIT"},
    )
    app.state.container = container

    app.add_middleware(
        ContentLengthLimitMiddleware,
        max_bytes=resolved.app_max_upload_bytes + 1024 * 1024,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    if resolved.app_allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=list(resolved.app_allowed_hosts),
        )
    if resolved.app_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved.app_cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
            expose_headers=["Content-Disposition", "X-Request-ID"],
            max_age=600,
        )

    install_exception_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(resumes.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(matches.router, prefix="/api/v1")
    return app
