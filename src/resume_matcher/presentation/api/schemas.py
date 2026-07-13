from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from resume_matcher.domain.entities import (
    EducationLevel,
    RecommendationPriority,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class SkillResponse(ApiModel):
    name: str
    normalized_name: str


class ExperienceResponse(ApiModel):
    title: str
    company: str
    start_date: str | None
    end_date: str | None
    location: str | None
    bullets: tuple[str, ...]
    skills: tuple[str, ...]


class EducationResponse(ApiModel):
    institution: str
    degree: str
    field: str | None
    graduation_year: int | None
    level: EducationLevel


class ResumeProfileResponse(ApiModel):
    name: str | None
    headline: str | None
    summary: str | None
    email: str | None
    phone: str | None
    location: str | None
    skills: tuple[SkillResponse, ...]
    experiences: tuple[ExperienceResponse, ...]
    education: tuple[EducationResponse, ...]
    certifications: tuple[str, ...]
    total_years_experience: float
    keywords: tuple[str, ...]


class ResumeResponse(ApiModel):
    id: UUID
    filename: str
    content_type: str
    sha256: str
    profile: ResumeProfileResponse
    created_at: datetime
    warnings: tuple[str, ...] = ()


class JobCreateRequest(ApiModel):
    job_description: str = Field(
        min_length=100,
        max_length=200_000,
        examples=["Senior AI Engineer\nRequired: Python, FastAPI, Docker, 5+ years experience..."],
    )


class JobProfileResponse(ApiModel):
    title: str
    company: str | None
    summary: str | None
    required_skills: tuple[SkillResponse, ...]
    preferred_skills: tuple[SkillResponse, ...]
    responsibilities: tuple[str, ...]
    education_level: EducationLevel
    minimum_years_experience: float
    keywords: tuple[str, ...]


class JobResponse(ApiModel):
    id: UUID
    profile: JobProfileResponse
    created_at: datetime


class MatchCreateRequest(ApiModel):
    resume_id: UUID
    job_id: UUID


class ScoreDimensionResponse(ApiModel):
    name: str
    weight: float
    raw_score: float
    weighted_score: float
    matched: tuple[str, ...]
    missing: tuple[str, ...]
    explanation: str


class RecommendationResponse(ApiModel):
    category: str
    priority: RecommendationPriority
    title: str
    guidance: str
    evidence: tuple[str, ...]


class MatchResultResponse(ApiModel):
    overall_score: float
    dimensions: tuple[ScoreDimensionResponse, ...]
    matched_skills: tuple[str, ...]
    missing_required_skills: tuple[str, ...]
    missing_preferred_skills: tuple[str, ...]
    matched_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    recommendations: tuple[RecommendationResponse, ...]
    explanation: str
    score_version: str


class OptimizationChangeResponse(ApiModel):
    section: str
    before: str | None
    after: str
    reason: str
    source_evidence: tuple[str, ...]


class OptimizedResumeResponse(ApiModel):
    name: str | None
    headline: str | None
    summary: str | None
    email: str | None
    phone: str | None
    location: str | None
    skills: tuple[SkillResponse, ...]
    experiences: tuple[ExperienceResponse, ...]
    education: tuple[EducationResponse, ...]
    certifications: tuple[str, ...]
    changes: tuple[OptimizationChangeResponse, ...]
    warnings: tuple[str, ...]


class MatchResponse(ApiModel):
    id: UUID
    resume_id: UUID
    job_id: UUID
    result: MatchResultResponse
    optimized_resume: OptimizedResumeResponse | None
    created_at: datetime
    updated_at: datetime


class DeleteResponse(ApiModel):
    deleted: bool


class HealthResponse(ApiModel):
    status: str
    version: str
    checks: dict[str, str] = Field(default_factory=dict)


class ProblemDetails(ApiModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str | None = None
    errors: list[dict[str, object]] | None = None
