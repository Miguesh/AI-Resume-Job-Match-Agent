from __future__ import annotations

import pytest

from resume_matcher.domain.skill_normalizer import (
    create_skill,
    deduplicate_skills,
    display_skill,
    normalize_skill,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  AMAZON Web Services ", "aws"),
        ("K8s", "kubernetes"),
        ("Postgre SQL", "postgresql"),
        ("Fast-API", "fast-api"),
        ("Natural Language Processing", "nlp"),
        ("C++", "c++"),
        ("CI / CD", "ci / cd"),
        ("Data & Analytics", "data and analytics"),
        ("...", ""),
    ],
)
def test_normalize_skill_handles_aliases_and_punctuation(value: str, expected: str) -> None:
    assert normalize_skill(value) == expected


@pytest.mark.parametrize(
    ("normalized", "expected"),
    [("aws", "AWS"), ("rest apis", "REST APIs"), ("python", "Python")],
)
def test_display_skill_uses_canonical_acronyms(normalized: str, expected: str) -> None:
    assert display_skill(normalized) == expected


def test_create_skill_keeps_display_and_matching_forms_together() -> None:
    skill = create_skill("Google Cloud Platform")

    assert skill.name == "GCP"
    assert skill.normalized_name == "gcp"


def test_deduplicate_skills_is_alias_aware_sorted_and_ignores_empty_values() -> None:
    skills = deduplicate_skills(
        ["Postgres", "POSTGRESQL", "", "  ", "Amazon Web Services", "AWS cloud"]
    )

    assert [(skill.name, skill.normalized_name) for skill in skills] == [
        ("AWS", "aws"),
        ("PostgreSQL", "postgresql"),
    ]
