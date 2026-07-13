from __future__ import annotations

import math
from collections.abc import Callable

import pytest

from resume_matcher.domain.entities import Education, EducationLevel, JobProfile, ResumeProfile
from resume_matcher.domain.matching import MatchingService, ScoringWeights
from resume_matcher.domain.skill_normalizer import create_skill


def test_default_score_has_exact_explainable_contributions(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
) -> None:
    result = MatchingService().score(resume_factory(), job_factory())
    dimensions = {dimension.name: dimension for dimension in result.dimensions}

    assert result.overall_score == 60.0
    assert result.score_version == "1.0.0"
    assert dimensions["skills"].raw_score == 50.0
    assert dimensions["skills"].weighted_score == 22.5
    assert dimensions["skills"].matched == ("Python", "FastAPI")
    assert dimensions["skills"].missing == ("Docker", "AWS")
    assert dimensions["experience"].raw_score == 60.0
    assert dimensions["experience"].weighted_score == 15.0
    assert dimensions["keywords"].raw_score == 66.67
    assert dimensions["keywords"].weighted_score == 10.0
    assert dimensions["education"].raw_score == 75.0
    assert dimensions["education"].weighted_score == 7.5
    assert dimensions["responsibilities"].raw_score == 100.0
    assert dimensions["responsibilities"].weighted_score == 5.0
    assert result.matched_skills == ("FastAPI", "Python")
    assert result.missing_required_skills == ("Docker",)
    assert result.missing_preferred_skills == ("AWS",)
    assert result.matched_keywords == ("Python", "leadership")
    assert result.missing_keywords == ("Docker",)
    assert "strongest dimension is responsibilities (100.0%)" in result.explanation
    assert "skills (50.0%) has the largest improvement opportunity" in result.explanation


def test_scoring_is_deterministic_and_does_not_mutate_inputs(
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
) -> None:
    resume = resume_factory()
    job = job_factory()
    service = MatchingService()

    first = service.score(resume, job)
    second = service.score(resume, job)

    assert first == second
    assert resume == resume_factory()
    assert job == job_factory()


@pytest.mark.parametrize(
    ("required", "preferred", "resume_skills", "expected"),
    [
        ((), (), (), 100.0),
        (("Python",), (), (), 0.0),
        (("Python",), (), ("Python",), 100.0),
        ((), ("AWS", "Python"), ("Python",), 50.0),
        (("Python",), ("AWS",), ("Python",), 80.0),
        (("Python",), ("AWS",), ("AWS",), 20.0),
    ],
)
def test_required_and_preferred_skill_weighting_branches(
    required: tuple[str, ...],
    preferred: tuple[str, ...],
    resume_skills: tuple[str, ...],
    expected: float,
    resume_factory: Callable[..., ResumeProfile],
    job_factory: Callable[..., JobProfile],
) -> None:
    resume = resume_factory(skills=tuple(create_skill(value) for value in resume_skills))
    job = job_factory(
        required_skills=tuple(create_skill(value) for value in required),
        preferred_skills=tuple(create_skill(value) for value in preferred),
    )
    service = MatchingService(
        ScoringWeights(skills=1, experience=0, keywords=0, education=0, responsibilities=0)
    )

    result = service.score(resume, job)

    assert result.overall_score == expected


@pytest.mark.parametrize(
    ("actual", "required", "expected"),
    [(-3.0, 5.0, 0.0), (0.0, 0.0, 100.0), (2.5, 5.0, 50.0), (8.0, 5.0, 100.0)],
)
def test_experience_score_is_bounded(actual: float, required: float, expected: float) -> None:
    assert MatchingService._experience_score(actual, required) == expected


@pytest.mark.parametrize(
    ("attained", "required", "expected"),
    [
        (EducationLevel.NONE, EducationLevel.NONE, 100.0),
        (EducationLevel.NONE, EducationLevel.BACHELOR, 0.0),
        (EducationLevel.ASSOCIATE, EducationLevel.BACHELOR, 66.67),
        (EducationLevel.BACHELOR, EducationLevel.MASTER, 75.0),
        (EducationLevel.DOCTORATE, EducationLevel.BACHELOR, 100.0),
    ],
)
def test_education_score_respects_ordered_levels(
    attained: EducationLevel,
    required: EducationLevel,
    expected: float,
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    education = ()
    if attained is not EducationLevel.NONE:
        education = (Education("University", "Degree", level=attained),)
    resume = resume_factory(education=education)

    assert MatchingService._education_score(resume, required) == expected


def test_terms_ignore_stop_words_and_responsibility_score_handles_no_target() -> None:
    assert MatchingService._terms("The API and your Python 3.12 platform") == {
        "api",
        "python",
        "platform",
    }
    assert MatchingService._overlap_score({"anything"}, set()) == 100.0
    assert MatchingService._overlap_score({"build"}, {"build", "operate"}) == 50.0


def test_empty_job_requirements_produce_full_score_and_fallback_recommendation(
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

    result = MatchingService().score(resume_factory(), job)

    assert result.overall_score == 100.0
    assert [dimension.raw_score for dimension in result.dimensions] == [100.0] * 5
    assert len(result.recommendations) == 1
    assert result.recommendations[0].category == "presentation"


def test_scoring_weights_reject_values_that_do_not_sum_to_one() -> None:
    with pytest.raises(ValueError, match=r"add up to 1\.0"):
        ScoringWeights(skills=0.5)


def test_scoring_weights_reject_negative_values_even_when_total_is_one() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        ScoringWeights(
            skills=-0.1, experience=0.5, keywords=0.3, education=0.2, responsibilities=0.1
        )


def test_scoring_weights_reject_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        ScoringWeights(
            skills=math.nan,
            experience=0.25,
            keywords=0.15,
            education=0.10,
            responsibilities=0.05,
        )
