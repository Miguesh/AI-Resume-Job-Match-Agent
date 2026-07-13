"""Post-generation checks that block obvious unsupported resume claims."""

from __future__ import annotations

from collections import Counter

from resume_matcher.domain.entities import OptimizedResume, ResumeProfile
from resume_matcher.domain.exceptions import FactualIntegrityError


class ResumeFactGuard:
    def validate(self, source: ResumeProfile, optimized: OptimizedResume) -> None:
        violations: list[str] = []
        self._validate_identity(source, optimized, violations)

        source_skills = {skill.normalized_name for skill in source.skills}
        added_skills = {
            skill.name for skill in optimized.skills if skill.normalized_name not in source_skills
        }
        if added_skills:
            violations.append(f"Unsupported skills added: {', '.join(sorted(added_skills))}")

        source_certifications = {
            certification.casefold().strip() for certification in source.certifications
        }
        added_certifications = {
            certification
            for certification in optimized.certifications
            if certification.casefold().strip() not in source_certifications
        }
        if added_certifications:
            violations.append(
                f"Unsupported certifications added: {', '.join(sorted(added_certifications))}"
            )

        source_roles = {
            (item.company.casefold().strip(), item.title.casefold().strip())
            for item in source.experiences
        }
        for experience in optimized.experiences:
            identity = (
                experience.company.casefold().strip(),
                experience.title.casefold().strip(),
            )
            if identity not in source_roles:
                violations.append(
                    f"Unsupported role added: {experience.title} at {experience.company}"
                )
                continue
            source_experience = next(
                item
                for item in source.experiences
                if (
                    item.company.casefold().strip(),
                    item.title.casefold().strip(),
                )
                == identity
            )
            if (
                experience.start_date,
                experience.end_date,
                experience.location,
            ) != (
                source_experience.start_date,
                source_experience.end_date,
                source_experience.location,
            ):
                violations.append(
                    f"Unsupported role metadata changed: {experience.title} at {experience.company}"
                )
            if (
                self._normalized_items(experience.bullets)
                != self._normalized_items(source_experience.bullets)
                or self._normalized_items(experience.skills)
                != self._normalized_items(source_experience.skills)
            ) and not self._has_change_for(optimized, "experience"):
                violations.append(
                    "Changed experience content has no evidence record: "
                    f"{experience.title} at {experience.company}"
                )

        source_education = {
            (item.institution.casefold().strip(), item.degree.casefold().strip())
            for item in source.education
        }
        for education in optimized.education:
            identity = (
                education.institution.casefold().strip(),
                education.degree.casefold().strip(),
            )
            if identity not in source_education:
                violations.append(
                    f"Unsupported education added: {education.degree} at {education.institution}"
                )
                continue
            source_item = next(
                item
                for item in source.education
                if (
                    item.institution.casefold().strip(),
                    item.degree.casefold().strip(),
                )
                == identity
            )
            if (
                education.field,
                education.graduation_year,
                education.level,
            ) != (
                source_item.field,
                source_item.graduation_year,
                source_item.level,
            ):
                violations.append(
                    f"Unsupported education metadata changed: {education.degree} at "
                    f"{education.institution}"
                )

        source_text = source.raw_text.casefold()
        for change in optimized.changes:
            evidence_items = tuple(
                evidence.strip() for evidence in change.source_evidence if evidence.strip()
            )
            if not evidence_items:
                violations.append(
                    f"Change in '{change.section}' does not cite non-empty source evidence"
                )
                continue
            for evidence in evidence_items:
                if evidence.casefold() not in source_text:
                    violations.append(
                        f"Change in '{change.section}' cites evidence not present in the source"
                    )

        for section in ("headline", "summary"):
            if getattr(source, section) != getattr(optimized, section) and not self._has_change_for(
                optimized, section
            ):
                violations.append(f"Changed {section} has no corresponding evidence record")

        if violations:
            raise FactualIntegrityError(violations)

    @staticmethod
    def _validate_identity(
        source: ResumeProfile,
        optimized: OptimizedResume,
        violations: list[str],
    ) -> None:
        for field_name in ("name", "email", "phone", "location"):
            if getattr(source, field_name) != getattr(optimized, field_name):
                violations.append(f"Identity or contact field changed: {field_name}")

    @staticmethod
    def _has_change_for(optimized: OptimizedResume, section: str) -> bool:
        expected = section.casefold()
        return any(expected in change.section.casefold() for change in optimized.changes)

    @staticmethod
    def _normalized_items(values: tuple[str, ...]) -> Counter[str]:
        return Counter(value.casefold().strip() for value in values)
