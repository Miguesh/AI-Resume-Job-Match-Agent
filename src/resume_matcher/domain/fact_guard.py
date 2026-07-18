"""Post-generation checks that block obvious unsupported resume claims."""

from __future__ import annotations

import re
from collections import Counter

from resume_matcher.domain.entities import Experience, OptimizedResume, ResumeProfile
from resume_matcher.domain.exceptions import FactualIntegrityError

_QUANTIFIED_CLAIM_PATTERN = re.compile(r"(?<![\w])(?:[$€£]\s*)?\d[\d,]*(?:\.\d+)?(?:\s*%)?(?![\w])")


class ResumeFactGuard:
    def validate(self, source: ResumeProfile, optimized: OptimizedResume) -> None:
        violations: list[str] = []
        self._validate_identity(source, optimized, violations)

        source_skill_counts = Counter(skill.normalized_name for skill in source.skills)
        optimized_skill_counts = Counter(skill.normalized_name for skill in optimized.skills)
        source_skills = set(source_skill_counts)
        added_skills = {
            skill.name for skill in optimized.skills if skill.normalized_name not in source_skills
        }
        if added_skills:
            violations.append(f"Unsupported skills added: {', '.join(sorted(added_skills))}")
        removed_skills = source_skill_counts - optimized_skill_counts
        if removed_skills:
            violations.append(
                "Verified skills removed: "
                + ", ".join(
                    sorted(
                        skill.name
                        for skill in source.skills
                        if skill.normalized_name in removed_skills
                    )
                )
            )
        duplicated_skills = optimized_skill_counts - source_skill_counts
        duplicated_supported = sorted(
            skill.name
            for skill in optimized.skills
            if skill.normalized_name in source_skills and skill.normalized_name in duplicated_skills
        )
        if duplicated_supported:
            violations.append(f"Verified skills duplicated: {', '.join(duplicated_supported)}")
        source_skill_order = tuple(skill.normalized_name for skill in source.skills)
        optimized_skill_order = tuple(skill.normalized_name for skill in optimized.skills)
        if (
            source_skill_counts == optimized_skill_counts
            and source_skill_order != optimized_skill_order
        ):
            self._require_bound_change(
                optimized,
                section="skills",
                before=", ".join(skill.name for skill in source.skills),
                after=", ".join(skill.name for skill in optimized.skills),
                violation="Reordered skills have no matching before/after evidence record",
                violations=violations,
            )

        source_certifications = Counter(
            certification.casefold().strip() for certification in source.certifications
        )
        optimized_certifications = Counter(
            certification.casefold().strip() for certification in optimized.certifications
        )
        added_certifications = {
            certification
            for certification in optimized.certifications
            if certification.casefold().strip() not in set(source_certifications)
        }
        if added_certifications:
            violations.append(
                f"Unsupported certifications added: {', '.join(sorted(added_certifications))}"
            )
        if source_certifications - optimized_certifications:
            violations.append("Verified certifications were removed")
        duplicated_certifications = optimized_certifications - source_certifications
        if any(value in source_certifications for value in duplicated_certifications):
            violations.append("Verified certifications were duplicated")

        unmatched_source_roles = set(range(len(source.experiences)))
        for experience in optimized.experiences:
            identity = (
                experience.company.casefold().strip(),
                experience.title.casefold().strip(),
            )
            candidates = [
                index
                for index in unmatched_source_roles
                if (
                    source.experiences[index].company.casefold().strip(),
                    source.experiences[index].title.casefold().strip(),
                )
                == identity
            ]
            if not candidates:
                known_identity = any(
                    (
                        item.company.casefold().strip(),
                        item.title.casefold().strip(),
                    )
                    == identity
                    for item in source.experiences
                )
                label = "Duplicate role" if known_identity else "Unsupported role added"
                violations.append(f"{label}: {experience.title} at {experience.company}")
                continue
            source_index = next(
                (
                    index
                    for index in candidates
                    if (
                        source.experiences[index].start_date,
                        source.experiences[index].end_date,
                    )
                    == (experience.start_date, experience.end_date)
                ),
                candidates[0],
            )
            unmatched_source_roles.remove(source_index)
            source_experience = source.experiences[source_index]
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
            section = f"experience:{source_index}"
            if self._normalized_sequence(experience.bullets) != self._normalized_sequence(
                source_experience.bullets
            ):
                self._require_bound_change(
                    optimized,
                    section=section,
                    before="\n".join(source_experience.bullets),
                    after="\n".join(experience.bullets),
                    violation=(
                        "Changed experience bullets have no matching before/after evidence record: "
                        f"{experience.title} at {experience.company}"
                    ),
                    violations=violations,
                )
            if self._normalized_items(experience.skills) != self._normalized_items(
                source_experience.skills
            ):
                violations.append(
                    "Unsupported experience skills changed: "
                    f"{experience.title} at {experience.company}"
                )

        for source_index in sorted(unmatched_source_roles):
            source_experience = source.experiences[source_index]
            violations.append(
                f"Verified role removed: {source_experience.title} at {source_experience.company}"
            )

        unmatched_source_education = set(range(len(source.education)))
        for education in optimized.education:
            identity = (
                education.institution.casefold().strip(),
                education.degree.casefold().strip(),
            )
            candidates = [
                index
                for index in unmatched_source_education
                if (
                    source.education[index].institution.casefold().strip(),
                    source.education[index].degree.casefold().strip(),
                )
                == identity
            ]
            if not candidates:
                known_identity = any(
                    (
                        item.institution.casefold().strip(),
                        item.degree.casefold().strip(),
                    )
                    == identity
                    for item in source.education
                )
                label = "Duplicate education" if known_identity else "Unsupported education added"
                violations.append(f"{label}: {education.degree} at {education.institution}")
                continue
            source_index = next(
                (
                    index
                    for index in candidates
                    if (
                        source.education[index].field,
                        source.education[index].graduation_year,
                        source.education[index].level,
                    )
                    == (education.field, education.graduation_year, education.level)
                ),
                candidates[0],
            )
            unmatched_source_education.remove(source_index)
            source_item = source.education[source_index]
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

        for source_index in sorted(unmatched_source_education):
            source_item = source.education[source_index]
            violations.append(
                f"Verified education removed: {source_item.degree} at {source_item.institution}"
            )

        source_text = source.raw_text.casefold()
        for change in optimized.changes:
            snapshots = self._change_snapshots(source, optimized, change.section)
            matching_snapshots = tuple(
                snapshot
                for snapshot in snapshots
                if self._same_optional_text(change.before, snapshot[0])
                and self._same_text(change.after, snapshot[1])
            )
            if not snapshots:
                violations.append(
                    f"Change in '{change.section}' does not identify an actual supported "
                    "section change"
                )
            elif not matching_snapshots:
                violations.append(
                    f"Change in '{change.section}' does not match the actual before/after content"
                )
            else:
                supported_claims: set[str] = set()
                for snapshot in matching_snapshots:
                    supported_claims.update(self._quantified_claims(snapshot[2]))
                unsupported_claims = self._quantified_claims(change.after) - supported_claims
                if unsupported_claims:
                    violations.append(
                        f"Change in '{change.section}' adds unsupported quantitative claims: "
                        f"{', '.join(sorted(unsupported_claims))}"
                    )

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
                elif matching_snapshots and not any(
                    evidence.casefold() in snapshot[2].casefold() for snapshot in matching_snapshots
                ):
                    violations.append(
                        f"Change in '{change.section}' cites evidence unrelated to that section"
                    )

        for section in ("headline", "summary"):
            before = getattr(source, section)
            after = getattr(optimized, section)
            if before != after:
                self._require_bound_change(
                    optimized,
                    section=section,
                    before=before,
                    after=after or "",
                    violation=f"Changed {section} has no matching before/after evidence record",
                    violations=violations,
                )

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

    @classmethod
    def _require_bound_change(
        cls,
        optimized: OptimizedResume,
        *,
        section: str,
        before: str | None,
        after: str,
        violation: str,
        violations: list[str],
    ) -> None:
        if not any(
            change.section.casefold().strip() == section.casefold().strip()
            and cls._same_optional_text(change.before, before)
            and cls._same_text(change.after, after)
            for change in optimized.changes
        ):
            violations.append(violation)

    @classmethod
    def _change_snapshots(
        cls,
        source: ResumeProfile,
        optimized: OptimizedResume,
        section: str,
    ) -> tuple[tuple[str | None, str, str], ...]:
        normalized_section = section.casefold().strip()
        if normalized_section in {"headline", "summary"}:
            before = getattr(source, normalized_section)
            after = getattr(optimized, normalized_section)
            context = f"{source.raw_text}\n{source.total_years_experience:g}"
            return cls._changed_snapshot(before, after or "", context)
        if normalized_section == "skills":
            before = ", ".join(skill.name for skill in source.skills)
            after = ", ".join(skill.name for skill in optimized.skills)
            context = "\n".join(skill.name for skill in source.skills)
            return cls._changed_snapshot(before, after, context)
        if normalized_section.startswith("experience:"):
            raw_index = normalized_section.partition(":")[2].strip()
            if not raw_index.isdecimal():
                return ()
            source_index = int(raw_index)
            if source_index >= len(source.experiences):
                return ()
            source_item = source.experiences[source_index]
            optimized_item = cls._optimized_experience_mapping(source, optimized).get(source_index)
            if optimized_item is None:
                return ()
            context = "\n".join(
                (
                    source_item.title,
                    source_item.company,
                    source_item.start_date or "",
                    source_item.end_date or "",
                    *source_item.bullets,
                    *source_item.skills,
                )
            )
            return cls._changed_snapshot(
                "\n".join(source_item.bullets),
                "\n".join(optimized_item.bullets),
                context,
            )
        return ()

    @staticmethod
    def _optimized_experience_mapping(
        source: ResumeProfile,
        optimized: OptimizedResume,
    ) -> dict[int, Experience]:
        """Pair repeated role identities one-to-one using the same policy as validation."""
        unmatched_source_roles = set(range(len(source.experiences)))
        mapping: dict[int, Experience] = {}
        for optimized_item in optimized.experiences:
            identity = (
                optimized_item.company.casefold().strip(),
                optimized_item.title.casefold().strip(),
            )
            candidates = [
                index
                for index in unmatched_source_roles
                if (
                    source.experiences[index].company.casefold().strip(),
                    source.experiences[index].title.casefold().strip(),
                )
                == identity
            ]
            if not candidates:
                continue
            source_index = next(
                (
                    index
                    for index in candidates
                    if (
                        source.experiences[index].start_date,
                        source.experiences[index].end_date,
                    )
                    == (optimized_item.start_date, optimized_item.end_date)
                ),
                candidates[0],
            )
            unmatched_source_roles.remove(source_index)
            mapping[source_index] = optimized_item
        return mapping

    @classmethod
    def _changed_snapshot(
        cls,
        before: str | None,
        after: str,
        evidence_context: str,
    ) -> tuple[tuple[str | None, str, str], ...]:
        if cls._same_optional_text(before, after):
            return ()
        return ((before, after, evidence_context),)

    @staticmethod
    def _same_optional_text(first: str | None, second: str | None) -> bool:
        if first is None or second is None:
            return first is second
        return ResumeFactGuard._same_text(first, second)

    @staticmethod
    def _same_text(first: str, second: str) -> bool:
        return first == second

    @staticmethod
    def _quantified_claims(value: str) -> set[str]:
        return {re.sub(r"[\s,]", "", token) for token in _QUANTIFIED_CLAIM_PATTERN.findall(value)}

    @staticmethod
    def _normalized_sequence(values: tuple[object, ...]) -> tuple[str, ...]:
        return tuple(str(value).casefold().strip() for value in values)

    @staticmethod
    def _normalized_items(values: tuple[str, ...]) -> Counter[str]:
        return Counter(value.casefold().strip() for value in values)
