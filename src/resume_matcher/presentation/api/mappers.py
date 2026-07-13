from __future__ import annotations

from resume_matcher.domain.entities import JobDescription, MatchAnalysis, ResumeDocument
from resume_matcher.presentation.api.schemas import (
    JobResponse,
    MatchResponse,
    ResumeResponse,
)


def resume_response(document: ResumeDocument, warnings: tuple[str, ...] = ()) -> ResumeResponse:
    return ResumeResponse(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        sha256=document.sha256,
        profile=document.profile,
        created_at=document.created_at,
        warnings=warnings,
    )


def job_response(job: JobDescription) -> JobResponse:
    return JobResponse.model_validate(job)


def match_response(match: MatchAnalysis) -> MatchResponse:
    return MatchResponse.model_validate(match)
