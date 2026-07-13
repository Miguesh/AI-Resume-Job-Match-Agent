from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from resume_matcher.domain.entities import (
    Education,
    Experience,
    OptimizationChange,
    OptimizedResume,
    ResumeProfile,
)
from resume_matcher.domain.exceptions import FactualIntegrityError
from resume_matcher.domain.fact_guard import ResumeFactGuard
from resume_matcher.domain.skill_normalizer import create_skill


def test_fact_guard_accepts_only_supported_reordered_content(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    supported = replace(
        optimized_resume,
        skills=tuple(reversed(source.skills)),
        experiences=(replace(source.experiences[0], title=" senior engineer "),),
        changes=(
            OptimizationChange(
                section="summary",
                before=source.summary,
                after=optimized_resume.summary or "",
                reason="Clarifies focus.",
                source_evidence=("  BUILD RELIABLE APIS  ",),
            ),
        ),
    )

    ResumeFactGuard().validate(source, supported)


def test_fact_guard_aggregates_unsupported_skill_role_education_and_evidence(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    unsupported = replace(
        optimized_resume,
        skills=(*source.skills, create_skill("Kubernetes")),
        experiences=(
            *source.experiences,
            Experience(title="CTO", company="Fictional Corp", bullets=("Led everything",)),
        ),
        education=(
            *source.education,
            Education(institution="Imaginary University", degree="Doctorate"),
        ),
        changes=(
            OptimizationChange(
                section="experience",
                before=None,
                after="Increased revenue by one billion dollars.",
                reason="Adds impact.",
                source_evidence=("one billion dollars",),
            ),
        ),
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, unsupported)

    assert error.value.violations == (
        "Unsupported skills added: Kubernetes",
        "Unsupported role added: CTO at Fictional Corp",
        "Unsupported education added: Doctorate at Imaginary University",
        "Change in 'experience' cites evidence not present in the source",
        "Changed summary has no corresponding evidence record",
    )
    assert str(error.value) == "Optimized resume failed factual-integrity checks"


def test_fact_guard_rejects_added_certifications(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    unsupported = replace(
        optimized_resume,
        certifications=(*source.certifications, "Certified Kubernetes Administrator"),
    )

    with pytest.raises(FactualIntegrityError):
        ResumeFactGuard().validate(source, unsupported)


@pytest.mark.parametrize("field", ["headline", "summary"])
def test_fact_guard_rejects_unrecorded_text_rewrites(
    field: str,
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    unsupported = replace(
        optimized_resume,
        **{field: "An unsupported rewrite."},
        changes=(),
    )

    with pytest.raises(FactualIntegrityError, match="factual-integrity") as error:
        ResumeFactGuard().validate(source, unsupported)

    assert any(field in violation for violation in error.value.violations)


def test_fact_guard_rejects_unrecorded_experience_rewrite(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    rewritten = replace(
        source.experiences[0],
        bullets=("Invented an unsupported billion-dollar result.",),
    )
    unsupported = replace(
        optimized_resume,
        summary=source.summary,
        experiences=(rewritten,),
        changes=(),
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, unsupported)

    assert any("Changed experience content" in value for value in error.value.violations)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "Someone Else"),
        ("email", "attacker@example.com"),
        ("phone", "+1 999 999 9999"),
    ],
)
def test_fact_guard_rejects_changed_identity_and_contact_fields(
    field: str,
    value: str,
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    unsupported = replace(optimized_resume, **{field: value})

    with pytest.raises(FactualIntegrityError):
        ResumeFactGuard().validate(source, unsupported)


@pytest.mark.parametrize("evidence", [(), ("",), ("   ",)])
def test_fact_guard_requires_non_empty_source_evidence_for_material_changes(
    evidence: tuple[str, ...],
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    unsupported = replace(
        optimized_resume,
        changes=(
            OptimizationChange(
                section="summary",
                before=source.summary,
                after="A materially rewritten summary.",
                reason="Tailors the summary.",
                source_evidence=evidence,
            ),
        ),
    )

    with pytest.raises(FactualIntegrityError):
        ResumeFactGuard().validate(source, unsupported)
