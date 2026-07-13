from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from resume_matcher.application.services.job_service import JobService
from resume_matcher.container import AppContainer
from resume_matcher.presentation.api.dependencies import (
    enforce_rate_limit,
    get_container,
    get_job_service,
    require_api_key,
)
from resume_matcher.presentation.api.mappers import job_response
from resume_matcher.presentation.api.schemas import JobCreateRequest, JobResponse

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Extract a job description",
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_job(
    payload: JobCreateRequest,
    service: Annotated[JobService, Depends(get_job_service)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> JobResponse:
    if len(payload.job_description) > container.settings.app_max_job_description_chars:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Job description exceeds the configured character limit",
        )
    return job_response(await service.create(payload.job_description))


@router.get("/{job_id}", response_model=JobResponse, summary="Get extracted job data")
async def get_job(
    job_id: UUID,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    return job_response(await service.get(job_id))
