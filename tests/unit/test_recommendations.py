from __future__ import annotations

from collections.abc import Callable

from resume_matcher.domain.entities import (
    EducationLevel,
    JobProfile,
    RecommendationPriority,
    ResumeProfile,
)
from resume_matcher.domain.recommendations import RecommendationService


def test_recommendations_are_prioritized_and_grounded_in_supplied_gaps(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
) -> None:
    missing_keywords = tuple(f"keyword-{index}" for index in range(12))

    recommendations = RecommendationService().build(
        resume=resume_factory(),
        job=job_factory(),
        missing_required=("Docker", "Kubernetes"),
        missing_preferred=("AWS",),
        missing_keywords=missing_keywords,
        experience_score=60,
        education_score=75,
    )

    assert [(item.category, item.priority) for item in recommendations] == [
        ("skills", RecommendationPriority.HIGH),
        ("experience", RecommendationPriority.HIGH),
        ("education", RecommendationPriority.MEDIUM),
        ("skills", RecommendationPriority.MEDIUM),
        ("keywords", RecommendationPriority.LOW),
    ]
    assert recommendations[0].evidence == ("Docker", "Kubernetes")
    assert recommendations[3].evidence == ("AWS",)
    assert recommendations[4].evidence == missing_keywords[:10]
    assert "never claim it" in recommendations[0].guidance
    assert "do not inflate tenure" in recommendations[1].guidance
    assert "Avoid keyword stuffing" in recommendations[4].guidance


def test_recommendations_only_include_dimensions_with_real_gaps(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
) -> None:
    recommendations = RecommendationService().build(
        resume=resume_factory(),
        job=job_factory(),
        missing_required=(),
        missing_preferred=("AWS",),
        missing_keywords=(),
        experience_score=100,
        education_score=100,
    )

    assert len(recommendations) == 1
    assert recommendations[0].title == "Surface preferred qualifications"
    assert recommendations[0].evidence == ("AWS",)


def test_recommendations_use_presentation_fallback_when_all_criteria_align(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
) -> None:
    recommendations = RecommendationService().build(
        resume=resume_factory(),
        job=job_factory(),
        missing_required=(),
        missing_preferred=(),
        missing_keywords=(),
        experience_score=100,
        education_score=100,
    )

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation.category == "presentation"
    assert recommendation.priority is RecommendationPriority.LOW
    assert "quantifying outcomes already supported" in recommendation.guidance


def test_recommendations_request_better_input_when_job_has_no_explicit_criteria(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
) -> None:
    job = job_factory(
        required_skills=(),
        preferred_skills=(),
        responsibilities=(),
        education_level=EducationLevel.NONE,
        minimum_years_experience=0,
        keywords=(),
    )

    recommendations = RecommendationService().build(
        resume=resume_factory(),
        job=job,
        missing_required=(),
        missing_preferred=(),
        missing_keywords=(),
        experience_score=100,
        education_score=100,
    )

    assert len(recommendations) == 1
    recommendation = recommendations[0]
    assert recommendation.category == "input_quality"
    assert recommendation.priority is RecommendationPriority.HIGH
    assert "complete role requirements" in recommendation.guidance
