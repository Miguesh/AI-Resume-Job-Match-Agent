from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from resume_matcher.application.services.resume_service import ResumeService
from resume_matcher.container import AppContainer
from resume_matcher.domain.exceptions import DocumentTooLargeError
from resume_matcher.presentation.api.dependencies import (
    enforce_rate_limit,
    get_container,
    get_resume_service,
    require_api_key,
)
from resume_matcher.presentation.api.mappers import resume_response
from resume_matcher.presentation.api.schemas import DeleteResponse, ResumeResponse

router = APIRouter(
    prefix="/resumes",
    tags=["resumes"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and extract a resume",
    dependencies=[Depends(enforce_rate_limit)],
)
async def upload_resume(
    file: Annotated[
        UploadFile,
        File(description="PDF or DOCX resume; maximum size is configured by APP_MAX_UPLOAD_BYTES"),
    ],
    service: Annotated[ResumeService, Depends(get_resume_service)],
    container: Annotated[AppContainer, Depends(get_container)],
) -> ResumeResponse:
    content = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            content.extend(chunk)
            if len(content) > container.settings.app_max_upload_bytes:
                raise DocumentTooLargeError(
                    "The uploaded file exceeds the "
                    f"{container.settings.app_max_upload_bytes}-byte limit"
                )
    finally:
        await file.close()
    document, warnings = await service.upload(
        filename=file.filename or "resume",
        content_type=file.content_type,
        content=bytes(content),
    )
    return resume_response(document, warnings)


@router.get("/{resume_id}", response_model=ResumeResponse, summary="Get extracted resume data")
async def get_resume(
    resume_id: UUID,
    service: Annotated[ResumeService, Depends(get_resume_service)],
) -> ResumeResponse:
    return resume_response(await service.get(resume_id))


@router.delete(
    "/{resume_id}", response_model=DeleteResponse, summary="Delete a resume and its file"
)
async def delete_resume(
    resume_id: UUID,
    service: Annotated[ResumeService, Depends(get_resume_service)],
) -> DeleteResponse:
    await service.delete(resume_id)
    return DeleteResponse(deleted=True)
