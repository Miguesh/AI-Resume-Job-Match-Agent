from __future__ import annotations

import hashlib
import hmac
from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from resume_matcher.application.services.job_service import JobService
from resume_matcher.application.services.match_service import ExportService, MatchService
from resume_matcher.application.services.resume_service import ResumeService
from resume_matcher.container import AppContainer

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="Application API key")


def get_container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


async def get_session(
    container: Annotated[AppContainer, Depends(get_container)],
) -> AsyncIterator[AsyncSession]:
    async with container.database.session_factory() as session:
        yield session


async def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> None:
    configured = container.settings.app_api_keys
    if not configured:
        return
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer API key is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    provided = hashlib.sha256(credentials.credentials.encode()).digest()
    if not any(
        hmac.compare_digest(provided, hashlib.sha256(value.encode()).digest())
        for value in configured
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer API key is required",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def enforce_rate_limit(
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> None:
    client = request.client.host if request.client else "unknown"
    allowed, retry_after = await container.rate_limiter.check(client)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded; retry later",
            headers={"Retry-After": str(retry_after)},
        )


def get_resume_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> ResumeService:
    return container.resume_service(session)


def get_job_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> JobService:
    return container.job_service(session)


def get_match_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> MatchService:
    return container.match_service(session)


def get_export_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> ExportService:
    return container.export_service(session)
