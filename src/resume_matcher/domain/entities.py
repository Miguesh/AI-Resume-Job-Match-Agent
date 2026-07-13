"""Domain entities and value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


class EducationLevel(StrEnum):
    NONE = "none"
    HIGH_SCHOOL = "high_school"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    DOCTORATE = "doctorate"


class RecommendationPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    normalized_name: str


@dataclass(frozen=True, slots=True)
class Experience:
    title: str
    company: str
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    bullets: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Education:
    institution: str
    degree: str
    field: str | None = None
    graduation_year: int | None = None
    level: EducationLevel = EducationLevel.NONE


@dataclass(frozen=True, slots=True)
class ResumeProfile:
    name: str | None
    headline: str | None
    summary: str | None
    email: str | None
    phone: str | None
    location: str | None
    skills: tuple[Skill, ...]
    experiences: tuple[Experience, ...]
    education: tuple[Education, ...]
    certifications: tuple[str, ...]
    total_years_experience: float
    keywords: tuple[str, ...]
    raw_text: str


@dataclass(frozen=True, slots=True)
class JobProfile:
    title: str
    company: str | None
    summary: str | None
    required_skills: tuple[Skill, ...]
    preferred_skills: tuple[Skill, ...]
    responsibilities: tuple[str, ...]
    education_level: EducationLevel
    minimum_years_experience: float
    keywords: tuple[str, ...]
    raw_text: str


@dataclass(frozen=True, slots=True)
class ScoreDimension:
    name: str
    weight: float
    raw_score: float
    weighted_score: float
    matched: tuple[str, ...]
    missing: tuple[str, ...]
    explanation: str


@dataclass(frozen=True, slots=True)
class Recommendation:
    category: str
    priority: RecommendationPriority
    title: str
    guidance: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MatchResult:
    overall_score: float
    dimensions: tuple[ScoreDimension, ...]
    matched_skills: tuple[str, ...]
    missing_required_skills: tuple[str, ...]
    missing_preferred_skills: tuple[str, ...]
    matched_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    recommendations: tuple[Recommendation, ...]
    explanation: str
    score_version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class OptimizationChange:
    section: str
    before: str | None
    after: str
    reason: str
    source_evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OptimizedResume:
    name: str | None
    headline: str | None
    summary: str | None
    email: str | None
    phone: str | None
    location: str | None
    skills: tuple[Skill, ...]
    experiences: tuple[Experience, ...]
    education: tuple[Education, ...]
    certifications: tuple[str, ...]
    changes: tuple[OptimizationChange, ...]
    warnings: tuple[str, ...] = ("Review every generated statement before submitting the resume.",)


@dataclass(frozen=True, slots=True)
class ResumeDocument:
    filename: str
    content_type: str
    sha256: str
    profile: ResumeProfile
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class JobDescription:
    profile: JobProfile
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class MatchAnalysis:
    resume_id: UUID
    job_id: UUID
    result: MatchResult
    optimized_resume: OptimizedResume | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
