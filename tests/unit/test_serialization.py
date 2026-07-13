from __future__ import annotations

from collections.abc import Callable

import pytest

from resume_matcher.domain.entities import (
    JobProfile,
    MatchAnalysis,
    OptimizedResume,
    ResumeProfile,
)
from resume_matcher.infrastructure.persistence.serialization import (
    job_profile_from_dict,
    job_profile_to_dict,
    match_result_from_dict,
    match_result_to_dict,
    optimized_resume_from_dict,
    optimized_resume_to_dict,
    resume_profile_from_dict,
    resume_profile_to_dict,
)


def test_resume_profile_serialization_round_trip_preserves_all_fields(
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    original = resume_factory()

    payload = resume_profile_to_dict(original)
    restored = resume_profile_from_dict(payload)

    assert restored == original
    assert isinstance(payload["skills"], list)
    assert payload["education"][0]["level"] == "bachelor"


def test_job_profile_serialization_round_trip_preserves_all_fields(
    job_factory: Callable[..., JobProfile],
) -> None:
    original = job_factory()

    payload = job_profile_to_dict(original)
    restored = job_profile_from_dict(payload)

    assert restored == original
    assert payload["education_level"] == "master"


def test_match_result_serialization_round_trip_preserves_nested_enums(
    match_analysis: MatchAnalysis,
) -> None:
    original = match_analysis.result

    payload = match_result_to_dict(original)
    restored = match_result_from_dict(payload)

    assert restored == original
    assert payload["recommendations"][0]["priority"] == "high"
    assert isinstance(restored.dimensions, tuple)
    assert isinstance(restored.recommendations, tuple)


def test_optimized_resume_serialization_round_trip_preserves_change_evidence(
    optimized_resume: OptimizedResume,
) -> None:
    payload = optimized_resume_to_dict(optimized_resume)

    restored = optimized_resume_from_dict(payload)

    assert restored == optimized_resume
    assert restored.changes[0].source_evidence == ("Build reliable APIs",)
    assert payload["changes"][0]["section"] == "summary"


def test_serialized_payload_is_detached_from_immutable_domain_entity(
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    original = resume_factory()
    payload = resume_profile_to_dict(original)

    payload["skills"][0]["name"] = "Changed"
    payload["experiences"][0]["bullets"].append("Invented bullet")

    assert original.skills[0].name == "Python"
    assert "Invented bullet" not in original.experiences[0].bullets


def test_deserialization_rejects_unknown_enum_values(
    job_factory: Callable[..., JobProfile],
) -> None:
    payload = job_profile_to_dict(job_factory())
    payload["education_level"] = "professor"

    with pytest.raises(ValueError, match="professor"):
        job_profile_from_dict(payload)


def test_deserialization_defaults_optional_collections_without_aliasing() -> None:
    first = resume_profile_from_dict({})
    second = resume_profile_from_dict({})

    assert first.skills == second.skills == ()
    assert first.experiences == second.experiences == ()
    assert first.education == second.education == ()
    assert first.raw_text == ""
