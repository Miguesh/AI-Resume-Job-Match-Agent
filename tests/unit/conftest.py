from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest

from resume_matcher.domain.entities import (
    Education,
    EducationLevel,
    Experience,
    JobProfile,
    MatchAnalysis,
    OptimizationChange,
    OptimizedResume,
    ResumeProfile,
)
from resume_matcher.domain.matching import MatchingService
from resume_matcher.domain.skill_normalizer import create_skill


@pytest.fixture
def resume_factory() -> Callable[..., ResumeProfile]:
    def build(**overrides: object) -> ResumeProfile:
        values: dict[str, object] = {
            "name": "Jane Doe",
            "headline": "Senior Platform Engineer",
            "summary": "Build reliable APIs and lead platform delivery",
            "email": "jane@example.com",
            "phone": "+1 212 555 0199",
            "location": "New York, NY",
            "skills": tuple(create_skill(value) for value in ("Python", "FastAPI", "Postgres")),
            "experiences": (
                Experience(
                    title="Senior Engineer",
                    company="Acme",
                    start_date="2021",
                    end_date="Present",
                    location="New York, NY",
                    bullets=(
                        "Built reliable Python APIs for the platform.",
                        "Reduced processing latency by 35 percent.",
                    ),
                    skills=("Python", "FastAPI"),
                ),
            ),
            "education": (
                Education(
                    institution="State University",
                    degree="Bachelor of Science",
                    field="Computer Science",
                    graduation_year=2020,
                    level=EducationLevel.BACHELOR,
                ),
            ),
            "certifications": ("AWS Certified Cloud Practitioner",),
            "total_years_experience": 3.0,
            "keywords": ("leadership",),
            "raw_text": (
                "Jane Doe\nBuild reliable APIs and lead platform delivery\n"
                "Skills: Python, FastAPI, PostgreSQL\n"
                "Senior Engineer at Acme\nBuilt reliable Python APIs for the platform.\n"
                "Reduced processing latency by 35 percent.\n"
                "Bachelor of Science, State University"
            ),
        }
        values.update(overrides)
        return ResumeProfile(**values)  # type: ignore[arg-type]

    return build


@pytest.fixture
def job_factory() -> Callable[..., JobProfile]:
    def build(**overrides: object) -> JobProfile:
        values: dict[str, object] = {
            "title": "Senior API Engineer",
            "company": "Example Corp",
            "summary": "Build the next generation platform.",
            "required_skills": tuple(create_skill(value) for value in ("Python", "Docker")),
            "preferred_skills": tuple(create_skill(value) for value in ("FastAPI", "AWS")),
            "responsibilities": ("Build reliable APIs and lead platform delivery",),
            "education_level": EducationLevel.MASTER,
            "minimum_years_experience": 5.0,
            "keywords": ("Python", "leadership", "Docker"),
            "raw_text": "Senior API Engineer requiring Python, Docker, and five years.",
        }
        values.update(overrides)
        return JobProfile(**values)  # type: ignore[arg-type]

    return build


@pytest.fixture
def match_analysis(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
) -> MatchAnalysis:
    resume = resume_factory()
    job = job_factory()
    return MatchAnalysis(
        resume_id=uuid4(),
        job_id=uuid4(),
        result=MatchingService().score(resume, job),
    )


@pytest.fixture
def optimized_resume(resume_factory: Callable[..., ResumeProfile]) -> OptimizedResume:
    resume = resume_factory()
    return OptimizedResume(
        name=resume.name,
        headline=resume.headline,
        summary="Platform engineer focused on reliable APIs.",
        email=resume.email,
        phone=resume.phone,
        location=resume.location,
        skills=resume.skills,
        experiences=resume.experiences,
        education=resume.education,
        certifications=resume.certifications,
        changes=(
            OptimizationChange(
                section="summary",
                before=resume.summary,
                after="Platform engineer focused on reliable APIs.",
                reason="Improves focus.",
                source_evidence=("Build reliable APIs",),
            ),
        ),
        warnings=("Review every statement.",),
    )
