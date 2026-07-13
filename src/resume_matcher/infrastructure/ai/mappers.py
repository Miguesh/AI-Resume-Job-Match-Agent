from __future__ import annotations

from resume_matcher.domain.entities import (
    Education,
    Experience,
    JobProfile,
    OptimizationChange,
    OptimizedResume,
    ResumeProfile,
)
from resume_matcher.domain.skill_normalizer import deduplicate_skills
from resume_matcher.infrastructure.ai.contracts import (
    EducationContract,
    ExperienceContract,
    JobExtractionContract,
    OptimizedResumeContract,
    ResumeExtractionContract,
)


def _experience(value: ExperienceContract) -> Experience:
    return Experience(
        title=value.title,
        company=value.company,
        start_date=value.start_date,
        end_date=value.end_date,
        location=value.location,
        bullets=tuple(value.bullets),
        skills=tuple(skill.name for skill in deduplicate_skills(value.skills)),
    )


def _education(value: EducationContract) -> Education:
    return Education(
        institution=value.institution,
        degree=value.degree,
        field=value.field,
        graduation_year=value.graduation_year,
        level=value.level,
    )


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


def resume_from_contract(value: ResumeExtractionContract, raw_text: str) -> ResumeProfile:
    return ResumeProfile(
        name=value.name,
        headline=value.headline,
        summary=value.summary,
        email=value.email,
        phone=value.phone,
        location=value.location,
        skills=deduplicate_skills(value.skills),
        experiences=tuple(_experience(item) for item in value.experiences),
        education=tuple(_education(item) for item in value.education),
        certifications=_unique(value.certifications),
        total_years_experience=value.total_years_experience,
        keywords=_unique(value.keywords),
        raw_text=raw_text,
    )


def job_from_contract(value: JobExtractionContract, raw_text: str) -> JobProfile:
    required = deduplicate_skills(value.required_skills)
    required_names = {skill.normalized_name for skill in required}
    preferred = tuple(
        skill
        for skill in deduplicate_skills(value.preferred_skills)
        if skill.normalized_name not in required_names
    )
    return JobProfile(
        title=value.title,
        company=value.company,
        summary=value.summary,
        required_skills=required,
        preferred_skills=preferred,
        responsibilities=_unique(value.responsibilities),
        education_level=value.education_level,
        minimum_years_experience=value.minimum_years_experience,
        keywords=_unique(value.keywords),
        raw_text=raw_text,
    )


def optimized_from_contract(value: OptimizedResumeContract) -> OptimizedResume:
    return OptimizedResume(
        name=value.name,
        headline=value.headline,
        summary=value.summary,
        email=value.email,
        phone=value.phone,
        location=value.location,
        skills=deduplicate_skills(value.skills),
        experiences=tuple(_experience(item) for item in value.experiences),
        education=tuple(_education(item) for item in value.education),
        certifications=_unique(value.certifications),
        changes=tuple(
            OptimizationChange(
                section=item.section,
                before=item.before,
                after=item.after,
                reason=item.reason,
                source_evidence=tuple(item.source_evidence),
            )
            for item in value.changes
        ),
        warnings=_unique(value.warnings)
        or ("Review every generated statement before submitting the resume.",),
    )
