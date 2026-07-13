from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from resume_matcher.domain.entities import EducationLevel


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExperienceContract(StrictContract):
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    start_date: str | None = Field(default=None, max_length=50)
    end_date: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=200)
    bullets: list[str] = Field(default_factory=list, max_length=30)
    skills: list[str] = Field(default_factory=list, max_length=100)


class EducationContract(StrictContract):
    institution: str = Field(min_length=1, max_length=250)
    degree: str = Field(min_length=1, max_length=250)
    field: str | None = Field(default=None, max_length=200)
    graduation_year: int | None = Field(default=None, ge=1900, le=2100)
    level: EducationLevel = EducationLevel.NONE


class ResumeExtractionContract(StrictContract):
    name: str | None = Field(default=None, max_length=200)
    headline: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=3000)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=250)
    skills: list[str] = Field(default_factory=list, max_length=250)
    experiences: list[ExperienceContract] = Field(default_factory=list, max_length=50)
    education: list[EducationContract] = Field(default_factory=list, max_length=20)
    certifications: list[str] = Field(default_factory=list, max_length=100)
    total_years_experience: float = Field(default=0, ge=0, le=80)
    keywords: list[str] = Field(default_factory=list, max_length=100)


class JobExtractionContract(StrictContract):
    title: str = Field(min_length=1, max_length=250)
    company: str | None = Field(default=None, max_length=250)
    summary: str | None = Field(default=None, max_length=3000)
    required_skills: list[str] = Field(default_factory=list, max_length=250)
    preferred_skills: list[str] = Field(default_factory=list, max_length=250)
    responsibilities: list[str] = Field(default_factory=list, max_length=100)
    education_level: EducationLevel = EducationLevel.NONE
    minimum_years_experience: float = Field(default=0, ge=0, le=80)
    keywords: list[str] = Field(default_factory=list, max_length=100)


class OptimizationChangeContract(StrictContract):
    section: str = Field(min_length=1, max_length=100)
    before: str | None = Field(default=None, max_length=5000)
    after: str = Field(min_length=1, max_length=5000)
    reason: str = Field(min_length=1, max_length=1000)
    source_evidence: list[str] = Field(default_factory=list, max_length=20)


class OptimizedResumeContract(StrictContract):
    name: str | None = Field(default=None, max_length=200)
    headline: str | None = Field(default=None, max_length=300)
    summary: str | None = Field(default=None, max_length=3000)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=250)
    skills: list[str] = Field(default_factory=list, max_length=250)
    experiences: list[ExperienceContract] = Field(default_factory=list, max_length=50)
    education: list[EducationContract] = Field(default_factory=list, max_length=20)
    certifications: list[str] = Field(default_factory=list, max_length=100)
    changes: list[OptimizationChangeContract] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=20)
