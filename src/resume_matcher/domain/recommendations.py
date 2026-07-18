"""Evidence-grounded improvement recommendations."""

from __future__ import annotations

from resume_matcher.domain.entities import (
    EducationLevel,
    JobProfile,
    Recommendation,
    RecommendationPriority,
    ResumeProfile,
)


class RecommendationService:
    def build(
        self,
        *,
        resume: ResumeProfile,
        job: JobProfile,
        missing_required: tuple[str, ...],
        missing_preferred: tuple[str, ...],
        missing_keywords: tuple[str, ...],
        experience_score: float,
        education_score: float,
    ) -> tuple[Recommendation, ...]:
        has_explicit_criteria = bool(
            job.required_skills
            or job.preferred_skills
            or job.minimum_years_experience > 0
            or job.keywords
            or job.education_level is not EducationLevel.NONE
            or job.responsibilities
        )
        if not has_explicit_criteria:
            return (
                Recommendation(
                    category="input_quality",
                    priority=RecommendationPriority.HIGH,
                    title="Provide a more complete job description",
                    guidance=(
                        "No explicit skills, experience, keywords, education, or responsibilities "
                        "were extracted. Add the complete role requirements before interpreting "
                        "the match score."
                    ),
                ),
            )

        items: list[Recommendation] = []
        if missing_required:
            items.append(
                Recommendation(
                    category="skills",
                    priority=RecommendationPriority.HIGH,
                    title="Address required-skill evidence",
                    guidance=(
                        "For each missing required skill, add a concrete achievement only if the "
                        "experience is true. Otherwise, treat it as a learning gap and never "
                        "claim it."
                    ),
                    evidence=missing_required,
                )
            )
        if experience_score < 100:
            items.append(
                Recommendation(
                    category="experience",
                    priority=RecommendationPriority.HIGH,
                    title="Clarify relevant experience depth",
                    guidance=(
                        f"The job asks for {job.minimum_years_experience:g} years while the resume "
                        f"supports {resume.total_years_experience:g}. Make dates, scope, and "
                        "directly "
                        "relevant achievements explicit; do not inflate tenure."
                    ),
                )
            )
        if education_score < 100:
            items.append(
                Recommendation(
                    category="education",
                    priority=RecommendationPriority.MEDIUM,
                    title="Clarify education or equivalent experience",
                    guidance=(
                        f"The extracted requirement is {job.education_level.value}. Add accurate "
                        "degree details, certifications, or equivalent experience when applicable."
                    ),
                )
            )
        if missing_preferred:
            items.append(
                Recommendation(
                    category="skills",
                    priority=RecommendationPriority.MEDIUM,
                    title="Surface preferred qualifications",
                    guidance="Add these only where the resume can support them with real evidence.",
                    evidence=missing_preferred,
                )
            )
        if missing_keywords:
            items.append(
                Recommendation(
                    category="keywords",
                    priority=RecommendationPriority.LOW,
                    title="Use the employer's terminology naturally",
                    guidance=(
                        "Where accurate, align wording with the job description inside achievement "
                        "bullets. Avoid keyword stuffing or hidden text."
                    ),
                    evidence=missing_keywords[:10],
                )
            )
        if not items:
            items.append(
                Recommendation(
                    category="presentation",
                    priority=RecommendationPriority.LOW,
                    title="Strengthen measurable outcomes",
                    guidance=(
                        "The structured criteria align well. Improve readability by leading "
                        "bullets with actions and quantifying outcomes already supported by your "
                        "experience."
                    ),
                )
            )
        return tuple(items)
