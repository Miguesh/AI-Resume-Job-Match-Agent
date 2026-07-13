from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from resume_matcher.container import AppContainer
from resume_matcher.presentation.api.dependencies import get_container
from resume_matcher.presentation.api.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse, summary="Liveness probe")
async def liveness(
    container: Annotated[AppContainer, Depends(get_container)],
) -> HealthResponse:
    return HealthResponse(status="ok", version=container.settings.app_version)


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def readiness(
    response: Response,
    container: Annotated[AppContainer, Depends(get_container)],
) -> HealthResponse:
    database_ready = await container.database.healthcheck()
    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ready else "degraded",
        version=container.settings.app_version,
        checks={
            "database": "ok" if database_ready else "unavailable",
            "ai_provider": container.settings.ai_provider.value,
        },
    )
