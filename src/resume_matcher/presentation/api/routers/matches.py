from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from resume_matcher.application.services.match_service import ExportService, MatchService
from resume_matcher.presentation.api.dependencies import (
    enforce_rate_limit,
    get_export_service,
    get_match_service,
    require_api_key,
)
from resume_matcher.presentation.api.mappers import match_response
from resume_matcher.presentation.api.schemas import MatchCreateRequest, MatchResponse

router = APIRouter(
    prefix="/matches",
    tags=["matches"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "",
    response_model=MatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute an explainable match",
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_match(
    payload: MatchCreateRequest,
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchResponse:
    analysis = await service.create(resume_id=payload.resume_id, job_id=payload.job_id)
    return match_response(analysis)


@router.get("/{match_id}", response_model=MatchResponse, summary="Get a match analysis")
async def get_match(
    match_id: UUID,
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchResponse:
    return match_response(await service.get(match_id))


@router.post(
    "/{match_id}/optimize",
    response_model=MatchResponse,
    summary="Generate a fact-guarded optimized resume",
    dependencies=[Depends(enforce_rate_limit)],
)
async def optimize_match(
    match_id: UUID,
    service: Annotated[MatchService, Depends(get_match_service)],
) -> MatchResponse:
    return match_response(await service.optimize(match_id))


@router.get(
    "/{match_id}/exports/{format_name}",
    summary="Export JSON analysis or a DOCX/PDF resume",
    response_class=Response,
)
async def export_match(
    match_id: UUID,
    format_name: Literal["json", "docx", "pdf"],
    service: Annotated[ExportService, Depends(get_export_service)],
) -> Response:
    artifact = await service.export(match_id, format_name)
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
