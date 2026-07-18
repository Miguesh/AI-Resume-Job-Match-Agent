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
from resume_matcher.infrastructure.ai.contracts import (
    EducationContract,
    ExperienceContract,
    OptimizationChangeContract,
    OptimizedResumeContract,
)
from resume_matcher.infrastructure.ai.mappers import optimized_from_contract


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
            OptimizationChange(
                section="skills",
                before=", ".join(skill.name for skill in source.skills),
                after=", ".join(skill.name for skill in reversed(source.skills)),
                reason="Prioritizes relevant verified skills.",
                source_evidence=tuple(skill.name for skill in source.skills),
            ),
        ),
    )

    ResumeFactGuard().validate(source, supported)


def test_fact_guard_rejects_unrecorded_skill_reorder(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    candidate = replace(
        optimized_resume,
        summary=source.summary,
        skills=tuple(reversed(source.skills)),
        changes=(),
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, candidate)

    assert any("Reordered skills" in item for item in error.value.violations)


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
        "Change in 'experience' does not identify an actual supported section change",
        "Change in 'experience' cites evidence not present in the source",
        "Changed summary has no matching before/after evidence record",
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

    assert any("Changed experience bullets" in value for value in error.value.violations)


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


def test_fact_guard_rejects_change_record_not_bound_to_returned_content(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    unsupported = replace(
        optimized_resume,
        changes=(
            OptimizationChange(
                section="summary",
                before="A different source summary.",
                after=optimized_resume.summary or "",
                reason="Claims to document the rewrite.",
                source_evidence=("Build reliable APIs",),
            ),
        ),
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, unsupported)

    assert any("actual before/after" in value for value in error.value.violations)
    assert any("Changed summary" in value for value in error.value.violations)


def test_fact_guard_requires_role_specific_change_record(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    rewritten = replace(
        source.experiences[0],
        bullets=tuple(reversed(source.experiences[0].bullets)),
    )
    unsupported = replace(
        optimized_resume,
        summary=source.summary,
        experiences=(rewritten,),
        changes=(
            OptimizationChange(
                section="experience",
                before="\n".join(source.experiences[0].bullets),
                after="\n".join(rewritten.bullets),
                reason="Reorders evidence.",
                source_evidence=source.experiences[0].bullets,
            ),
        ),
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, unsupported)

    assert any("experience bullets" in value for value in error.value.violations)
    assert any("actual supported section" in value for value in error.value.violations)


@pytest.mark.parametrize(
    ("field", "replacement", "expected_violation"),
    [
        ("skills", lambda source: source.skills[:-1], "Verified skills removed"),
        (
            "skills",
            lambda source: (*source.skills, source.skills[0]),
            "Verified skills duplicated",
        ),
        ("certifications", lambda source: (), "Verified certifications were removed"),
        (
            "certifications",
            lambda source: (*source.certifications, source.certifications[0]),
            "Verified certifications were duplicated",
        ),
        ("experiences", lambda source: (), "Verified role removed"),
        (
            "experiences",
            lambda source: (*source.experiences, source.experiences[0]),
            "Duplicate role",
        ),
        ("education", lambda source: (), "Verified education removed"),
        (
            "education",
            lambda source: (*source.education, source.education[0]),
            "Duplicate education",
        ),
    ],
)
def test_fact_guard_requires_exact_structured_inventories(
    field: str,
    replacement: Callable[[ResumeProfile], tuple[object, ...]],
    expected_violation: str,
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    unsupported = replace(optimized_resume, **{field: replacement(source)})

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, unsupported)

    assert any(expected_violation in value for value in error.value.violations)


def test_fact_guard_rejects_changed_per_role_skill_inventory(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    changed_role = replace(
        source.experiences[0],
        skills=(*source.experiences[0].skills, "Kubernetes"),
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(
            source,
            replace(optimized_resume, experiences=(changed_role,)),
        )

    assert any("Unsupported experience skills changed" in item for item in error.value.violations)


def test_fact_guard_rejects_fabricated_quantified_claim(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory(
        summary="Improved conversion by 5%.",
        raw_text="Jane Doe\nImproved conversion by 5%.\nPython FastAPI Postgres",
    )
    after = "Improved conversion by 99%."
    candidate = replace(
        optimized_resume,
        summary=after,
        changes=(
            OptimizationChange(
                section="summary",
                before=source.summary,
                after=after,
                reason="Inflates the source metric.",
                source_evidence=("Improved conversion by 5%.",),
            ),
        ),
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, candidate)

    assert any("unsupported quantitative claims: 99%" in item for item in error.value.violations)


def test_fact_guard_accepts_quantified_claim_present_in_section_context(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    source_role = source.experiences[0]
    bullets = tuple(reversed(source_role.bullets))
    candidate = replace(
        optimized_resume,
        summary=source.summary,
        experiences=(replace(source_role, bullets=bullets),),
        changes=(
            OptimizationChange(
                section="experience:0",
                before="\n".join(source_role.bullets),
                after="\n".join(bullets),
                reason="Prioritizes a verified metric.",
                source_evidence=("Reduced processing latency by 35 percent.",),
            ),
        ),
    )

    ResumeFactGuard().validate(source, candidate)


def test_experience_index_disambiguates_repeated_role_identity(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    first_role = Experience(
        title="Engineer",
        company="Example Corp",
        start_date="2020",
        end_date="2022",
        bullets=("Built internal APIs.",),
        skills=("Python",),
    )
    second_role = replace(
        first_role,
        bullets=("Reduced latency by 35 percent.", "Led API reliability reviews."),
    )
    source = resume_factory(
        experiences=(first_role, second_role),
        raw_text=(
            "Example Corp Engineer Built internal APIs. Reduced latency by 35 percent. "
            "Led API reliability reviews. Python FastAPI PostgreSQL"
        ),
    )
    reordered_bullets = tuple(reversed(second_role.bullets))
    candidate = replace(
        optimized_resume,
        summary=source.summary,
        experiences=(first_role, replace(second_role, bullets=reordered_bullets)),
        changes=(
            OptimizationChange(
                section="experience:1",
                before="\n".join(second_role.bullets),
                after="\n".join(reordered_bullets),
                reason="Prioritizes reliability evidence.",
                source_evidence=second_role.bullets,
            ),
        ),
    )

    ResumeFactGuard().validate(source, candidate)


def test_fact_guard_requires_exact_change_serialization(
    resume_factory: Callable[..., ResumeProfile],
    optimized_resume: OptimizedResume,
) -> None:
    source = resume_factory()
    invalid_change = replace(
        optimized_resume.changes[0],
        before=f"{source.summary} ",
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, replace(optimized_resume, changes=(invalid_change,)))

    assert any("actual before/after" in item for item in error.value.violations)


def test_optimized_mapper_preserves_provider_order_and_fact_guard_accepts_reorder(
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    source = resume_factory()
    contract = OptimizedResumeContract(
        name=source.name,
        headline=source.headline,
        summary=source.summary,
        email=source.email,
        phone=source.phone,
        location=source.location,
        skills=["Postgres", "Python", "FastAPI"],
        experiences=[
            ExperienceContract(
                title=item.title,
                company=item.company,
                start_date=item.start_date,
                end_date=item.end_date,
                location=item.location,
                bullets=list(item.bullets),
                skills=list(item.skills),
            )
            for item in source.experiences
        ],
        education=[
            EducationContract(
                institution=item.institution,
                degree=item.degree,
                field=item.field,
                graduation_year=item.graduation_year,
                level=item.level,
            )
            for item in source.education
        ],
        certifications=list(source.certifications),
        changes=[
            OptimizationChangeContract(
                section="skills",
                before="Python, FastAPI, PostgreSQL",
                after="PostgreSQL, Python, FastAPI",
                reason="Prioritizes relevant verified skills.",
                source_evidence=["PostgreSQL", "Python", "FastAPI"],
            )
        ],
    )

    optimized = optimized_from_contract(contract)

    assert [skill.normalized_name for skill in optimized.skills] == [
        "postgresql",
        "python",
        "fastapi",
    ]
    ResumeFactGuard().validate(source, optimized)


def test_mapper_does_not_hide_provider_duplicates_from_fact_guard(
    resume_factory: Callable[..., ResumeProfile],
) -> None:
    source = resume_factory()
    optimized = optimized_from_contract(
        OptimizedResumeContract(
            name=source.name,
            headline=source.headline,
            summary=source.summary,
            email=source.email,
            phone=source.phone,
            location=source.location,
            skills=["Python", "FastAPI", "Postgres", "Python"],
            experiences=[
                ExperienceContract(
                    title=source.experiences[0].title,
                    company=source.experiences[0].company,
                    start_date=source.experiences[0].start_date,
                    end_date=source.experiences[0].end_date,
                    location=source.experiences[0].location,
                    bullets=list(source.experiences[0].bullets),
                    skills=list(source.experiences[0].skills),
                )
            ],
            education=[
                EducationContract(
                    institution=source.education[0].institution,
                    degree=source.education[0].degree,
                    field=source.education[0].field,
                    graduation_year=source.education[0].graduation_year,
                    level=source.education[0].level,
                )
            ],
            certifications=[*source.certifications, source.certifications[0]],
        )
    )

    with pytest.raises(FactualIntegrityError) as error:
        ResumeFactGuard().validate(source, optimized)

    assert any("skills duplicated" in item for item in error.value.violations)
    assert any("certifications were duplicated" in item for item in error.value.violations)
